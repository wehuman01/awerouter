# awerouter Bootstrap Protocol

This document is for AI coding agents. Help the user install and configure `awerouter`, a transparent LLM router that splits coding-agent traffic across cheap/fast and strong/accurate providers.

## Language Behavior

- Reply in the user's language when possible.
- If the user asks in Chinese, continue in Chinese.
- If the user asks in English, continue in English.

## Do Not Launch Servers

**Never run `awerouter serve run` or `awerouter serve all` inside this agent.** They start a long-lived proxy session. Always tell the user to run them in their own terminal.

You may run these read-only or non-interactive commands: `awerouter init`, `awerouter config path`, `awerouter config show`, `awerouter config edit`, `awerouter list`, `awerouter serve status` (read-only instance listing), `awerouter usage stats`, `awerouter usage log`, `awerouter usage calibrate`, `awerouter usage savings`.

Do not run `awerouter add` inside the agent — it is interactive and would block the session.

## Step 1: Install awerouter CLI

### Prerequisites

- Python >= 3.9 (`python3 --version`)
- pip available (`pip --version`)

If Python is missing, tell the user to install it from https://www.python.org/.

### Steps

#### 1. Install awerouter

```bash
pip install awerouter
```

#### 2. Verify awerouter CLI

```bash
awerouter --version
```

Expected output: `awerouter X.Y.Z`

---

## Step 2: Install awerouter skill

Install the skill so the agent can help manage routing in this and future sessions. Choose one of the following options.

### Option A: Via aweskill (recommended if aweskill is available)

Use this option if the user already has aweskill installed, or is willing to install it. This gives full skill management — install, update, projection, backup.

#### Prerequisites

- Node.js >= 20 (`node --version`) — required by aweskill
- npm available (`npm --version`)

If Node.js is missing, tell the user to install it from https://nodejs.org/.

#### Steps

##### A1. Install aweskill (if not already installed)

```bash
npm install -g aweskill
```

##### A2. Initialize the aweskill central store (if not already done)

```bash
aweskill store init
```

##### A3. Install awerouter skill from GitHub

```bash
aweskill install wehuman01/awerouter
```

##### A4. Identify the current agent

```bash
aweskill agent supported
```

Look for lines marked with `✓`. Common agent ids: `claude-code`, `codex`, `cursor`, `gemini-cli`, `windsurf`, `opencode`, `qwen-code`.

If you cannot determine the agent id, ask the user.

##### A5. Project awerouter skill to this agent

```bash
aweskill agent add skill awerouter --global --agent <agent-id>
```

##### A6. Verify

```bash
aweskill agent list --global --agent <agent-id>
```

Expected: `awerouter` shows as `linked`.

---

### Option B: Direct copy (no aweskill needed)

Use this option if the user does not have aweskill and does not want to install Node.js. This copies the SKILL.md file directly into the agent's skill directory.

#### Prerequisites

- `curl` or `wget` available

#### Steps

##### B1. Identify the current agent's skill directory

Determine which agent is running and its global skill directory:

| Agent | Skill directory |
|---|---|
| Claude Code | `~/.claude/skills/awerouter/` |
| Codex | `~/.codex/skills/awerouter/` |
| Cursor | `.cursor/skills/awerouter/` (project-level) |
| Gemini CLI | `~/.gemini/skills/awerouter/` |
| Windsurf | `~/.windsurf/skills/awerouter/` |
| OpenCode | `~/.opencode/skills/awerouter/` |
| Qwen Code | `~/.qwen/skills/awerouter/` |

If the agent is not in this list, ask the user where to place the skill file.

##### B2. Download and place SKILL.md

```bash
mkdir -p <skill-directory>
curl -fsSL https://raw.githubusercontent.com/wehuman01/awerouter/main/resources/skills/awerouter/SKILL.md -o <skill-directory>/SKILL.md
```

Replace `<skill-directory>` with the path from step B1.

---

## Step 3: Initialize config

```bash
awerouter init            # or pick a bundled combo: awerouter init step-glm / glm-codex / step-glm-mm
awerouter init <template> --merge   # config already exists? add the template's missing providers/profiles/settings without overwriting anything
```

This creates config files in `~/.config/awerouter/` from a bundled template:
- `providers.json`
- `routing.json`

With `--merge` on an existing config, the template's missing providers, profiles, and settings are added in place — existing entries are never overwritten. The merged config is validated before the command finishes. (If config is missing, `--merge` falls back to creating it from the template.)

