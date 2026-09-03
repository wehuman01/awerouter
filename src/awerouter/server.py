"""awerouter — smart LLM router daemon.

Routes coding-agent requests to flash (cheap/fast) or pro (strong/accurate)
providers based on structural request signals. Same-protocol passthrough
proxy (anthropic / openai-chat / openai-responses); no translation, no
request body parsing on the response path. Profiles may opt into rtk
tool-result compression on the request path (default off).
"""

from __future__ import annotations

import asyncio
import errno
import json
import os
import signal
import time
import urllib.request
import uuid

import aiohttp
from aiohttp import web

from awerouter import __version__
from awerouter import rtk
from awerouter import runtime
from awerouter.claude import (
    AUTH_SENTINEL as CLAUDE_SENTINEL,
    ClaudeAuthError,
    apply_claude_auth,
    claude_auth_path,
    login_status,
)
from awerouter.codex import AUTH_SENTINEL, CodexAuthError, apply_codex_auth, load_codex_login
from awerouter.config import (
    die,
    expand_value,
    is_loopback_url,
    load_for_profile,
    providers_path,
    routing_path,
)
from awerouter.logging import append, auto_threshold, ensure_log_dir
from awerouter.protocols import ENDPOINT_PATHS, extract
from awerouter.router import resolve
from awerouter.types import RequestLog, ResolveResult
from awerouter.update_check import cached_update_hint
from awerouter.vision import (
    CAPTIONS,
    build_caption_body,
    cache_key,
    collect_images,
    image_key,
    parse_caption_response,
    replace_images,
)


# Per-request opt-out for rtk compression (value "off" disables it), so a
# debugging session can see raw tool output without touching routing.json.
TOKEN_SAVER_HEADER = "x-awerouter-token-saver"


def _rtk_enabled(request: web.Request, profile) -> bool:
    if not profile.rtk:
        return False
    return request.headers.get(TOKEN_SAVER_HEADER, "").lower() != "off"


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------

# Headers we always pass through from the client request.
_PASS_THROUGH = frozenset({
    "anthropic-version",
    "content-type",
    "x-api-key",
    "x-request-id",
    "traceparent",
    "tracestate",
})


def _filter_headers(headers: dict) -> dict:
    """Keep only pass-through headers, drop hop-by-hop and auth."""
    out = {}
    for k, v in headers.items():
        name = k.lower()
        if name in _PASS_THROUGH:
            out[name] = v
    return out


async def _set_auth(headers: dict, provider, env: dict | None = None,
                    force_claude_refresh: bool = False) -> None:
    """Replace any incoming auth header with the destination provider's creds.

    No-auth providers (local model servers) send no auth header at all — the
    client's incoming key is dropped, not forwarded. Authorization header
    auto-prefixes 'Bearer ' if the value lacks it. The 'codex' sentinel loads
    the local Codex CLI login and writes the ChatGPT account header set; the
    'claude' sentinel loads the awerouter-owned OAuth login (off the event
    loop — a stale token refreshes over the network here).
    """
    headers.pop("authorization", None)
    headers.pop("x-api-key", None)
    if not provider.auth:
        return
    if provider.auth == AUTH_SENTINEL:
        apply_codex_auth(headers)
        return
    if provider.auth == CLAUDE_SENTINEL:
        await asyncio.to_thread(apply_claude_auth, headers, force_claude_refresh)
        return
    auth_value = expand_value(provider.auth, env)
    if provider.auth_header == "authorization" and not auth_value.lower().startswith("bearer "):
        auth_value = f"Bearer {auth_value}"
    headers[provider.auth_header] = auth_value


# Known clients and their User-Agent prefixes, normalized to a stable label.
# awerouter only sees the wire request, so the UA header is the only place
# the caller's identity exists (aweswitch launches clients outside our view).
_AGENT_RULES = (
    ("claude", "claude-code"),
    ("codex", "codex"),
    ("opencode", "opencode"),
    ("cursor", "cursor"),
    ("curl", "curl"),
)


def _agent_from_ua(ua: str) -> str:
    """Best-effort caller identity: 'claude-cli/2.0 (external, cli)' → 'claude-code'.

    Unknown but identifiable clients fall back to the first UA token
    ('python-requests/2.31' → 'python-requests'); empty UA → ''.
    """
    if not ua:
        return ""
    token = ua.split()[0].split("/")[0].lower()
    for prefix, label in _AGENT_RULES:
        if prefix in token:
            return label
    return token


# ---------------------------------------------------------------------------
# Upstream proxy (single attempt)
# ---------------------------------------------------------------------------


