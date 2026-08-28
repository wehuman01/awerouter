"""Codex subscription account (local CLI login) as a provider auth source.

A providers.json entry with "auth": "codex" rides the local Codex CLI login
instead of a static API key, so the subscription's own models mix into normal
flash/pro routing next to key-based providers. Verified-minimal wire contract
(same one awewarm's native transport probes with):

  POST {base_url}/responses            (Responses protocol, openai-responses group)
  Authorization: Bearer <access_token> (tokens.access_token)
  chatgpt-account-id: <account_id>     (tokens.account_id)
  OpenAI-Beta: responses=experimental
  originator: codex_cli_rs

Read-only by design: OpenAI refresh tokens are single-use and rotating, so
refreshing here would invalidate the local CLI's login. The CLI keeps sole
ownership of refresh; the access token lives ~10 days and is re-read from
disk on every forwarded request (and once more on an upstream 401).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Sentinel providers.json auth value selecting the local Codex CLI login.
AUTH_SENTINEL = "codex"

# Headers the ChatGPT Codex backend requires beyond the bearer token.
CODEX_HEADERS = {
    "OpenAI-Beta": "responses=experimental",
    "originator": "codex_cli_rs",
}


class CodexAuthError(Exception):
    """No usable local Codex login: auth.json missing or malformed."""


def auth_json_path() -> Path:
    home = os.environ.get("CODEX_HOME") or "~/.codex"
    return Path(home).expanduser() / "auth.json"


def load_codex_login() -> tuple[str, str]:
    """(access_token, account_id) from the local Codex CLI login."""
    path = auth_json_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CodexAuthError(f"codex login not found: {path} — run: codex login") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexAuthError(f"cannot read codex login {path}: {exc}") from None
    if not isinstance(payload, dict):
        raise CodexAuthError(f"codex login {path} is not a JSON object")
    # codex CLI writes {"tokens": {...}}; a flat block is accepted too.
    tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else payload
    access_token = tokens.get("access_token")
    account_id = tokens.get("account_id")
    if not isinstance(access_token, str) or not access_token:
        raise CodexAuthError(f"no access_token in {path} — run: codex login")
    if not isinstance(account_id, str) or not account_id:
        raise CodexAuthError(f"no account_id in {path} — re-login: codex logout && codex login")
    return access_token, account_id


def apply_codex_auth(headers: dict) -> None:
    """Write the full codex auth header set from the local login."""
    access_token, account_id = load_codex_login()
    headers["authorization"] = f"Bearer {access_token}"
    headers["chatgpt-account-id"] = account_id
    headers.update(CODEX_HEADERS)