Bundled templates are `<name>.providers.json` + `<name>.routing.json` pairs (`default`, `step-glm`, `glm-codex`, `step-glm-mm`; the README's "Common setup templates" section says what each combo routes where). An unknown name fails with the list of available templates. `step-glm-mm` is the multimodal sidekick: settings `imageModel: flash` + `defaultModel: pro` make a non-multimodal flagship (pro) do all the work while image-bearing requests go to the multimodal flash; it also sets `imageBridge: true`, so follow-up text turns return to pro carrying flash's transcriptions of history images; its `protocol` is a list (`["anthropic", "openai-chat"]`), so one serve instance takes Claude Code and openai-chat clients on the same port.

Override with `AWEROUTER_CONFIG_DIR` if needed.

---

## Step 4: Configure providers and routing

Tell the user the difference between the two files:

- `providers.json` stores endpoints and auth. It contains secrets or secret references.
- `routing.json` stores routing strategy. It should usually be the file you edit to change behavior.

### Edit providers

Before writing anything, scan the shell config for API-key variables the user already exports (see "Discover existing keys first" in Step 5) and reuse them — reference existing variables with `${VAR_NAME}` instead of asking the user to set anything new.

1. Read `providers.json`.
2. Update only the protocol group you need: `anthropic`, `openai-chat`, or `openai-responses`.
3. Use `${ENV_VAR}` for auth values. Local model servers (Ollama, LM Studio, llama.cpp, vLLM) need no auth — omit the `auth` key entirely, e.g. `{ "base_url": "http://127.0.0.1:11434/v1" }` under `openai-chat`. A Codex subscription account needs no key either: `"auth": "codex"` under `openai-responses` (base_url `https://chatgpt.com/backend-api/codex`) rides the local Codex CLI login (`~/.codex/auth.json`).
4. Keep `base_url` exactly as the client expects.

### Edit routing

1. Read `routing.json`.
2. Set a `profile` id for each routing setup.
3. Set `protocol` to the matching provider group.
4. Set `longContextThreshold` to an integer, or `"auto"` to calibrate it from the profile's own traffic at each serve start (policy in `settings.longContextAuto`: `percentile`/`windowDays`/`minSamples`/`fallbackThreshold`, all optional).
5. Use `destinations.flash` for cheap/fast tasks and `destinations.pro` for hard tasks.
6. Optionally add `backups` — ordered failover queues keyed like `destinations` (`"backups": {"flash": ["glm,glm-4.7-flash"], "pro": [...]}`, same `provider,model` strings; a bare string is a one-element queue). On a pre-stream 429/5xx/network error the request walks the queue. Zero config each tier gets one implicit cross-tier hop (flash→pro, pro→flash); an explicit list replaces it (want pro at the end of the flash queue, list it). A 429/Retry-After cools the candidate ~30s in-process (capped 60s), so a dead quota window sticks to the backup. For image-bearing requests, backups under providers without `"multimodal": true` are dropped (declare it in providers.json). `provider/<model>` direct forwards never fail over — unless the same-vendor account entries share a `"pool": "stepfun"` tag in providers.json (multi-account quota spread): a 429 then fails over to the same model on the next pool member, declaration order wrapping from the named entry.

If the user is unsure, recommend starting from `awerouter init` and changing one profile at a time.

---

## Step 5: Set up environment variables

Provider auth uses `${ENV_VAR}` references that expand from the shell environment. These must be set before starting `awerouter serve run`. Providers without an `auth` key (local model servers) need no environment variable.

### Discover existing keys first

Before asking the user to set anything, scan for API-key variables they already have:

- Shell config files: `~/.zshrc`, `~/.bashrc`, `~/.bash_profile` — look for `export <NAME>=...` where NAME matches `*_API_KEY`, `*_AUTH_TOKEN`, `*_KEY`, or `*_TOKEN` (e.g. `GLM_API_KEY`, `STEPFUN_AUTH_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_KEY`).
- Windows: the user environment (`[Environment]::GetEnvironmentVariable("NAME", "User")`).
- This agent's own process environment.

Reference discovered variables directly in `providers.json` (e.g. `"auth": "${GLM_API_KEY}"`) so nothing new needs to be set. Report variable names only — never values. Only ask the user for keys that are missing, and persist those with the platform method below.

Local model servers (no `auth` key) and subscription sentinels (`"auth": "codex"` / `"auth": "claude"`) never read environment variables — discovery does not apply to them.

### Where to put them

| Platform | Target | Scope |
|----------|--------|-------|
| zsh (default on macOS) | `~/.zshrc` | all zsh shells |
| bash | `~/.bashrc` or `~/.bash_profile` | all bash shells |
| Windows | `setx` (writes user environment variables) | cmd and PowerShell both |

On Windows, prefer `setx` — it persists to the user environment, so both cmd and PowerShell pick it up.

### Format

bash/zsh — append to the shell config file:

```bash
export STEPFUN_AUTH_TOKEN="..."
export GLM_API_KEY="..."
export OPENAI_API_KEY="..."
```

Windows — run `setx` (works from cmd and PowerShell):

```bat
setx STEPFUN_AUTH_TOKEN "..."
setx GLM_API_KEY "..."
setx OPENAI_API_KEY "..."
```

Do not pass `/M` to `setx` — that targets machine scope and requires admin.

### Steps

1. Read `providers.json` to find which `${ENV_VAR}` names are referenced.
2. Check which env vars are already set to avoid duplicates.
3. Set them using the platform-appropriate method.
4. Tell the user to reload: `source ~/.zshrc` (bash/zsh) or open a new terminal (Windows `setx` — it does not affect the current one).

---

## Step 6: Tell the user to start serving (pick a mode)

`awerouter serve` is a long-lived daemon — never run it inside the agent. Present the two modes and let the user pick.

### Option A: Smart routing — one profile, flash/pro split

Client base URLs (the serve banner prints them):
- Claude Code -> `ANTHROPIC_BASE_URL=http://127.0.0.1:20128`
- OpenAI-compatible clients -> `OPENAI_BASE_URL=http://127.0.0.1:20128/v1`

Tell the user to start the daemon themselves:
```bash
awerouter serve run [profile-name]          # foreground
awerouter serve run [profile-name] -d       # background: survives the terminal, log in ~/.local/state/awerouter/serve-<profile>.log
awerouter serve run [profile-name] --install  # resident service: starts at login, survives reboots/crashes (launchd / systemd user unit)
```

### Option B: Local integrated gateway — every profile and declared model on one port

`awerouter serve all` serves every routing.json profile plus every provider-declared model on one port; clients pick by model name:
- `<profile>/auto` — that profile's smart route; `<profile>/flash` / `<profile>/pro` force a tier (a profile's own tier labels also work).
- `<provider>/<model>` — a fixed forward to a model listed in that provider's `models` array (providers.json, per protocol group); it bypasses automatic routing.