def _codex_proxy(base_url: str) -> "str | None":
    """Subscription-login backends (chatgpt.com, api.anthropic.com) commonly
    need the shell proxy to be reachable; honor the same env vars the codex
    and claude CLIs honor (https_proxy/all_proxy, system settings on macOS).
    Loopback targets never take the proxy (local relays); other providers
    stay direct, exactly as before."""
    if is_loopback_url(base_url):
        return None
    proxies = urllib.request.getproxies()
    proxy = proxies.get("https") or proxies.get("all")
    if proxy and not proxy.startswith(("http://", "https://")):
        return None  # socks proxies would need aiohttp-socks; not a dependency
    return proxy


def _codex_sse_response(raw: bytes) -> "dict | None":
    """Extract the final `response` object from a codex SSE stream.

    Returns the object carried by the last response.completed / response.failed
    event, or None when the stream ended without either (truncated / no
    terminal event). The codex backend's terminal object omits the output
    items, so they are rebuilt from the response.output_item.done events.
    """
    found = None
    items = []
    for line in raw.decode("utf-8", "replace").splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        ptype = payload.get("type")
        if ptype == "response.output_item.done" and isinstance(payload.get("item"), dict):
            items.append(payload["item"])
        elif ptype in ("response.completed", "response.failed"):
            found = payload.get("response")
    if isinstance(found, dict) and not found.get("output") and items:
        found["output"] = items
    return found


async def _proxy_request(
    session: aiohttp.ClientSession,
    body: dict,
    dest,
    providers: dict,
    headers: dict,
    path: str,
    timeout: aiohttp.ClientTimeout,
    force_claude_refresh: bool = False,
) -> aiohttp.ClientResponse:
    """Fire one upstream request. Raises on network/timeout errors."""
    provider = providers[dest.provider_name]
    upstream_url = provider.base_url.rstrip("/") + path

    # Rewrite model to the destination's real model id (copy: body is reused across retries)
    body = dict(body)
    body["model"] = dest.model
    if provider.auth == AUTH_SENTINEL:
        # The ChatGPT Codex backend is zero-data-retention: the CLI itself
        # always sends store=false, and a client's store=true is rejected.
        body["store"] = False
        # Sampling controls are CLI-internal; clients that send them get 400s.
        body.pop("max_output_tokens", None)
        if not body.get("stream"):
            # The backend only speaks SSE. A non-streaming client gets the
            # stream buffered back into one JSON response (in _proxy_flow).
            body["stream"] = True

    # Auth
    await _set_auth(headers, provider, os.environ, force_claude_refresh)

    sub_auth = provider.auth in (AUTH_SENTINEL, CLAUDE_SENTINEL)
    return await session.post(
        upstream_url,
        json=body,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,
        proxy=_codex_proxy(provider.base_url) if sub_auth else None,
    )


# ---------------------------------------------------------------------------
# Image bridge (opt-in): flash transcribes history images to text
# ---------------------------------------------------------------------------

CAPTION_TIMEOUT = aiohttp.ClientTimeout(connect=10, total=60)


async def _caption_image(session, provider, model: str, protocol: str,
                         image_part: dict) -> str:
    """One non-streaming transcription call to the multimodal destination.

    Raises on any failure — the caller falls back to the plain image route.
    """
    body = build_caption_body(protocol, model, image_part)
    headers = {"content-type": "application/json"}
    if protocol == "anthropic":
        headers["anthropic-version"] = "2023-06-01"
    await _set_auth(headers, provider, os.environ)
    url = provider.base_url.rstrip("/") + ENDPOINT_PATHS[protocol]
    async with session.post(url, json=body, headers=headers,
                            timeout=CAPTION_TIMEOUT, allow_redirects=False) as up:
        if up.status != 200:
            raise RuntimeError(f"caption upstream status {up.status}")
        data = await up.json(content_type=None)
    caption = parse_caption_response(protocol, data)
    if not caption:
        raise RuntimeError("caption response carried no text")
    return caption


