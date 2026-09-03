"""Gateway mode tests: one port, every profile, model name picks the profile.

`awerouter serve all` serves all routing.json profiles on a single port.
Requests address a profile as '<profile>/auto|flash|pro'; bare tier names go
to defaultProfile (or the only profile). These tests build the gateway app
directly (create_gateway_app) the way _load_gateway_state does.
"""

import asyncio
import json
import os

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from awerouter import __version__
from awerouter.config import format_routing_display, load_providers, load_routing, validate_profiles
from awerouter.server import (
    _GatewayEntry,
    _gateway_client_hints,
    _load_gateway_state,
    _reload_gateway,
    create_gateway_app,
)
from awerouter.types import Destination, Provider, RoutingProfile, Settings

PROTOCOLS = ("anthropic", "openai-chat", "openai-responses")


def run(coro):
    asyncio.run(coro)


@pytest.fixture(autouse=True)
def _tmp_log(tmp_path, monkeypatch):
    monkeypatch.setenv("AWEROUTER_LOG_DIR", str(tmp_path / "logs"))
    os.environ.setdefault("STEPFUN_KEY", "flash-key")
    os.environ.setdefault("ANTHROPIC_KEY", "pro-key")


def _providers(port):
    """The same mock upstream registered under every protocol (the shape
    _load_gateway_state builds per profile)."""
    def group():
        return {
            "stepfun": Provider("stepfun", f"http://127.0.0.1:{port}", "${STEPFUN_KEY}"),
            "anthropic": Provider("anthropic", f"http://127.0.0.1:{port}", "${ANTHROPIC_KEY}", "x-api-key"),
        }
    return {p: group() for p in PROTOCOLS}


def _entry(name, protocols, flash_model, pro_model, threshold=32, settings=None,
           port=0):
    profile = RoutingProfile(
        name=name, protocols=protocols, long_context_threshold=threshold,
        destinations={
            "flash": Destination("stepfun", flash_model),
            "pro": Destination("anthropic", pro_model),
        },
        settings=settings or Settings(),
    )
    return _GatewayEntry(
        profile=profile, settings=profile.settings,
        providers={p: _providers(port)[p] for p in profile.protocols},
    )


def _glm_deep(port=0):
    return {
        "glm": _entry("glm", "anthropic", "glm-flash", "glm-pro", port=port),
        "deep": _entry("deep", "anthropic", "deep-flash", "deep-pro", port=port),
    }


def _mock_upstream(routes):
    """Start one mock upstream answering every path in routes with the JSON
    body's model echoed back. Returns the started TestServer."""
    async def up(request):
        body = await request.json()
        return web.json_response({"model": body["model"]})

    app = web.Application()
    for path in routes:
        app.router.add_post(path, up)
    return app


class TestGatewayModels:
    def test_v1_models_lists_every_profile(self):
        entries = {
            "step-glm": _entry("step-glm", "anthropic", "sf-flash", "glm-pro"),
            "step-codex": _entry("step-codex", "openai-responses", "sf-flash", "gpt-pro"),
        }
        async def t():
            async with TestClient(TestServer(create_gateway_app(entries, "step-glm"))) as c:
                r = await c.get("/v1/models")
                assert r.status == 200
                ids = [m["id"] for m in (await r.json())["data"]]
                # bare tiers of the default profile first, then per-profile tiers
                assert ids[:3] == ["flash", "auto", "pro"]
                assert "step-glm/auto" in ids and "step-glm/pro" in ids
                assert "step-codex/auto" in ids and "step-codex/flash" in ids
        run(t())

    def test_v1_models_without_default_lists_aliases_only(self):
        entries = {
            "a": _entry("a", "anthropic", "f", "p"),
            "b": _entry("b", "anthropic", "f", "p"),
        }
        async def t():
            async with TestClient(TestServer(create_gateway_app(entries, None))) as c:
                ids = [m["id"] for m in (await (await c.get("/v1/models")).json())["data"]]
                assert "auto" not in ids  # no default: bare names are not routable
                assert "a/auto" in ids and "b/auto" in ids
        run(t())

    def test_root_advertises_gateway_mode(self):
        entries = {"a": _entry("a", "anthropic", "f", "p")}
        async def t():
            async with TestClient(TestServer(create_gateway_app(entries, None))) as c:
                d = await (await c.get("/")).json()
                assert d["mode"] == "gateway"
                assert d["models"] == ["a"]
                assert d["version"] == __version__
        run(t())


