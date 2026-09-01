<div align="center">
  <img src="logo/logo.webp" alt="awerouter" width="860">
  <h1>awerouter: Smart LLM Router <a href="https://github.com/Webioinfo01/aweskill"><img src="https://raw.githubusercontent.com/Webioinfo01/aweskill/main/logo/aweskill-badge2.svg" alt="aweskill companion"></a></h1>
  <p><strong>Route cheap/fast tasks to Flash, hard decisions to Pro.</strong></p>
  <p>Transparent same-protocol proxy that routes coding-agent requests by structural signals — no keyword guessing, no LLM classifier. Speaks Anthropic Messages, OpenAI Chat Completions, and OpenAI Responses.</p>
  <p>
    <strong>English</strong> ·
    <a href="./README_cn.md">简体中文</a>
  </p>
  <p>
    <a href="https://ko-fi.com/mugpeng"><img src="https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
  </p>
  <p>
    <img src="https://img.shields.io/pypi/v/awerouter?style=flat-square&color=7C3AED" alt="Version">
    <img src="https://img.shields.io/badge/python-%E2%89%A53.9-0EA5E9?style=flat-square" alt="Python">
    <img src="https://img.shields.io/badge/license-MPL--2.0-22C55E?style=flat-square" alt="License">
  </p>
  <p>
    <img src="https://img.shields.io/badge/status-alpha-c96a3d?style=flat-square" alt="Status">
    <img src="https://img.shields.io/badge/install-pip-22C55E?style=flat-square" alt="pip">
    <img src="https://img.shields.io/badge/platform-terminal-334155?style=flat-square" alt="Platform">
    <img src="https://img.shields.io/pypi/dm/awerouter?style=flat-square" alt="Downloads">
    <img src="https://img.shields.io/github/stars/mugpeng/awerouter?style=flat-square" alt="Stars">
  </p>
</div>

> Transparent proxy that splits coding-agent traffic across providers by cost and capability. Same-protocol passthrough — no translation. Optional per-profile tool-result compression (RTK, off by default).

## Support Tools

awerouter works best alongside two companion tools:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI skill package manager for AI agents. Installs the awerouter skill so your agent can manage routing in natural language.
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Agent profile switcher. Launches Claude Code, Codex, or OpenCode sessions with a profile that points `BASE_URL` at the awerouter daemon.

aweskill lets the agent **manage** routing by operating skills; aweswitch lets you **launch** sessions through it. Configure awerouter once, then start any agent against it with `aweswitch <profile>`.

## Install & Usage

### Let AI agent install and configure

If you are working in Claude Code, Codex, Cursor, or another coding agent, tell it:

```text
Read https://github.com/mugpeng/awerouter/blob/main/README.ai.md and follow it to install and configure awerouter.
```