async def _bridge_images(request_id: str, session, body: dict, protocol: str,
                         profile, providers: dict, settings) -> bool:
    """Replace history images with flash transcriptions so a text-only pro
    can continue the session. Returns True when the body was rewritten.

    Fires only when the request carries images but NOT in the final message
    (a fresh upload routes to the multimodal imageModel natively). Every
    caption must succeed before any rewrite happens; on failure the body
    stays untouched and the L1 image guard routes the request as before.
    """
    feat = extract(protocol, body)
    if not (feat.has_image and not feat.has_new_image):
        return False
    dest = profile.destinations[settings.image_model]
    provider = providers[dest.provider_name]
    if provider.auth == AUTH_SENTINEL:
        return False  # SSE-only codex backend cannot serve non-streaming captions

    captions: dict = {}
    for part in collect_images(body, protocol):
        ihash = image_key(protocol, part)
        caption = CAPTIONS.get(cache_key(provider.name, dest.model, ihash))
        if caption is None:
            t0 = time.monotonic()
            try:
                caption = await _caption_image(
                    session, provider, dest.model, protocol, part)
            except Exception as exc:  # any failure falls back to the image route
                print(f"  bridge: caption failed ({exc}); {request_id} "
                      f"keeps the image route -> {settings.image_model}")
                return False
            CAPTIONS.put(cache_key(provider.name, dest.model, ihash), caption)
            print(f"  bridge: {dest.provider_name}/{dest.model} transcribed image "
                  f"{ihash[:8]} in {time.monotonic() - t0:.1f}s")
        captions[ihash] = caption
    replace_images(body, protocol, dest.model, captions)
    return True


# ---------------------------------------------------------------------------
# Request handlers
# ---------------------------------------------------------------------------


def _resolve_for_request(body: dict, profile, settings, protocol: str) -> ResolveResult:
    """Shared routing decision for all message-shaped endpoints."""
    feat = extract(protocol, body)
    tr = settings.tool_routing
    return resolve(
        body.get("model") or None,
        feat,
        profile.destinations,
        settings.background_model,
        settings.think_model,
        profile.long_context_threshold,
        tr.web_search or settings.web_search_model,
        settings.search_result_discount,
        tr.edit,
        settings.image_model,
        settings.default_model,
    )


class _RoutingState:
    """Mutable routing state shared across the retry loop."""

    def __init__(self, profile, settings, body: dict, agent: str = "", rtk_saved: int = 0,
                 protocol: str = ""):
        self.profile = profile
        self.body = body
        self.inbound_model = body.get("model") or ""
        self.agent = agent
        self.rtk_saved = rtk_saved
        self.protocol = protocol
        self.result = _resolve_for_request(body, profile, settings, protocol)
        self.attempt = 0
        self.streaming_started = False
        self.codex_retried = False          # 401 auth retry happened (codex re-read / claude refresh)
        self.claude_force_refresh = False   # next upstream call forces a claude token refresh
        self.codex_stream_fix = False


def _log_failure(state: _RoutingState, request_id: str, t0: float, status: int) -> None:
    """Log requests that never got an upstream response (502 path)."""
    dest = state.profile.destinations[state.result.destination]
    ensure_log_dir()
    append(RequestLog(
        ts=_now_iso(),
        request_id=request_id,
        model_in=state.inbound_model or "<none>",
        label=state.result.label,
        destination=state.result.destination,
        provider=dest.provider_name,
        model_out=dest.model,
        status=status,
        ms=int((time.monotonic() - t0) * 1000),
        bytes=0,
        token_count=state.result.inspect.token_count,
        tokens=state.result.inspect.token_breakdown,
        file_search_tokens=state.result.inspect.file_search_tokens,
        rtk_saved=state.rtk_saved,
        profile=state.profile.name,
        protocol=state.protocol,
        agent=state.agent,
        codex_retried=state.codex_retried,
    ))


def _protocol_mismatch(request: web.Request, endpoint_protocol: str) -> web.HTTPBadRequest:
    profile = request.app["profile"]
    return web.HTTPBadRequest(
        text=json.dumps({"error": {"message": (
            f"profile '{profile.name}' speaks '{profile.protocol}'; "
            f"this endpoint serves '{endpoint_protocol}'. "
            "Start a profile of the matching protocol, or point this client elsewhere."
        )}}),
        content_type="application/json",
    )