Base URLs are the same shape as Option A (`/v1` for the openai wires, bare for anthropic — the endpoint path picks the wire protocol among those a profile serves). `GET /v1/models` lists every available name; unknown names return a descriptive 400. Tell the user:

```bash
awerouter serve all [--port N] [-d] [--install]
```

If the user wants a provider's models directly callable, add the `models` list to its providers.json entry — you may make that edit yourself. The optional top-level `defaultProfile` in routing.json maps bare `auto`/`flash`/`pro` names to one profile (keeps Claude Code's three-tier env vars working).

If only one routing profile exists, the profile name is optional. Either way, `awerouter serve status` shows every running instance (foreground, background, and resident). Resident instances show as `svc:launchd` / `svc:systemd`; `awerouter serve stop [PROFILE]` stops them through the service manager (a plain SIGTERM would be instantly undone by the restart policy) — they return at the next login; `awerouter serve stop [PROFILE] --purge` also removes the service file so they never start again. Config edits (routing.json / providers.json) hot-reload without a restart — a broken file keeps the previous config serving until it parses again.

---

## Step 7: Verify and tune

Run these checks:
```bash
awerouter list
awerouter config show
awerouter usage stats
awerouter usage calibrate
```

If the user wants cheaper routing without losing accuracy:
1. Start from `awerouter usage calibrate`.
2. Adjust `longContextThreshold`, or set it to `"auto"` so each serve start picks the percentile of the profile's own recent L3 traffic (the calibrate output ends with the value auto would pick).
3. Review `awerouter usage savings`.

## Final Step

After setup, tell the user to invoke skills (`/` in Claude Code, `$` in Codex, or the equivalent in other agents) and check if `awerouter` appears in the list. If it does, the skill is ready to use immediately. If not, the user should restart the agent.

> awerouter is installed and configured. Invoke skills (type `/` or `$` depending on your agent) and look for `awerouter` — if it appears, you're good to go. If not, restart the agent. Then you can ask me things like:
>
> - "Add a GLM provider for the openai-chat group."
> - "List my awerouter profiles."
> - "Tune longContextThreshold from my usage."

If the user is speaking Chinese, use this version instead:

> awerouter 已安装并配置完成。请调用 skills（输入 `/` 或 `$`，取决于你的 agent），看看列表中是否出现了 `awerouter`。如果出现了，说明已就绪可以直接使用。如果没有，请重启 agent 后再试。然后你可以继续问我，例如：
>
> - "给 openai-chat 分组加一个 GLM provider。"
> - "列出我的 awerouter profile。"
> - "根据 usage 调一下 longContextThreshold。"

---

## Next Steps

### aweswitch — profile-based launching

awerouter pairs naturally with [aweswitch](https://github.com/Webioinfo01/aweswitch), the agent profile switcher. An aweswitch profile can point `ANTHROPIC_BASE_URL` (plus `ANTHROPIC_MODEL=auto` and the `_HAIKU_`/`_OPUS_` tier vars) at the awerouter daemon so routing is applied on launch.

If the user agrees, read the aweswitch AI install guide:

```
https://github.com/Webioinfo01/aweswitch/blob/main/README.ai.md
```

## Safety Rules

- Do not run `awerouter serve run` or `awerouter serve all` inside the agent.
- Do not hardcode secrets into config files.
- When scanning shell configs or the environment for keys, report variable names only — never print key values.
- Do not edit `providers.json` and `routing.json` in the same step unless the user explicitly asks.
- If a command fails, report the exact command and error message.
- If the user uses a non-default config directory, always use `AWEROUTER_CONFIG_DIR`.