The agent will install the CLI, init config, help you add profiles, and install the awerouter skill via [aweskill](https://aweskill.webioinfo.top/) for ongoing routing management.

**After setup, you can tell the agent things like:**

> "Add a stepfun flash provider and a pro profile."
> "List my awerouter profiles."
> "Tune longContextThreshold from my usage."
> "Explain my usage savings."

The agent can run read-only commands (`list`, `config show`, `usage stats`, `usage calibrate`, `usage savings`) and edit config directly, but it will **not** run `awerouter serve` (long-lived daemon), `awerouter add` (interactive wizard), `awerouter restore` (overwrites config), `awerouter usage clean` (deletes logs), or `awerouter self-update` (upgrades the installation). To start the daemon, run it in your own terminal:

```bash
awerouter serve cc-router-1
```

#### awerouter skill

Install the [awerouter skill](https://github.com/mugpeng/awerouter/blob/main/resources/skills/awerouter/SKILL.md) via [aweskill](https://aweskill.webioinfo.top/) to let AI agents manage routing with natural language:

- List, inspect, add, and edit routing profiles
- Edit `providers.json` (endpoints/auth) and `routing.json` (strategy) separately
- Read `usage stats` / `usage calibrate` / `usage savings` and suggest threshold changes
- Guide environment-variable setup for `${ENV_VAR}` auth references

After install, you can tell the agent things like "Add a GLM provider for the openai-chat group", "Raise longContextThreshold to 12000", or "Show me which provider handles my web_search traffic". The agent reads the config, makes changes, and verifies with `awerouter config show` / `awerouter list`.

#### Launch through aweswitch

Once awerouter is configured, launch any agent through it by pointing an aweswitch profile at the daemon.

**Example: launch OpenCode through awerouter**

Start the daemon with an openai-chat profile in one terminal:

```bash
awerouter serve oc-router-1
```

Add an aweswitch OpenCode profile pointing at it:

```json
{
  "profiles": {
    "opencode": {
      "oc-awerouter": {
        "env": {
          "OPENCODE_BASE_URL": "http://127.0.0.1:20128/v1",
          "OPENCODE_API_KEY": "sk-any-non-empty-value",
          "OPENCODE_NAME": "awerouter",
          "OPENCODE_MODEL": "auto"
        }
      }
    }
  }
}
```

```bash
aweswitch oc-awerouter
```

With `OPENCODE_MODEL` set to `auto`, awerouter routes each request by structural signals — the upstream provider receives the actual model id from `routing.json` destinations, not `auto`. Claude Code works the same way via an `anthropic` profile (`ANTHROPIC_MODEL=auto`).

### Manual install and usage

Install from PyPI:

```bash
pip install awerouter
```

Quick Start:

```bash
# 1. Init config (creates ~/.config/awerouter/{providers,routing}.json)
awerouter init                # or pick a bundled combo: awerouter init step-glm / glm-codex / step-glm-mm (see "Common setup templates")

# 2. Interactively add a profile (writes both files, references stay consistent)
awerouter add
#    or edit by hand: providers.json for keys (${ENV_VAR}), routing.json for flash/pro

# 3. Start the daemon (profile name optional when only one exists)
awerouter serve [cc-router-1]     # shorthand: awerouter cc-router-1

# 4. Point CC at it — the serve banner prints both lines below
export ANTHROPIC_BASE_URL=http://127.0.0.1:20128
# aweswitch profile env: ANTHROPIC_MODEL=auto, _HAIKU_=flash, _OPUS_=pro
```

The bundled template source is [`src/awerouter/resources/templates/`](src/awerouter/resources/templates/); `awerouter init <template>` generates its matching files in your configuration directory. Already have a config? `awerouter init <template> --merge` adds the template's missing providers, profiles, and settings to it — existing entries are never overwritten, profile id collisions are skipped, and newly-set `imageModel`/`defaultModel` print a warning since they re-route every profile.

## Config

Two files in `~/.config/awerouter/` (override with `AWEROUTER_CONFIG_DIR`):

**providers.json** — endpoints + keys, grouped by wire protocol (redacted in `config show`):

```json
{
  "anthropic": {
    "stepfun":   { "base_url": "https://api.stepfun.com/step_plan", "auth": "${STEPFUN_AUTH_TOKEN}" },
    "anthropic": { "base_url": "https://api.anthropic.com",          "auth": "${ANTHROPIC_KEY}" }
  },
  "openai-chat": {
    "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1", "auth": "${STEPFUN_AUTH_TOKEN}" }
  },
  "openai-responses": {
    "openai": { "base_url": "https://api.openai.com/v1", "auth": "${OPENAI_API_KEY}" }
  }
}
```

Three protocols are supported. `base_url` uses each native client's convention — copy it verbatim from your client config; awerouter appends the endpoint path the same way the native client would:

| Protocol id         | `base_url` style | Endpoint |
|---------------------|------------------|----------|
| `anthropic`         | `ANTHROPIC_BASE_URL` (no `/v1`) | `base_url + /v1/messages` |
| `openai-chat`       | `OPENAI_BASE_URL` (includes version segment) | `base_url + /chat/completions` |
| `openai-responses`  | `OPENAI_BASE_URL` (includes version segment) | `base_url + /responses` |

The same provider often uses a different path per protocol — GLM for instance: `https://open.bigmodel.cn/api/anthropic` for Claude-protocol clients but `https://open.bigmodel.cn/api/coding/paas/v4` for chat completions and `https://open.bigmodel.cn/api/v1` for responses. That's why each protocol group carries its own `base_url` — and why a multi-protocol profile lists the provider in each group it serves.

The auth header is **auto-detected from `base_url`**: `anthropic.com` → `x-api-key` (bare token); everyone else → `Authorization` (auto-prefixes `Bearer `). No `auth_header` field needed unless the heuristic is wrong.

### Local models (no auth)

Local model servers don't need a key — just omit `auth` and the request goes upstream with no auth header at all:

```json
{
  "anthropic": {
    "ollama":    { "base_url": "http://127.0.0.1:11434" },
    "anthropic": { "base_url": "https://api.anthropic.com", "auth": "${ANTHROPIC_KEY}" }
  },
  "openai-chat": {
    "ollama": { "base_url": "http://127.0.0.1:11434/v1" }
  }
}
```

Works with any OpenAI-compatible server (Ollama, LM Studio, llama.cpp, vLLM) under `openai-chat`; Ollama ≥ 0.14 also speaks the Anthropic protocol, so it can sit in the `anthropic` group next to Claude Code. Note the path convention: `openai-chat` base_urls carry the `/v1` segment, `anthropic` ones don't — same as their cloud counterparts above.

Local and cloud mix freely in one profile — cheap drafting on local, hard calls on cloud:

```json
"destinations": {
  "flash": "ollama,qwen3-coder:30b",
  "pro":   "anthropic,claude-opus-5"
}
```

End to end with Ollama, flash=local / pro=cloud:

```bash
ollama pull qwen3-coder:30b      # local server listens on 127.0.0.1:11434 by default
awerouter serve cc-router-1
export ANTHROPIC_BASE_URL=http://127.0.0.1:20128
```

Default ports for the common local servers (all `openai-chat`, all no-auth): LM Studio `http://127.0.0.1:1234/v1`, llama.cpp `http://127.0.0.1:8080/v1`, vLLM `http://127.0.0.1:8000/v1`.

If the local server is down, the flash→pro fallback kicks in on connection errors and requests transparently go to the cloud — local-first with a cloud safety net, no extra config.

Guard against a forgotten key: a provider with no `auth` whose `base_url` is **not** on localhost gets a warning at serve start (`awerouter add` asks for confirmation in the same case). LAN servers without auth are legitimate — the warning is informational, not fatal.

### Codex account (subscription login)

`"auth": "codex"` in the `openai-responses` group rides the local Codex CLI login (`$CODEX_HOME/auth.json`, default `~/.codex/auth.json`) instead of an API key — the subscription's own models mix into flash/pro routing next to key-based providers:

```json
"openai-responses": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1", "auth": "${STEPFUN_AUTH_TOKEN}" },
  "codex":   { "base_url": "https://chatgpt.com/backend-api/codex", "auth": "codex" }
}
```

```json
"destinations": {
  "flash": "stepfun,step-router-v1",
  "pro":   "codex,gpt-5.6-luna"
}
```

Any Responses-speaking client (Codex itself, or any agent with a configurable OpenAI Responses base URL) points at awerouter with a dummy key; the real `Authorization: Bearer <access_token>` plus `chatgpt-account-id` headers are injected per request. A few body fields are normalized for the backend's quirks: `store` is forced to `false` (zero-data-retention, `store: true` is rejected), `max_output_tokens` is dropped (rejected), and since the backend has no non-streaming mode a non-streaming request goes upstream as SSE and comes back buffered into a single JSON response (output items rebuilt from the stream) — both client styles just work.

How it behaves:

- **Read-only login, no refresh.** OpenAI refresh tokens are single-use and rotating; refreshing here would invalidate the local CLI's login, so the CLI keeps sole ownership of refresh. awerouter re-reads `auth.json` on every request, and once more on an upstream 401 (the CLI usually refreshed it). A 401 that survives the re-read means the login itself is expired: flash requests then fall back to a keyed pro destination — one printed line per fallback, and a `401-retry` marker in `usage log` — surfacing the 401 only when pro rides the same codex login. The access token lives ~10 days — keep using `codex` (or awewarm) so the login stays fresh.
- **Proxy-aware.** codex providers honor `https_proxy`/`all_proxy` (the same vars the Codex CLI honors) — chatgpt.com often needs the shell proxy to be reachable. Other providers always connect directly.
- **Model names drift.** `gpt-5-codex`/`gpt-5.1-codex` are already rejected by the backend with a 400; the current name is whatever the CLI uses (`gpt-5.6-luna` at the time of writing). The model comes from your destination entry, so a rename is a one-line routing.json edit.
- **No login yet?** A missing/invalid `auth.json` turns requests into a 503 with a `run: codex login` hint, and serve prints a warning at startup. Deliberately no fallback there, unlike an expired token mid-session: a missing login is a config error best fixed immediately, and silently serving it from a paid pro would hide both the error and the bill.

The sentinel only loads in the `openai-responses` group — the ChatGPT Codex backend speaks the Responses protocol, so it can't sit in `anthropic`/`openai-chat` profiles.

### Claude account (subscription login)

`"auth": "claude"` in the `anthropic` group routes through a Claude Pro/Max subscription login that awerouter itself owns — no local Claude Code CLI login is needed or used (`awerouter login claude` runs the same PKCE device flow the CLI uses; tokens live in `~/.config/awerouter/claude-auth.json`, mode 0600). The subscription's own models mix into flash/pro routing next to key-based providers:

```json
"anthropic": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan", "auth": "${STEPFUN_AUTH_TOKEN}" },
  "claude":  { "base_url": "https://api.anthropic.com", "auth": "claude" }
}
```

```json
"destinations": {
  "flash": "stepfun,step-router-v1",
  "pro":   "claude,claude-opus-4-5"
}
```

```bash
awerouter login claude    # opens the browser; paste the code shown on the callback page
awerouter logout claude   # removes the stored login
```

Point any Anthropic-protocol client at awerouter with a dummy key (Claude Code via `ANTHROPIC_BASE_URL` — the CLI's own login is never touched; each OAuth login is an independent session). The real `Authorization: Bearer <access_token>` plus the OAuth-required `anthropic-beta: oauth-2025-04-20` flag are injected per request; no body normalization is needed. How it behaves:

- **awerouter owns refresh.** The inverse of codex's read-only design: this login belongs to awerouter, so it refreshes — access tokens are short-lived (~hours) and renewed with the rotating refresh token, the new one persisted atomically before the request proceeds. An in-process lock plus a re-read under it keep concurrent requests from racing the refresh; a second awerouter process winning the race is recovered the same way (refresh rejected + file changed underneath → the winner's token is used).
- **401 handling mirrors codex.** An upstream 401 forces one refresh and retries the same destination; a 401 that survives means the login is dead — flash requests fall back to a keyed pro destination (one printed line per fallback, `401-retry` marker in `usage log`), surfacing the 401 only when pro rides the same claude login. A missing login is a 503 with a `run: awerouter login claude` hint and a serve-start warning — same deliberate no-fallback reasoning as codex.
- **Proxy-aware** like codex providers (`https_proxy`/`all_proxy`) — api.anthropic.com and platform.claude.com often need the shell proxy.
- **Wire contract drifts; ToS caveat.** The endpoints (client id, `platform.claude.com` authorize/token, with legacy `console.anthropic.com` as a 404/405 fallback) and the header set are the reverse-engineered public contract shared by every community client — they can break without notice. And per Anthropic's 2026 policy, third-party use of subscription OAuth tokens is ToS-restricted: this rides your own subscription, at your own risk.

The sentinel only loads in the `anthropic` group — the subscription backend speaks the Messages protocol.

### Common setup templates

`awerouter init` takes an optional bundled template name and generates a matching `providers.json` + `routing.json` pair in one shot (no name: `default`). Three ready-made combos ship out of the box; hand-copying any snippet below into your own config works just as well. Keys are `${ENV_VAR}` placeholders — a missing env var dies at startup with a clear message. To fold a template into an existing config instead, append `--merge`: it fills in only what is missing and never touches what you already have.

**step-glm** — key-only Chinese two-tier combo: flash on StepFun step_plan, pro on the GLM coding plan. For agents speaking the openai-chat protocol:

```json
"openai-chat": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1",        "auth": "${STEPFUN_AUTH_TOKEN}" },
  "glm":     { "base_url": "https://open.bigmodel.cn/api/coding/paas/v4", "auth": "${GLM_API_KEY}" }
}
```

```json
"destinations": {
  "flash": "stepfun,step-3.7-flash",
  "pro":   "glm,glm-5.3"
}
```

```bash
awerouter init step-glm      # needs STEPFUN_AUTH_TOKEN and GLM_API_KEY
```

**glm-codex** — the GLM coding plan soaks up flash traffic, a ChatGPT subscription (`"auth": "codex"`, see above) handles pro:

```json
"openai-responses": {
  "glm":   { "base_url": "https://open.bigmodel.cn/api/v1",       "auth": "${GLM_API_KEY}" },
  "codex": { "base_url": "https://chatgpt.com/backend-api/codex", "auth": "codex" }
}
```

```json
"destinations": {
  "flash": "glm,glm-5.3-flash",
  "pro":   "codex,gpt-5.6-terra"
}
```

```bash
awerouter init glm-codex     # needs GLM_API_KEY, plus a ChatGPT subscription via codex login
```

**step-glm-mm** — the multimodal sidekick, no smart split: a non-multimodal flagship (GLM 5.3 on the coding plan) does all the work, and only image-bearing requests go to a multimodal flash (StepFun step-3.7-flash). Same vendors as step-glm; the settings do the inverting. Dual-protocol (`["anthropic", "openai-chat"]`): one serve instance takes Claude Code *and* openai-chat agents on the same port — each protocol rides its own provider entry:

```json
"anthropic": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan",      "auth": "${STEPFUN_AUTH_TOKEN}" },
  "glm":     { "base_url": "https://open.bigmodel.cn/api/anthropic", "auth": "${GLM_API_KEY}" }
},
"openai-chat": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1",        "auth": "${STEPFUN_AUTH_TOKEN}" },
  "glm":     { "base_url": "https://open.bigmodel.cn/api/coding/paas/v4", "auth": "${GLM_API_KEY}" }
}
```

```json
"settings": {
  "imageModel": "flash",
  "defaultModel": "pro"
}
```

```json
"cc-router-1": {
  "protocol": ["anthropic", "openai-chat"],
  "destinations": {
    "flash": "stepfun,step-3.7-flash",
    "pro":   "glm,glm-5.3"
  }
}
```

```bash
awerouter init step-glm-mm        # needs STEPFUN_AUTH_TOKEN and GLM_API_KEY
# Claude Code:    export ANTHROPIC_BASE_URL=http://127.0.0.1:20128        (no /v1)
# openai-chat:    export OPENAI_BASE_URL=http://127.0.0.1:20128/v1       (with /v1)
```

`imageModel: flash` moves the image guard to the multimodal model (it outranks tier labels and long context — a request pro cannot see must never reach pro); `defaultModel: pro` flips the cost-first fall-through, so everything text goes to the flagship. Background-tier tasks still ride flash. Prefer a single vendor? Point flash at GLM's own multimodal `glm-5.3-flash` (`https://open.bigmodel.cn/api/v1`) instead of StepFun — one line in each protocol group.

Backend model names drift (see the Codex account section) — renaming is a one-line change in routing.json.

**routing.json** — strategy, no secrets (safe to commit):

```json
{
  "settings": {
    "backgroundModel": "flash",
    "thinkModel": "pro",
    "toolRouting": {
      "webSearch": "pro",
      "edit": "pro"
    },
    "longContextAuto": {
      "percentile": 95,
      "windowDays": 7,
      "minSamples": 50,
      "fallbackThreshold": 8000
    }
  },
  "cc-router-1": {
    "protocol": "anthropic",
    "port": 20128,
    "longContextThreshold": 8000,
    "destinations": {
      "flash": "stepfun,step-3.7-flash",
      "pro":   "anthropic,claude-opus-5"
    }
  },
  "cc-pro-first": {
    "protocol": "anthropic",
    "longContextThreshold": 8000,
    "destinations": {
      "flash": "stepfun,step-3.7-flash",
      "pro":   "anthropic,claude-opus-5"
    },
    "defaultModel": "pro"
  }
}
```

`settings` is optional (defaults: `flash`/`pro`). It maps the model ids CC sends for the background (Haiku) and think (Opus) tiers; every tool-keyed routing rule (L1 `webSearch` included) lives in `settings.toolRouting` — the legacy top-level `webSearchModel` still works as a fallback. `imageModel` re-aims the image guard (default `pro`; `flash` when pro is a non-multimodal flagship — see the step-glm-mm template) and `defaultModel` flips the cost-first fall-through (default `flash`; `pro` for pro-first profiles). The main loop uses `auto` — routed by difficulty by L3. Set these in your aweswitch profile: `ANTHROPIC_DEFAULT_HAIKU_MODEL=flash`, `ANTHROPIC_MODEL=auto`, `ANTHROPIC_DEFAULT_OPUS_MODEL=pro`.

Every settings key can also be written **directly in a profile body**, flat next to `protocol`/`destinations` (`cc-pro-first` above flips only `defaultModel`). It then applies to that profile alone; missing keys — and, inside `toolRouting`/`longContextAuto`, missing fields — inherit from the global `settings` block, so each profile re-tunes exactly what differs. `config show <profile>` prints the profile's effective values with its override keys in the entry, and the serve banner lists them on an `overrides -> ...` line.

Settings keys, their defaults, and what each one steers (all of them settable globally and per profile):

| Key | Values | Default | Controls |
|-----|--------|---------|----------|
| `backgroundModel` | model id (e.g. `flash`, `c1/flash`) | `flash` | L2: requests carrying this tier label route to flash |
| `thinkModel` | model id | `pro` | L2: requests carrying this tier label route to pro |
| `webSearchModel` | `flash` / `pro` | `pro` | L1: destination for requests declaring `web_search` (legacy — `toolRouting.webSearch` wins when set) |
| `imageModel` | `flash` / `pro` | `pro` | L1: destination for image-bearing requests (the capability guard — outranks tiers and length) |
| `defaultModel` | `flash` / `pro` | `flash` | fall-through destination when no layer matches |
| `searchResultDiscount` | number 0–1 | `0.3` | L3: weight of file-search (Grep/Glob/LS) result tokens; `1` = off |
| `toolRouting.webSearch` | `flash` / `pro` / `null` | `null` | overrides `webSearchModel` for the web_search guard |
| `toolRouting.edit` | `flash` / `pro` / `null` | `pro` | L4: destination for the turn after code changed; `null` disables the checkpoint |
| `longContextAuto.percentile` | 1–99 | `95` | which percentile of the L3 distribution becomes the `"auto"` threshold |
| `longContextAuto.windowDays` | ≥ 1 | `7` | trailing window for auto calibration |
| `longContextAuto.minSamples` | ≥ 1 | `50` | below this many L3 samples, the fallback applies |
| `longContextAuto.fallbackThreshold` | ≥ 0 | `8000` | threshold until enough samples exist (backs `"auto"` before serve resolves it) |

`backgroundModel`/`thinkModel` take free-form model ids (whatever the client actually sends for those tiers), not `flash`/`pro`. Unknown keys — in `settings` or in a profile body — die at load naming the offender, so a typo never silently inherits the global value.

`longContextThreshold` is an integer, or `"auto"` to calibrate it from this profile's own traffic: at every `serve` start, awerouter takes the `percentile` of the profile's L3 effective-token distribution over the trailing `windowDays` as the threshold. With fewer than `minSamples` L3 requests in the window (fresh profile, quiet week) the `fallbackThreshold` applies instead. All four knobs live in `settings.longContextAuto` and are optional — the banner always prints what was picked and why. Note the percentile sets the flash/pro *split*, not flash's capability ceiling: if your flash model degrades on very long contexts, keep a manual threshold.

Keys reference `${ENV_VAR}` syntax. Missing env vars die with a clear message at startup.

> **Profile-based routing:** `routing.json` groups configs under profile ids (like aweswitch). `awerouter serve <profile>` starts one; with a single profile it auto-selects. `protocol` maps the profile to a providers.json group and decides which endpoint it serves — the serve banner prints the matching client env (`ANTHROPIC_BASE_URL` for Claude Code, `OPENAI_BASE_URL` / Codex `wire_api` for the openai protocols). It accepts a single id or a list: `"protocol": ["anthropic", "openai-chat"]` serves both wire protocols on one port — clients pick by endpoint path (`/v1/messages` vs `/v1/chat/completions`), each protocol forwards through its own provider group, and every destination provider must exist in each served group (per-protocol `base_url`s). Note: openai clients are single-model, so L2 tier labels effectively never fire for them — openai traffic routes by L1 + L3 with a flash default.

> **Ports:** the optional `port` field pins a profile's listen port (`awerouter list` shows it); precedence: `--port` flag > profile `port` > 20128 default. An explicitly chosen port that is already in use fails loudly — clients hardcode it, it must not silently move. Without one, serve takes the first free port scanning up from 20128: the first instance gets 20128, the next 20129, and so on — the assignment follows start order, not the profile. For the one-instance-at-a-time swap workflow, leave profiles portless and point clients at 20128.

## How It Routes

First-match-wins pipeline, evaluated per request:

| Layer | Signal | Decision |
|-------|--------|----------|
| L1 Capability | `web_search` tool in body; image content present | `toolRouting.webSearch` (default **pro**; legacy `webSearchModel` still works); `settings.imageModel` (default **pro**) |
| L2 Tier label | `model == c1/flash` or `c1/think` | flash / pro respectively |
| L3 Difficulty | token count (all request content) > threshold | **pro**; else fall through |
| L4 Edit checkpoint | trailing tool batch changed code (`edit`/`write`/`apply_patch`/...) | `toolRouting.edit` (default **pro**, `null` disables) |

CC's `/model` picker sets the tier model id (c1/flash / c1/pro / c1/think). awerouter reads it and routes accordingly — no keyword parsing, no LLM classifier. The image guard is a capability rule, not a difficulty guess: it sits above tier labels and long context, so with `imageModel: flash` an image-bearing request reaches the multimodal model no matter what tier it carries or how long it is (a model that cannot see images must never get them). Everything that matches no layer falls through to `settings.defaultModel` (default flash — cost-first).

L4 is a consequence checkpoint, not a difficulty guess. Structure cannot see the turn that *decides* an edit — that turn routes by whatever came before it — but the turn right *after* code changed is the review turn (verify, continue, report), so it goes to pro: flash drafts, pro reviews. The signal is the **trailing parallel batch** of tool calls: any edit-class call in it marks the batch (`[Grep, Edit]` and `[Edit, Grep]` route identically). Shell-wrapped calls (codex `exec_command`/`shell`) are classified by their command text — `apply_patch` counts as edit. L4 sits below L3 on purpose — a session already above `longContextThreshold` stays pro no matter what tool just ran, so flash never sees contexts it may degrade on and the long-context crossing stays one-way flash→pro (below the threshold, edit-checkpoint turns go pro and later turns return to flash). Edit-class covers `Edit`/`Write`/`NotebookEdit`/`apply_patch`/`replace_in_file` and friends, matched case-insensitively. Earlier versions also routed search/mechanical phases to flash here; since flash is already the fall-through default, those rules changed nothing and were removed (v0.4.8).

All tool-keyed rules live in one block — `settings.toolRouting` (`webSearch`/`edit`) — and the serve banner prints the active mapping on one `tool -> ...` line.

## Token Saver (RTK)

> **⚠️ Experimental — that's why it's off by default.** Compression is lossy: long file reads keep head + tail plus a skeleton of signature lines (the marker names the offset to re-read the middle), grep keeps 10 matches per file, diffs are line-capped. Format detection is heuristic and can misfire on unusual content, which loses information — the model usually notices and re-reads, costing an extra turn. If an agent starts behaving oddly (re-reading the same files, missing detail), turn RTK off or send `X-Awerouter-Token-Saver: off` for that session. Check real savings with `awerouter usage log`.

Coding agents resubmit the whole conversation every turn, and most of it is tool output — git diffs, grep hits, directory listings, build logs. A profile can opt into RTK compression, which rewrites that text in place before routing and forwarding:

```json
"cc-router-1": {
  "protocol": "anthropic",
  "longContextThreshold": 8000,
  "rtk": true,
  "destinations": { "flash": "stepfun,step-3.7-flash", "pro": "anthropic,claude-opus-5" }
}
```

- **What it touches:** `tool_result` / tool-message content only — never user prompts or model replies. Rule-based filters (git diff/status/log, grep, find, tree, ls, build output, …) auto-detect the format and compress it; unrecognized content, anything under 500 chars, and error results (`is_error`) pass through untouched.
- **Fail-open:** any failure (exception, filter error) leaves the body as-is — never a broken request. Note this guards against crashes, not heuristic misjudgment (see the warning above).
- **Deterministic:** the same history compresses to the same bytes every turn, so provider prompt-cache prefixes survive.
- **Per-request escape hatch:** send `X-Awerouter-Token-Saver: off` to forward one request uncompressed (e.g. debugging an agent that needs full diff/log detail).
- Compression runs before routing, and `/v1/messages/count_tokens` is compressed too, so L3 decisions and usage logs match what is actually billed. After enabling RTK, re-run `usage calibrate` — a threshold tuned on uncompressed traffic over-triggers pro (`"auto"` self-corrects after its window).

Compression is inspired by [rtk](https://github.com/rtk-ai/rtk) (Apache 2.0) and [9router](https://github.com/decolua/9router)'s JS port (MIT); this implementation is a from-scratch Python rewrite. The request log records the estimated saved tokens per request.

## Commands

```bash
awerouter init [TEMPLATE]             # create config from a bundled template (default / step-glm / glm-codex / step-glm-mm); --merge fills it into an existing config
awerouter add                         # interactively add a profile (pick category and providers)
awerouter list                        # list profiles (name, protocol, port, flash, pro, threshold)
awerouter serve [PROFILE] [--port N] [--host 127.0.0.1]  # port: --port > profile 'port' > 20128
awerouter <PROFILE>                   # shorthand for serve PROFILE
awerouter restore [providers|routing] # restore a config file from its .bak backup
awerouter self-update [--check]        # upgrade to the latest PyPI release (--check: versions only)
awerouter config path                 # print both config file paths
awerouter config show [PROFILE]       # redacted config; PROFILE = its providers + entry only
awerouter config edit [providers|routing]  # open one file in $EDITOR (backs up to .bak first)
awerouter usage stats [--since ..] [--profile ..]
awerouter usage clean                 # delete saved request logs (asks to confirm)
awerouter usage log [--lines 20] [--all] [--tokens] [--since ..] [--profile ..]
awerouter usage tokens [--since ..] [--profile ..]
awerouter usage calibrate [--since ..] [--profile ..]
awerouter usage savings [--since ..] [--profile ..]
```

All `usage` subcommands read the same request log. `log`, `stats`, `tokens`, `calibrate`, and `savings` take `--since` (`today`, `yesterday`, `7d`, or `YYYY-MM-DD`, local time) and `--profile` directly — e.g. `awerouter usage stats --since today --profile cc-1`; `clean` deletes everything and takes no window options.

`usage stats` aggregates the log per profile (with its wire protocol): label/agent/destination/provider/model breakdowns with percentages, error and fallback counts, latency percentiles (first byte and total) per destination/provider/model, and estimated request tokens (all request content: messages, system prompt, tools, tool I/O). `usage clean` deletes the saved logs (`requests.jsonl` + rotated backup) after a confirmation prompt. `usage log` shows entries verbatim — the last 20 by default, or every entry with `--all`; requests that went through a codex login re-read carry a `401-retry` marker; each line includes the protocol served and the calling agent, detected from the client's `User-Agent` header (`claude-cli/...` → `claude-code`, `codex_cli_rs/...` → `codex`, `opencode/...` → `opencode`). `--tokens` swaps the status/latency/model-in columns for the per-type token breakdown of each request (`msg/sys/tools/results/calls/think`); entries logged before per-type counting show only the total.

`usage tokens` aggregates those per-type breakdowns: input-token totals and share by content type (messages, system prompt, tool definitions, tool results, tool-call arguments, thinking) — useful for seeing how much of a request's tokens are environment constants (system prompt + tool definitions) versus conversation.

`config edit` and the `add` wizard snapshot the target file to `<name>.json.bak` before every write; `awerouter restore [providers|routing]` copies a backup back (with confirmation, then validates the restored config). `config path` prints the two config file paths; `config show [PROFILE]` shows the redacted full config, or just one profile's providers and routing entry.

`self-update` upgrades the installed package — pipx installs use `pipx upgrade awerouter`, everything else `pip install --upgrade`; restart running serve instances afterwards. Every command also checks PyPI in a background thread (at most once a day, cached as `update-check.json` in the config dir) and prints a one-line reminder after the command when a newer release exists — also throttled to once a day; `AWEROUTER_NO_UPDATE_CHECK=1` disables the check entirely. The serve banner shows the same update hint from the cached check.

`usage calibrate` shows the request-token distribution of L3 traffic (the threshold-sensitive layer; all request content — messages, system prompt, tools, tool I/O) and suggests candidate `longContextThreshold` values at p90/p95/p99, plus what `"auto"` would pick under `settings.longContextAuto`. Run it after some real traffic, then either edit `routing.json` or switch the profile to `"auto"` and let serve calibrate on each start.

`usage savings` is the token accounting view: how many request-input tokens each tier consumed and how many pro input tokens routing offloaded to flash vs a pro-only baseline. A cache-sensitivity section brackets the offload between "all cache reads" and "all full price" (Anthropic-style ~0.1x read / 1.25x write / 5-min TTL) and shows your switch cadence vs the TTL — a cache-warm pro-only baseline would have billed those tokens at cache-read prices. The output ends with ready-to-fill formulas using the measured token counts — substitute your providers' input prices (per 1M tokens) and read off the saved amount (output tokens, flash-side caching, and capability-mismatch turns are not modeled).

## Troubleshooting

**CC shows `502 status code (no body)` right after launch** — a shell proxy (Clash etc.) is hijacking loopback traffic. Requests to `127.0.0.1:20128` go into the proxy, whose `127.0.0.1` is itself, so nothing is listening and the proxy returns an empty 502. `serve` prints a warning when it detects this; fix it by exempting loopback in your shell config:

```bash
export no_proxy=127.0.0.1,localhost NO_PROXY=127.0.0.1,localhost
```

Then open a new terminal and relaunch CC.

## Development

```bash
git clone https://github.com/mugpeng/awerouter
cd awerouter
pip install -e ".[dev]"
pytest
```

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for architecture notes, config semantics, and the release process.

## Support

If awerouter saves you money, consider supporting it:

- ⭐ Star the repo — it helps others find it.
- ☕ [Ko-fi](https://ko-fi.com/mugpeng) — buy me a coffee.
- 💬 WeChat — scan the QR code below.

<p align="center">
  <img src="assets/images/wechat-pay.jpg" alt="WeChat Pay" width="240">
</p>

> awerouter is free and open source. Sponsors keep it maintained — thank you.

## Awesome Ecosystem

awerouter is part of a growing family of "awesome" tools — CLI-first, local-first, and operable by AI agents.

### CLI Tools

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first skill package manager supporting 47+ AI coding agents.
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Agent profile switcher for Claude Code, Codex, and OpenCode.
- **[awerouter](https://github.com/mugpeng/awerouter)** — Smart router that splits requests between Flash and Pro models using structural signals, cutting unnecessary model spend.
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — Bookmark, categorize, and restore AI coding sessions; pairs with aweswitch to save profiles and launch with one command.
- **[aweshare](https://github.com/wehuman01/aweshare)** — Share local Ollama/vLLM backends, domestic coding plans, or authorized OpenAI/Anthropic subscriptions through a self-hosted hub — a sharing economy for tokens.
- **[awewarm](https://github.com/wehuman01/awewarm)** — Subscription window warmer that keeps AI coding-plan windows active, for local setups and through a remote hub server.
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — AI-agent-operable scientific literature discovery and curation.

### Desktop Apps

- **[awedot](https://awedot.wehuman.top/)** — A floating orb at your screen edge keeps track of the current AI session: bookmark it in one click, resume anytime, and pair with aweswitch to pin the agent's config (e.g., relaunch with the GLM model).

### Project Collections

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — A curated survey of AI applications in biology, bioinformatics, and biomedical research. Powered by awescholar.
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — A curated collection of state-of-the-art AI systems for virtual tumor modeling and simulation: static models, dynamic models, agents, benchmarks, and reviews.