async def _proxy_flow(request: web.Request, endpoint_protocol: str) -> web.StreamResponse:
    """Generic same-protocol proxy flow: route, forward, retry, stream back, log."""
    profile = request.app["profile"]
    settings = request.app["settings"]
    session: aiohttp.ClientSession = request.app["session"]

    if endpoint_protocol not in profile.protocols:
        raise _protocol_mismatch(request, endpoint_protocol)
    providers: dict = request.app["providers"][endpoint_protocol]

    t0 = time.monotonic()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    body = await request.json()
    headers = _filter_headers(dict(request.headers))
    path = ENDPOINT_PATHS[endpoint_protocol]

    # Timeout: generous for streaming, tight for non-streaming
    is_stream = body.get("stream", False)
    timeout = aiohttp.ClientTimeout(
        connect=10,
        total=None if is_stream else 120,
        sock_read=None if is_stream else 120,
    )

    # Image bridge before rtk/routing: history images become flash
    # transcriptions, so what rtk compresses and the router scores is
    # exactly what goes upstream.
    if settings.image_bridge:
        await _bridge_images(request_id, session, body, endpoint_protocol,
                             profile, providers, settings)

    # rtk compression before routing: L3 decisions, effective_tokens, and the
    # usage log then reflect what is actually sent (and billed) upstream.
    # Runs once — retries and the flash→pro fallback reuse the same body.
    rtk_saved = 0
    if _rtk_enabled(request, profile):
        stats = rtk.compress_body(body, endpoint_protocol)
        line = rtk.format_log(stats)
        if line:
            print(line)
        rtk_saved = stats.saved_tokens if stats else 0

    state = _RoutingState(profile, settings, body,
                          _agent_from_ua(request.headers.get("User-Agent", "")),
                          rtk_saved, endpoint_protocol)

    while True:
        dest_key = state.result.destination
        dest = state.profile.destinations[dest_key]
        state.attempt += 1
        state.codex_stream_fix = (
            providers[dest.provider_name].auth == AUTH_SENTINEL
            and not state.body.get("stream")
        )

        try:
            up = await _proxy_request(
                session, state.body, dest, providers, dict(headers), path, timeout,
                state.claude_force_refresh,
            )
        except (CodexAuthError, ClaudeAuthError) as exc:
            # Login missing/invalid — retrying can't help; tell the user.
            _log_failure(state, request_id, t0, 503)
            raise web.HTTPServiceUnavailable(
                text=json.dumps({"error": {"message": str(exc)}}),
                content_type="application/json",
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            # Network-level failure
            if dest_key == "flash" and state.attempt == 1:
                state.result = _fallback_result(state)
                continue
            _log_failure(state, request_id, t0, 502)
            raise web.HTTPBadGateway(
                text=json.dumps({"error": {"message": f"upstream error: {exc}"}}),
                content_type="application/json",
            )

        # We have a response — decide whether to fallback or stream back
        status = up.status
        is_transient = status in (429, 408) or (status >= 500 and status < 600)

        if is_transient and dest_key == "flash" and state.attempt == 1 and not state.streaming_started:
            up.close()
            state.result = _fallback_result(state)
            continue

        # A codex-account 401 usually means the login file changed under us
        # (the local CLI refreshed it): re-read auth.json and retry the same
        # destination once before surfacing the 401 to the client. A
        # claude-account 401 gets the same one-shot retry with a forced token
        # refresh (stale clock, token rotated by another process).
        auth = providers[dest.provider_name].auth
        if status == 401 and not state.codex_retried and auth in (AUTH_SENTINEL, CLAUDE_SENTINEL):
            up.close()
            state.codex_retried = True
            state.claude_force_refresh = auth == CLAUDE_SENTINEL
            state.attempt -= 1  # login retry, not a fallback attempt
            continue

        # Second 401: the login itself is rejected (dead account token, not a
        # mid-flight refresh). When flash rides a subscription login and pro
        # has its own key, the same flash→pro rescue as transient failures
        # keeps the request alive — one printed line per fallback, so a dead
        # login is loud instead of silently burning paid pro. Pro on the same
        # login can't help; the 401 surfaces as before.
        if (status == 401 and auth in (AUTH_SENTINEL, CLAUDE_SENTINEL)
                and dest_key == "flash" and state.attempt == 1
                and providers[state.profile.destinations["pro"].provider_name].auth != auth):
            up.close()
            print(f"  {auth} 401 -> login rejected after retry; {request_id} falls back to pro")
            state.result = _fallback_result(state)
            continue

        # A codex 200 for a non-streaming client: the upstream ran SSE (the
        # backend has no non-streaming mode) — buffer it back into one JSON
        # response object, which is what the client asked for.
        if (state.codex_stream_fix and status == 200):
            raw = await up.read()
            up.close()
            byte_count = len(raw)
            ms = int((time.monotonic() - t0) * 1000)
            obj = _codex_sse_response(raw)
            if obj is None:
                response_body = {
                    "error": {
                        "message": "codex upstream stream ended without a completed response",
                    },
                }
                response_status = 502
            elif obj.get("error"):
                response_body = obj
                response_status = 500
            else:
                response_body = obj
                response_status = 200
            ensure_log_dir()
            append(RequestLog(
                ts=_now_iso(),
                request_id=request_id,
                model_in=state.inbound_model or "<none>",
                label=state.result.label,
                destination=dest_key,
                provider=dest.provider_name,
                model_out=dest.model,
                status=response_status,
                ms=ms,
                duration_ms=int((time.monotonic() - t0) * 1000),
                bytes=byte_count,
                token_count=state.result.inspect.token_count,
                tokens=state.result.inspect.token_breakdown,
                file_search_tokens=state.result.inspect.file_search_tokens,
                rtk_saved=state.rtk_saved,
                profile=profile.name,
                protocol=state.protocol,
                agent=state.agent,
                codex_retried=state.codex_retried,
            ))
            return web.json_response(response_body, status=response_status)

        # Success path or non-fallbackable error — stream back
        ms = int((time.monotonic() - t0) * 1000)
        resp = web.StreamResponse(status=status)

        # Copy upstream content-type, anthropic-version
        for h in ("content-type", "anthropic-version", "x-request-id"):
            val = up.headers.get(h)
            if val:
                resp.headers[h] = val

        byte_count = 0
        try:
            try:
                await resp.prepare(request)
            except (aiohttp.ClientError, ConnectionError):
                # Client hung up before we wrote headers — not an upstream
                # failure. Log the request as a client disconnect and stop
                # quietly instead of letting aiohttp log a 500 traceback.
                status = 499
            else:
                try:
                    async for chunk in up.content.iter_any():
                        await resp.write(chunk)
                        byte_count += len(chunk)
                        state.streaming_started = True
                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError):
                    # Client disconnect or upstream mid-stream error — log partial
                    status = status if status and status < 400 else (status or 499)
                finally:
                    try:
                        await resp.write_eof()
                    except Exception:
                        pass
        finally:
            up.close()

        # Log (always, even on disconnect — needed for calibration)
        ensure_log_dir()
        append(RequestLog(
            ts=_now_iso(),
            request_id=request_id,
            model_in=state.inbound_model or "<none>",
            label=state.result.label,
            destination=dest_key,
            provider=dest.provider_name,
            model_out=dest.model,
            status=status,
            ms=ms,
            duration_ms=int((time.monotonic() - t0) * 1000),
            bytes=byte_count,
            token_count=state.result.inspect.token_count,
            tokens=state.result.inspect.token_breakdown,
            file_search_tokens=state.result.inspect.file_search_tokens,
            rtk_saved=state.rtk_saved,
            profile=profile.name,
            protocol=state.protocol,
            agent=state.agent,
            codex_retried=state.codex_retried,
        ))

        return resp