class TestGatewayRouting:
    """The alias picks the profile; the tier maps onto that profile's own
    L2 labels, so forcing works even with customized tier names."""

    def test_alias_auto_runs_pipeline_short_goes_flash(self):
        async def t():
            up_server = TestServer(_mock_upstream(["/v1/messages"]))
            await up_server.start_server()
            try:
                entries = _glm_deep(up_server.port)
                async with TestClient(TestServer(create_gateway_app(entries, "glm"))) as c:
                    r = await c.post("/v1/messages", json={
                        "model": "deep/auto", "messages": [{"content": "short"}],
                    })
                    assert r.status == 200
                    assert (await r.json())["model"] == "deep-flash"
            finally:
                await up_server.close()
        run(t())

    def test_alias_auto_long_context_goes_pro(self):
        async def t():
            up_server = TestServer(_mock_upstream(["/v1/messages"]))
            await up_server.start_server()
            try:
                entries = _glm_deep(up_server.port)
                async with TestClient(TestServer(create_gateway_app(entries, "glm"))) as c:
                    r = await c.post("/v1/messages", json={
                        "model": "glm/auto", "messages": [{"content": "x" * 200}],
                    })
                    assert r.status == 200
                    assert (await r.json())["model"] == "glm-pro"
            finally:
                await up_server.close()
        run(t())

    def test_alias_pro_forces_pro_with_custom_labels(self):
        """thinkModel=opus-tier: '/pro' still forces the pro destination —
        the tier normalizes to the profile's own L2 label."""
        entries = {
            "glm": _entry("glm", "anthropic", "glm-flash", "glm-pro",
                          settings=Settings(background_model="haiku", think_model="opus-tier")),
        }
        async def t():
            up_server = TestServer(_mock_upstream(["/v1/messages"]))
            await up_server.start_server()
            try:
                for group in entries["glm"].providers.values():
                    for pname, p in group.items():
                        group[pname] = Provider(
                            pname, f"http://127.0.0.1:{up_server.port}", p.auth, p.auth_header)
                async with TestClient(TestServer(create_gateway_app(entries, "glm"))) as c:
                    r = await c.post("/v1/messages", json={
                        "model": "glm/pro", "messages": [{"content": "hi"}],
                    })
                    assert r.status == 200
                    assert (await r.json())["model"] == "glm-pro"
                    # the profile's own tier labels work as tiers too
                    r2 = await c.post("/v1/messages", json={
                        "model": "glm/haiku", "messages": [{"content": "hi"}],
                    })
                    assert (await r2.json())["model"] == "glm-flash"
            finally:
                await up_server.close()
        run(t())

    def test_bare_name_routes_to_default(self):
        async def t():
            up_server = TestServer(_mock_upstream(["/v1/messages"]))
            await up_server.start_server()
            try:
                entries = _glm_deep(up_server.port)
                async with TestClient(TestServer(create_gateway_app(entries, "deep"))) as c:
                    r = await c.post("/v1/messages", json={
                        "model": "pro", "messages": [{"content": "hi"}],  # bare think label
                    })
                    assert r.status == 200
                    assert (await r.json())["model"] == "deep-pro"
            finally:
                await up_server.close()
        run(t())

    def test_single_profile_is_the_implicit_default(self):
        entries = {"only": _entry("only", "anthropic", "of", "op")}
        async def t():
            async with TestClient(TestServer(create_gateway_app(entries, None))) as c:
                r = await c.post("/v1/messages", json={
                    "model": "auto", "messages": [{"content": "hi"}],
                })
                # dead upstream (port 0) -> 502 after fallback, but the bare
                # name itself resolved (a resolution failure would be a 400)
                assert r.status == 502
        run(t())

    def test_multi_protocol_profile_serves_each_endpoint(self):
        entries = {"mm": _entry("mm", ["anthropic", "openai-chat"], "mm-f", "mm-p")}
        async def t():
            up_server = TestServer(_mock_upstream(["/v1/messages", "/chat/completions"]))
            await up_server.start_server()
            try:
                for group in entries["mm"].providers.values():
                    for pname, p in group.items():
                        group[pname] = Provider(
                            pname, f"http://127.0.0.1:{up_server.port}", p.auth, p.auth_header)
                async with TestClient(TestServer(create_gateway_app(entries, "mm"))) as c:
                    r = await c.post("/v1/messages", json={
                        "model": "mm/pro", "messages": [{"content": "hi"}],
                    })
                    assert (await r.json())["model"] == "mm-p"
                    r2 = await c.post("/v1/chat/completions", json={
                        "model": "mm/pro", "messages": [{"role": "user", "content": "hi"}],
                    })
                    assert (await r2.json())["model"] == "mm-p"
            finally:
                await up_server.close()
        run(t())

    def test_log_records_the_alias_and_profile(self):
        async def t():
            up_server = TestServer(_mock_upstream(["/v1/messages"]))
            await up_server.start_server()
            try:
                entries = _glm_deep(up_server.port)
                async with TestClient(TestServer(create_gateway_app(entries, "glm"))) as c:
                    await c.post("/v1/messages", json={
                        "model": "deep/flash", "messages": [{"content": "hi"}],
                    })
            finally:
                await up_server.close()
        run(t())
        from awerouter.logging import tail
        e = tail(1)[0]
        assert e.profile == "deep"
        assert e.model_in == "deep/flash"  # the alias, not the rewritten tier
        assert e.model_out == "deep-flash"


