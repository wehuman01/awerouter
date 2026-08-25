# awerouter × aweswitch: Two Tools, One Command

![awerouter](../../../logo/logo.png)

Nobody writes about the unglamorous half of running a local router. The routing itself is solved: four layers, structural signals, zero tokens. What is left is the last mile — getting a real session in front of the daemon. Export these variables, in the right shell, before the client starts, without stepping on whatever those variables currently say. Then do it again for the next agent, which wants different variables. Tutorials end with `export ANTHROPIC_BASE_URL=...` and pretend the story is over.

Those exports rot. They live in the wrong terminal. They point at a daemon that came back on a different port. They leak into sessions that never asked for them.

The fix is not another feature in the router. It is a tool you may already have sitting next to it.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## The Other Half Already Exists

[aweswitch](https://github.com/Webioinfo01/aweswitch) is a session launcher. Profiles live in one JSON file (`~/.config/aweswitch/config.json`); `aweswitch <profile>` starts the agent with that profile's environment frozen into the new process. Already-open sessions keep whatever they started with, and different terminals run different profiles side by side.

Notice the shape of the fit. awerouter's entire requirement on the world is: a session must start pointing at `127.0.0.1:<port>` with these env vars set. aweswitch's entire job is: start a session with exactly these env vars set. Neither tool contains a line of code that knows about the other. The whole contract is localhost and a port number. That is what natural integration actually looks like — two tools that each do one thing, meeting at a socket.

## Five Lines, No Secret

An awerouter-facing profile in an aweswitch config, complete:

```json
"cc-awerouter": {
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:20128",
    "ANTHROPIC_AUTH_TOKEN": "xxx",
    "ANTHROPIC_MODEL": "auto",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "flash",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "pro"
  }
}
```

That token is `"xxx"` — not redacted for this article, the literal value. The daemon strips every incoming auth header and stamps the destination provider's real credential on each request, so the launch profile carries no secret at all. In a config file full of `${PROVIDER_TOKEN}` references, the only profiles whose token is a joke are the awerouter ones. That is a feature.

The model lines are the tier wiring: `auto` rides the main lane, routed per request by difficulty; `flash` and `pro` map Claude Code's background and think picks onto the router's tier labels. The `serve` banner prints these exact lines — paste them once, never think about them again.

## Every Agent, the Same Pattern

Each agent repeats the pattern under its own env names:

```json
"oc-awerouter": {
  "env": {
    "OPENCODE_BASE_URL": "http://127.0.0.1:20128/v1",
    "OPENCODE_API_KEY": "xxx",
    "OPENCODE_NAME": "awerouter",
    "OPENCODE_MODEL": "auto"
  }
}
```

Codex does the same with `OPENAI_BASE_URL` and `OPENAI_MODEL`, pointed at a daemon whose profile speaks its Responses wire format. Each daemon instance serves one profile; the port number is how an aweswitch profile chooses which one a session rides. Start several daemons and they line up on 20128, 20129, ... in start order; a profile that must own a fixed port pins `port` in `routing.json` and fails loudly if someone else took it. And a request that reaches a daemon of the wrong protocol gets a named 400 — "this profile speaks anthropic, this endpoint serves openai-chat" — an error you can act on, not garbage bytes.

## One Session, Many Keys

Here is the deepest reason the pair beats either tool alone. A session environment holds exactly one token. But a routed session's cheap turns go to StepFun and its hard turns go to Anthropic — different providers, different keys. No launcher can express that, because the credential is chosen before anyone knows what the request is.

The router is the one place where the credential can be picked per request, at the same moment the destination is. That is why `"xxx"` is not hiding a secret. It is marking a decision that no longer lives in the session.

## The Router Knows Who Is Calling

Every client identifies itself in `User-Agent`. awerouter normalizes it — `claude-code`, `codex`, `opencode` — and writes it into the request log, so `awerouter usage stats` breaks traffic down by label, by agent, by profile. Every aweswitch-launched session shows up in the analytics individually, with zero per-session setup: you can see that the claude-code session took mostly `default` turns while the opencode one tipped into `longContext`, and tune each profile accordingly.

## Division of Labor

aweswitch routes sessions. awerouter routes requests. One decides where a process points; the other decides where each request goes. The launcher freezes an environment; the router rewrites the model id and the credential on every turn.

Two commands total:

```bash
awerouter serve cc-router-1    # once, in a corner terminal
aweswitch cc-awerouter         # per session
```

No glue code. No hooks. No coupling — the entire integration is an env var and a port number. Tools that each do exactly one thing compose at a localhost socket, and the composition is smoother than most features.