async def handle_messages(request: web.Request) -> web.StreamResponse:
    return await _proxy_flow(request, "anthropic")


async def handle_chat_completions(request: web.Request) -> web.StreamResponse:
    return await _proxy_flow(request, "openai-chat")


async def handle_responses(request: web.Request) -> web.StreamResponse:
    return await _proxy_flow(request, "openai-responses")


def _fallback_result(state: _RoutingState) -> ResolveResult:
    """Return a new resolve result for the pro fallback."""
    pro_dest = state.profile.destinations["pro"]
    return ResolveResult(
        destination="pro",
        model=pro_dest.model,
        label=state.result.label + "→fallback",
        inspect=state.result.inspect,
    )


async def handle_count_tokens(request: web.Request) -> web.Response:
    profile = request.app["profile"]
    settings = request.app["settings"]
    session: aiohttp.ClientSession = request.app["session"]

    if "anthropic" not in profile.protocols:
        raise _protocol_mismatch(request, "anthropic")
    providers: dict = request.app["providers"]["anthropic"]

    body = await request.json()
    headers = _filter_headers(dict(request.headers))

    # Same compression as /v1/messages: the client's context-window estimate
    # must match what actually gets sent upstream.
    if _rtk_enabled(request, profile):
        rtk.compress_body(body, "anthropic")

    # Image bridge here too, for the same reason: the token estimate must
    # reflect the transcriptions that /v1/messages would actually send.
    if settings.image_bridge:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        await _bridge_images(rid, session, body, "anthropic",
                             profile, providers, settings)

    # Resolve destination (same logic as messages)
    result = _resolve_for_request(body, profile, settings, "anthropic")
    dest = profile.destinations[result.destination]
    provider = providers[dest.provider_name]

    upstream_url = provider.base_url.rstrip("/") + request.path
    body["model"] = dest.model
    await _set_auth(headers, provider, os.environ)

    try:
        async with session.post(
            upstream_url, json=body, headers=headers,
            timeout=aiohttp.ClientTimeout(connect=10, total=30),
        ) as up:
            data = await up.json()
            return web.json_response(data, status=up.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise web.HTTPBadGateway(
            text=json.dumps({"error": {"message": f"upstream error: {exc}"}}),
            content_type="application/json",
        )


async def handle_models(request: web.Request) -> web.Response:
    settings = request.app["settings"]
    models = [
        {"id": settings.background_model, "object": "model"},
        {"id": "auto", "object": "model"},
        {"id": settings.think_model, "object": "model"},
    ]
    return web.json_response({"data": models, "object": "list"})


async def handle_root(request: web.Request) -> web.Response:
    return web.json_response({
        "name": "awerouter",
        "version": request.app["version"],
        "endpoints": [
            "POST /v1/messages",
            "POST /v1/messages/count_tokens",
            "POST /v1/chat/completions",
            "POST /v1/responses",
            "GET /v1/models",
        ],
    })


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _loopback_proxy_warning() -> "str | None":
    """Warn when shell proxy vars would hijack loopback traffic to awerouter.

    Clients honor http_proxy/https_proxy/all_proxy; without 127.0.0.1 in
    no_proxy, requests to awerouter get routed into the proxy — whose own
    127.0.0.1 is itself — so they fail to connect and come back as 502
    with an empty body.
    """
    has_proxy = any(
        os.environ.get(k) for k in
        ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")
    )
    if not has_proxy:
        return None
    no_proxy = (os.environ.get("no_proxy") or os.environ.get("NO_PROXY") or "").lower()
    if "127.0.0.1" in no_proxy or "localhost" in no_proxy:
        return None
    return (
        "warning: proxy env vars are set, but no_proxy does not exempt loopback\n"
        "  (clients will route awerouter traffic into the proxy and get empty 502s)\n"
        "  fix: export no_proxy=127.0.0.1,localhost NO_PROXY=127.0.0.1,localhost"
    )


def _flat_providers(providers_by_protocol: dict) -> dict:
    """Flatten grouped providers for the serve-start warnings: one entry per
    provider name (first group wins on name collisions — the warning names
    providers, config show shows the per-group detail)."""
    return {p.name: p for group in providers_by_protocol.values() for p in group.values()}


def create_app(providers: dict, profile, settings) -> web.Application:
    """providers is the profile's groups keyed by served protocol
    ({protocol: {provider_name: Provider}}); each handler picks its own group."""
    app = web.Application()
    app["providers"] = providers
    app["profile"] = profile
    app["settings"] = settings
    app["version"] = __version__

    session = aiohttp.ClientSession()
    app["session"] = session

    app.add_routes([
        web.get("/", handle_root),
        web.get("/v1/models", handle_models),
        web.post("/v1/messages", handle_messages),
        web.post("/v1/messages/count_tokens", handle_count_tokens),
        web.post("/v1/chat/completions", handle_chat_completions),
        web.post("/v1/responses", handle_responses),
        # Unversioned aliases: OpenAI-style clients whose base_url omits /v1
        # (or includes it) both work. Handlers forward the canonical upstream
        # path regardless of the inbound one.
        web.get("/models", handle_models),
        web.post("/chat/completions", handle_chat_completions),
        web.post("/responses", handle_responses),
    ])

    async def on_cleanup(app):
        await app["session"].close()

    app.on_cleanup.append(on_cleanup)
    return app


# ---------------------------------------------------------------------------
# Hot reload: routing.json / providers.json changes apply without a restart
# ---------------------------------------------------------------------------

# How often the watcher polls the config files' mtimes.
_RELOAD_POLL_S = 1.0


def _config_mtimes() -> tuple:
    mtimes = []
    for p in (routing_path(), providers_path()):
        try:
            mtimes.append(p.stat().st_mtime_ns)
        except OSError:  # missing (deleted mid-edit) counts as a change to None
            mtimes.append(None)
    return tuple(mtimes)


def _reload_config(app, profile_name: str) -> bool:
    """Swap a live app's profile/settings/providers for a freshly loaded copy.

    Prints why on refusal and returns False — the running config stays in
    effect until a loadable file shows up. In-flight requests keep whatever
    they read at their start; the swap only affects requests that begin
    after it.
    """
    try:
        new_providers, new_profile, new_settings = load_for_profile(profile_name)
    except SystemExit as exc:
        print(f"  config reload skipped (serving the previous config): {exc}")
        return False
    old_profile = app["profile"]
    auto_line = _resolve_auto_threshold(new_profile, new_settings)
    app["providers"] = new_providers
    app["profile"] = new_profile
    app["settings"] = new_settings
    if new_profile.port != old_profile.port:
        print(f"  note -> 'port' for this profile is now {new_profile.port or '(default)'} "
              "in routing.json; restart serve to rebind")
    flash, pro = new_profile.destinations["flash"], new_profile.destinations["pro"]
    print(f"  config reloaded -> flash={flash.provider_name}/{flash.model}  "
          f"pro={pro.provider_name}/{pro.model}  "
          f"L3>{new_profile.long_context_threshold:,}")
    if auto_line is not None:
        print(auto_line)
    return True


async def _watch_config(app, profile_name: str) -> None:
    """Poll config mtimes and reload on change.

    A failed reload announces itself once per file state (mid-save partial
    write, broken JSON) and retries when the file changes again.
    """
    last = _config_mtimes()
    while True:
        await asyncio.sleep(_RELOAD_POLL_S)
        now = _config_mtimes()
        if now == last:
            continue
        if _reload_config(app, profile_name):
            last = now


# ---------------------------------------------------------------------------
# Serve command (called from cli.py)
# ---------------------------------------------------------------------------


def _client_hint(protocol: str, display_host: str, port: int, settings) -> str:
    if protocol == "anthropic":
        return (
            "point Claude Code here:\n"
            f"  export ANTHROPIC_BASE_URL=http://{display_host}:{port}\n"
            f"  tier env: ANTHROPIC_MODEL=auto  "
            f"ANTHROPIC_DEFAULT_HAIKU_MODEL={settings.background_model}  "
            f"ANTHROPIC_DEFAULT_OPUS_MODEL={settings.think_model}"
        )
    base = (
        "point your OpenAI client here:\n"
        f"  export OPENAI_BASE_URL=http://{display_host}:{port}/v1\n"
        f"  (base_url with or without /v1 both work)\n"
    )
    if protocol == "openai-responses":
        return base + (
            '  codex: set base_url to the same URL in config.toml '
            '(wire_api = "responses")'
        )
    # openai-chat serves non-codex OpenAI-compatible agents (opencode etc.);
    # codex itself needs an openai-responses profile — documented in README.
    return base


def _client_hints(protocols, display_host: str, port: int, settings) -> str:
    """One hint block per served protocol: a multi-protocol profile serves
    every client style on the same port."""
    return "\n\n".join(_client_hint(p, display_host, port, settings) for p in protocols)


# How far past the default port an implicit serve scans before giving up.
_PORT_SCAN_SPAN = 100


def _fmt_setting_value(value) -> str:
    """One overrides-line item: strings bare, nested blocks as compact JSON."""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(", ", ": "))


