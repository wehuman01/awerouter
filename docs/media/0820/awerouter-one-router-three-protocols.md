# awerouter: One Router, Three Protocols, Any Provider Mix

![awerouter](../../../logo/logo.png)

Here is something most routing tools will not tell you up front: they are locked to one wire protocol and one provider ecosystem. An Anthropic-only router cannot speak to a GLM endpoint. An OpenAI-only router cannot front Claude Code. If you want to mix StepFun for cheap work and Anthropic for hard work, you need two tools.

awerouter does not have that limitation. It speaks three protocols natively — Anthropic Messages, OpenAI Chat Completions, OpenAI Responses — and within a single routing profile you can mix as many providers as you like inside one protocol group. Crossing protocols means starting another profile of the same router, not adopting a second tool. The router does not care what is on the other end. It only cares which end is cheap and which one is strong.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## One Profile, Many Providers

A routing profile has two destinations: `flash` and `pro`. Each destination is a comma-separated string of `providerName,modelId`. The provider name maps to an entry in `providers.json`, which stores the endpoint and auth for the matching protocol group.

```json
{
  "cc-router-1": {
    "protocol": "anthropic",
    "longContextThreshold": 8000,
    "destinations": {
      "flash": "stepfun,step-3.7-flash",
      "pro":   "anthropic,claude-opus-5"
    }
  }
}
```

The same profile can just as easily point `flash` at GLM and `pro` at OpenAI. The protocol group in `providers.json` carries the matching `base_url` — and because each provider often uses a different path per protocol, the config lets you specify the right endpoint for each wire format:

| Protocol | Base URL convention | Endpoint |
|---|---|---|
| `anthropic` | `ANTHROPIC_BASE_URL` style, no `/v1` | `base_url + /v1/messages` |
| `openai-chat` | `OPENAI_BASE_URL` includes version | `base_url + /chat/completions` |
| `openai-responses` | `OPENAI_BASE_URL` includes version | `base_url + /responses` |

GLM, for instance, uses `https://open.bigmodel.cn/api/coding/paas/v4` for chat completions but `https://open.bigmodel.cn/api/v1` for responses. awerouter stores both under the same provider name, each in its own protocol group, and picks the right one at request time.

## The Client Does Not Need to Know

From the client's perspective, nothing changed. Claude Code still points at `ANTHROPIC_BASE_URL=http://127.0.0.1:20128`. Codex sets the same address as its `base_url` in `config.toml`. OpenCode points its own OpenAI-compatible provider config at it too. The awerouter daemon terminates the native protocol, applies the routing decision, and forwards the request upstream in the same wire format.

Each profile runs as its own daemon instance, and the instances share one config directory. Start several on the same machine and they line up on sequential ports — 20128, 20129, ... — so Claude Code, Codex, and OpenCode each sit in front of their own routing profile, each mixing providers differently. The router is the common layer. The clients never see each other.

## Protocol-Agnostic Routing

The routing decision itself is completely protocol-blind. The `resolve()` function receives a precomputed `InspectResult` — a normalized snapshot of the request's structure — and returns a `ResolveResult` with a destination and a label. It does not know whether the incoming request was Anthropic Messages or OpenAI Chat Completions. It does not need to.

Three protocol-specific extractors produce the same `InspectResult`:

- `token_count` — estimated total input tokens
- `has_image` — any image block present
- `has_web_search` — `web_search_*` tool declared
- `file_search_tokens` — tokens from grep/glob/ls results only
- `last_tools` — the trailing batch of parallel tool calls, with `last_phase` flagging whether any call in it changed code

One router. Three extractors. Same decision.

## Mixing Providers Is Not an Afterthought

The reason multi-provider routing matters is not flexibility for its own sake. It is the price and capability spread between providers.

A typical setup: StepFun `step-3.7-flash` handles the high-frequency routine traffic at a fraction of the cost. Anthropic `claude-opus-5` handles the genuinely hard sessions. If you also use GLM for certain coding tasks, it slots in alongside them — no second router, no proxy chain, no client reconfiguration.

Adding a provider is a config edit, not an architecture change. The agent can do it in one turn:

> "Add GLM as a provider in the openai-chat group. Set flash to `glm,glm-4-flash`."

## Local Models Join the Mix

A provider does not have to be a cloud API. Local inference servers — Ollama, LM Studio, llama.cpp, vLLM — are providers too, and they need no key: omit the `auth` field and the request goes upstream with no auth header at all.

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

Any OpenAI-compatible server fits under `openai-chat` (LM Studio `http://127.0.0.1:1234/v1`, llama.cpp `http://127.0.0.1:8080/v1`, vLLM `http://127.0.0.1:8000/v1`); Ollama ≥ 0.14 also speaks the Anthropic protocol, so a local model can even sit in the `anthropic` group next to Claude Code. The path conventions match their cloud counterparts: `openai-chat` base_urls carry the `/v1` segment, `anthropic` ones don't.

From there, local and cloud mix freely in one profile — cheap drafting on a local model, hard calls on a cloud API:

```json
"destinations": {
  "flash": "ollama,qwen3-coder:30b",
  "pro":   "anthropic,claude-opus-5"
}
```

If the local server is down, the flash→pro fallback fires on connection errors and requests transparently go to the cloud — local-first routing with a cloud safety net, no extra config.

## Why This Matters

The first generation of LLM proxies assumed a one-to-one relationship: one client, one provider, one protocol. That model breaks down the moment you actually want to mix.

awerouter's design treats the protocol layer as transport and the provider mix as strategy. They are independent axes. You can change providers without touching routing logic. You can change routing logic without touching providers. The four-layer decision pipeline does not care which provider sits behind `flash` or `pro` — it only cares that `flash` exists and `pro` exists.

That separation is what lets one router and one config directory — one daemon instance per profile — serve every agent on your machine, across every provider you use, in every protocol they speak.

## More from the awerouter Series

- [awerouter: No Fear of DeepSeek Price Hikes — One Sentence Lets Smart Routing Save You Money](https://mp.weixin.qq.com/s/8jucVeQWQRjCIUEXxj-fHQ)
- [awerouter Update: The Dashboard Shows You Exactly How Much You Saved](https://mp.weixin.qq.com/s/V1tPgz-jEekAMRdLMzGZGQ)

## More from mugpeng

awerouter is part of the aweteam ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first skill package manager for 47+ AI coding agents
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Agent profile switcher for Claude Code, Codex, and OpenCode; launches sessions pointing at the awerouter daemon
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — AI coding session manager with profile-aware restoration
- **[awerouter](https://github.com/mugpeng/awerouter)** — A smart LLM router that automatically directs agent requests to fast, low-cost Flash models or more capable Pro providers using structural signals, balancing cost, latency, and reasoning quality.
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — Automated scientific literature discovery and curation for Awesome lists.