class TestGatewayErrors:
    def _entries(self):
        return {
            "glm": _entry("glm", ["anthropic", "openai-chat"], "glm-flash", "glm-pro"),
            "codex": _entry("codex", "openai-responses", "cx-flash", "cx-pro"),
        }

    def test_unknown_profile_400_lists_available(self):
        async def t():
            async with TestClient(TestServer(create_gateway_app(self._entries(), "glm"))) as c:
                r = await c.post("/v1/messages", json={
                    "model": "nope/auto", "messages": [{"content": "hi"}],
                })
                assert r.status == 400
                msg = (await r.json())["error"]["message"]
                assert "unknown profile 'nope'" in msg
                assert "glm" in msg and "codex" in msg
        run(t())

    def test_protocol_mismatch_names_serving_profiles(self):
        async def t():
            async with TestClient(TestServer(create_gateway_app(self._entries(), "glm"))) as c:
                r = await c.post("/v1/messages", json={
                    "model": "codex/auto", "messages": [{"content": "hi"}],
                })
                assert r.status == 400
                msg = (await r.json())["error"]["message"]
                assert "speaks 'openai-responses'" in msg
                assert "glm" in msg  # the profile that DOES serve anthropic
        run(t())

    def test_bad_tier_400(self):
        async def t():
            async with TestClient(TestServer(create_gateway_app(self._entries(), "glm"))) as c:
                r = await c.post("/v1/messages", json={
                    "model": "glm/turbo", "messages": [{"content": "hi"}],
                })
                assert r.status == 400
                assert "tier" in (await r.json())["error"]["message"]
        run(t())

    def test_bare_name_without_default_400(self):
        entries = {
            "a": _entry("a", "anthropic", "f", "p"),
            "b": _entry("b", "anthropic", "f", "p"),
        }
        async def t():
            async with TestClient(TestServer(create_gateway_app(entries, None))) as c:
                r = await c.post("/v1/messages", json={
                    "model": "auto", "messages": [{"content": "hi"}],
                })
                assert r.status == 400
                assert "defaultProfile" in (await r.json())["error"]["message"]
        run(t())

    def test_default_profile_wrong_protocol_400(self):
        entries = {
            "glm": _entry("glm", "anthropic", "f", "p"),
            "cx": _entry("cx", "openai-responses", "f", "p"),
        }
        async def t():
            async with TestClient(TestServer(create_gateway_app(entries, "cx"))) as c:
                r = await c.post("/v1/messages", json={
                    "model": "auto", "messages": [{"content": "hi"}],
                })
                assert r.status == 400
                assert "default profile" in (await r.json())["error"]["message"]
        run(t())