def _overrides_line(overrides: dict) -> str:
    return "  ".join(f"{k}={_fmt_setting_value(v)}" for k, v in overrides.items())


def _resolve_auto_threshold(profile, settings) -> "str | None":
    """Materialize longContextThreshold: "auto" from this profile's own log.

    Runs once at serve start (before the socket opens, so no request can race
    it); the value stays fixed for the process lifetime. With too few samples
    the fallbackThreshold loaded by config.py stays in effect. Returns the
    banner line to print — the choice must be visible.
    """
    if not profile.threshold_auto:
        return None
    cfg = settings.long_context_auto
    picked = auto_threshold(profile.name, settings.search_result_discount, cfg)
    if picked is not None:
        threshold, samples = picked
        profile.long_context_threshold = threshold
        return (f"  L3 threshold -> auto: p{cfg.percentile} of {samples} L3 requests "
                f"(last {cfg.window_days}d) = {threshold:,}")
    return (f"  L3 threshold -> auto: fewer than {cfg.min_samples} L3 requests in "
            f"last {cfg.window_days}d — fallbackThreshold {cfg.fallback_threshold:,} in effect")


def _noauth_warning(providers: dict) -> "str | None":
    """Warn on no-auth providers pointing off-machine — almost always a
    forgotten 'auth' entry (LAN servers with no auth are the legit exception)."""
    offenders = sorted(
        p.name for p in providers.values()
        if not p.auth and not is_loopback_url(p.base_url)
    )
    if not offenders:
        return None
    return (
        "warning: no auth set for off-machine providers: " + ", ".join(offenders) + "\n"
        "  (cloud APIs need an 'auth' entry; ignore if these are unauthenticated internal servers)"
    )


def _codex_login_warning(providers: dict) -> "str | None":
    """Warn when configured Codex providers cannot load the local login."""
    offenders = sorted(
        p.name for p in providers.values()
        if p.auth == AUTH_SENTINEL
    )
    if not offenders:
        return None
    try:
        load_codex_login()
    except CodexAuthError as exc:
        return (
            "warning: invalid codex login for providers: " + ", ".join(offenders) + "\n"
            f"  ({exc})"
        )
    return None


def _claude_login_warning(providers: dict) -> "str | None":
    """Claude-login providers with no usable stored login — every request to
    them 503s with an 'awerouter login claude' hint until the login exists.
    Store check only: a present-but-stale token is fine (it refreshes on the
    first request), so this never touches the network."""
    offenders = sorted(
        p.name for p in providers.values()
        if p.auth == CLAUDE_SENTINEL
    )
    if not offenders:
        return None
    if claude_auth_path().exists():
        if login_status() is not None:
            return None
        return (
            "warning: invalid claude login for providers: " + ", ".join(offenders) + "\n"
            f"  ({claude_auth_path()} — re-run: awerouter login claude)"
        )
    return (
        "warning: no claude login for providers: " + ", ".join(offenders) + "\n"
        f"  ({claude_auth_path()} — run: awerouter login claude)"
    )