class TestGatewayCountTokens:
    def test_count_tokens_resolves_via_alias(self):
        async def t():
            captured = {}

            async def up(request):
                body = await request.json()
                captured["model"] = body.get("model")
                return web.json_response({"input_tokens": 5})

            up_app = web.Application()
            up_app.router.add_post("/v1/messages/count_tokens", up)
            up_server = TestServer(up_app)
            await up_server.start_server()
            try:
                entries = {"glm": _entry("glm", "anthropic", "glm-flash", "glm-pro",
                                         port=up_server.port)}
                async with TestClient(TestServer(create_gateway_app(entries, None))) as c:
                    r = await c.post("/v1/messages/count_tokens", json={
                        "model": "glm/pro", "messages": [{"content": "hi"}],
                    })
                    assert r.status == 200
                    assert captured["model"] == "glm-pro"  # rewritten, not the alias
            finally:
                await up_server.close()
        run(t())


class TestGatewayLoadState:
    """_load_gateway_state reads routing.json into entries + default."""

    def _write(self, tmp_path, routing):
        (tmp_path / "providers.json").write_text(json.dumps({"anthropic": {
            "stepfun": {"base_url": "https://x", "auth": "${K}"},
            "anthropic": {"base_url": "https://y", "auth": "${K}"},
        }}))
        (tmp_path / "routing.json").write_text(json.dumps(routing))

    def _profile(self, threshold=8000):
        return {"protocol": "anthropic", "longContextThreshold": threshold,
                "destinations": {"flash": "stepfun,sf", "pro": "anthropic,op"}}

    def test_loads_all_profiles_and_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {
            "defaultProfile": "glm",
            "glm": self._profile(),
            "deep": self._profile(4000),
        })
        entries, default = _load_gateway_state()
        assert sorted(entries) == ["deep", "glm"]
        assert default == "glm"
        assert entries["deep"].profile.long_context_threshold == 4000
        assert "anthropic" in entries["glm"].providers
        assert "stepfun" in entries["glm"].providers["anthropic"]

    def test_single_profile_auto_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"glm": self._profile()})
        _, default = _load_gateway_state()
        assert default == "glm"

    def test_multiple_profiles_no_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"a": self._profile(), "b": self._profile()})
        _, default = _load_gateway_state()
        assert default is None

    def test_missing_default_dies(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"defaultProfile": "ghost", "glm": self._profile()})
        with pytest.raises(SystemExit, match="ghost"):
            _load_gateway_state()