async def _serve(host: str, port: int, providers: dict, profile, settings,
                 port_explicit: bool = False, background: bool = False) -> None:
    auto_line = _resolve_auto_threshold(profile, settings)
    app = create_app(providers, profile, settings)
    runner = web.AppRunner(app)
    await runner.setup()

    async def _bind(p: int) -> web.TCPSite:
        site = web.TCPSite(runner, host=host, port=p)
        await site.start()
        return site

    site = None
    if port_explicit:
        # An explicitly chosen port (--port or the profile's port field) must
        # not silently move: clients hardcode it.
        try:
            site = await _bind(port)
        except OSError:
            await runner.cleanup()
            die(
                f"port {port} is already in use — another awerouter (or process) is holding it.\n"
                f"  stop it first, or launch with a different --port"
            )
    else:
        # Implicit default: take the first free port scanning up from it, so
        # concurrent instances get predictable sequential ports (20128, 20129,
        # ...) in start order instead of random ones.
        for candidate in range(port, port + _PORT_SCAN_SPAN):
            try:
                site = await _bind(candidate)
                if candidate != port:
                    print(f"  note         -> port {port} busy; using next free port {candidate}")
                break
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    await runner.cleanup()
                    die(f"cannot bind {host}:{candidate}: {exc}")
    if site is None:
        await runner.cleanup()
        die(f"no free port in {port}-{port + _PORT_SCAN_SPAN - 1}; pass --port explicitly")
    actual_port = site._server.sockets[0].getsockname()[1]
    print(f"awerouter listening on {host}:{actual_port}  [{profile.name}]")
    print(f"  protocol      -> {profile.protocol}")
    print("  hot reload    -> on (routing.json/providers.json changes apply without restart)")
    if profile.port is not None:
        print(f"  port          -> {profile.port} (from routing.json; --port overrides)")
    if profile.rtk:
        print(f"  rtk           -> on (tool-result compression)")
    if settings.image_bridge:
        bd = profile.destinations[settings.image_model]
        print(f"  image bridge  -> on ({bd.provider_name}/{bd.model} transcribes "
              f"history images to text)")
    print(f"  bg            -> {settings.background_model}  "
          f"think -> {settings.think_model}  "
          f"main -> {'auto' if settings.default_model == 'flash' else settings.default_model}")
    if settings.image_model != "pro" or settings.default_model != "flash":
        print(f"  image         -> {settings.image_model}  "
              f"default -> {settings.default_model}")
    tr = settings.tool_routing
    parts = [f"web→{tr.web_search or settings.web_search_model}",
             *(f"{k}→{v}" for k, v in (("edit", tr.edit),) if v)]
    print(f"  tool          -> {'  '.join(parts)}")
    if profile.settings_overrides:
        print(f"  overrides     -> {_overrides_line(profile.settings_overrides)}")
    print(f"  flash  -> {profile.destinations['flash'].provider_name}/{profile.destinations['flash'].model}")
    print(f"  pro    -> {profile.destinations['pro'].provider_name}/{profile.destinations['pro'].model}")
    if auto_line is not None:
        print(auto_line)
    else:
        print(f"  L3 threshold -> {profile.long_context_threshold}")
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    print()
    print(_client_hints(profile.protocols, display_host, actual_port, settings))
    update_hint = cached_update_hint()
    if update_hint:
        print()
        print(update_hint)
    warning = _loopback_proxy_warning()
    if warning:
        print()
        print(warning)
    flat = _flat_providers(providers)
    warning = _noauth_warning(flat)
    if warning:
        print()
        print(warning)
    warning = _codex_login_warning(flat)
    if warning:
        print()
        print(warning)
    warning = _claude_login_warning(flat)
    if warning:
        print()
        print(warning)
    try:
        runtime.register(profile.name, profile.protocol, actual_port, host, background)
    except OSError as exc:
        print(f"  warning -> cannot register this instance ({exc}); "
              "awerouter status/stop won't see it")
    watcher = asyncio.ensure_future(_watch_config(app, profile.name))
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGTERM", "SIGHUP"):  # graceful stop / lost terminal
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):  # Windows loops, non-main thread
            pass
    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        runtime.unregister()
        await runner.cleanup()