class TestGatewayHotReload:
    def _write(self, tmp_path, profiles, default=None):
        (tmp_path / "providers.json").write_text(json.dumps({"anthropic": {
            "stepfun": {"base_url": "https://x", "auth": "${K}"},
            "anthropic": {"base_url": "https://y", "auth": "${K}"},
        }}))
        routing = {name: {"protocol": "anthropic", "longContextThreshold": t,
                          "destinations": {"flash": "stepfun,sf", "pro": "anthropic,op"}}
                   for name, t in profiles.items()}
        if default:
            routing["defaultProfile"] = default
        (tmp_path / "routing.json").write_text(json.dumps(routing))

    def _app(self):
        # _reload_gateway only swaps these two entries; a plain dict is the app
        # (same as the single-profile TestHotReload tests)
        return {"gateway": {"old": _entry("old", "anthropic", "f", "p")},
                "default_profile": None}

    def test_reload_swaps_profiles_and_default(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"glm": 8000, "deep": 4000}, default="glm")
        app = self._app()
        assert _reload_gateway(app) is True
        assert sorted(app["gateway"]) == ["deep", "glm"]
        assert app["default_profile"] == "glm"
        assert app["gateway"]["deep"].profile.long_context_threshold == 4000
        assert "config reloaded -> 2 profile(s)" in capsys.readouterr().out

    def test_reload_announces_added_and_removed(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"glm": 8000})
        app = self._app()
        assert _reload_gateway(app) is True
        self._write(tmp_path, {"deep": 4000}, default="deep")
        assert _reload_gateway(app) is True
        out = capsys.readouterr().out
        assert "profiles added   -> deep" in out
        assert "profiles removed -> glm" in out
        assert app["default_profile"] == "deep"

    def test_invalid_config_keeps_serving_previous(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"glm": 8000})
        app = self._app()
        assert _reload_gateway(app) is True
        old = app["gateway"]
        (tmp_path / "routing.json").write_text("{ broken")
        assert _reload_gateway(app) is False
        assert app["gateway"] is old
        assert "reload skipped" in capsys.readouterr().out

    def test_empty_config_keeps_serving_previous(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"glm": 8000})
        app = self._app()
        assert _reload_gateway(app) is True
        old = app["gateway"]
        (tmp_path / "routing.json").write_text(json.dumps({"settings": {}}))
        assert _reload_gateway(app) is False
        assert app["gateway"] is old
        assert "no profiles" in capsys.readouterr().out


class TestDefaultProfileConfig:
    """routing.json's top-level defaultProfile key (config.py parsing)."""

    def _write(self, tmp_path, routing):
        (tmp_path / "providers.json").write_text(json.dumps({"anthropic": {
            "p": {"base_url": "https://x", "auth": "${K}"},
        }}))
        (tmp_path / "routing.json").write_text(json.dumps(routing))

    def _profile(self):
        return {"protocol": "anthropic", "longContextThreshold": 1,
                "destinations": {"flash": "p,m", "pro": "p,m"}}

    def test_parsed_onto_global_settings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"defaultProfile": "cc-1", "cc-1": self._profile()})
        settings, profiles = load_routing()
        assert settings.default_profile == "cc-1"
        # per-profile copies do not carry it (it is not a routing knob)
        assert profiles["cc-1"].settings.default_profile is None

    def test_unknown_name_dies(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"defaultProfile": "ghost", "cc-1": self._profile()})
        with pytest.raises(SystemExit, match="defaultProfile 'ghost'"):
            load_routing()

    def test_non_string_dies(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"defaultProfile": 42, "cc-1": self._profile()})
        with pytest.raises(SystemExit, match="defaultProfile"):
            load_routing()

    def test_profile_body_with_key_dies_as_unknown(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        body = dict(self._profile(), defaultProfile="cc-1")
        self._write(tmp_path, {"cc-1": body})
        with pytest.raises(SystemExit, match="unknown key"):
            load_routing()

    def test_config_show_displays_it(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWEROUTER_CONFIG_DIR", str(tmp_path))
        self._write(tmp_path, {"defaultProfile": "cc-1", "cc-1": self._profile()})
        validate_profiles(load_providers(), load_routing()[1])
        settings, profiles = load_routing()
        assert '"defaultProfile": "cc-1"' in format_routing_display(settings, profiles)


class TestGatewayClientHints:
    def test_with_default_includes_tier_env(self):
        entries = {"glm": _entry("glm", "anthropic", "f", "p")}
        hints = _gateway_client_hints(entries, "glm", "127.0.0.1", 20128)
        assert "ANTHROPIC_BASE_URL=http://127.0.0.1:20128" in hints
        assert "bare names route to 'glm'" in hints
        assert "glm/auto" in hints

    def test_without_default_omits_tier_env(self):
        entries = {
            "a": _entry("a", "anthropic", "f", "p"),
            "b": _entry("b", "openai-chat", "f", "p"),
        }
        hints = _gateway_client_hints(entries, None, "127.0.0.1", 20128)
        assert "ANTHROPIC_MODEL" not in hints  # bare names 400: no tier env lies
        assert "bare names are rejected" in hints
