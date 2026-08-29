# awerouter update: Put a Local Model on Flash

![awerouter](../../../logo/logo.png)

awerouter's routing used to assume one thing: both ends of the ladder are API keys — flash gets a cheap key, pro gets a strong key. But the cheapest capable model you own may not sit behind any API at all. It may be running on your own machine, on hardware you already paid for.

So `auth` is now optional in providers.json. Any local inference server can take a slot in the protocol groups next to key-based providers, reached with no auth header at all — and everything still goes through the same transparent proxy.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## Local Models: No Key Required

Ollama, LM Studio, llama.cpp, vLLM — they all fit. Ollama speaks the Anthropic protocol natively these days, so even Claude Code profiles can put a local model on flash. The config looks like this:

```json
{
  "anthropic": {
    "ollama":    { "base_url": "http://127.0.0.1:11434" },
    "anthropic": { "base_url": "https://api.anthropic.com", "auth": "${ANTHROPIC_KEY}" }
  }
}
```

Local and cloud mix freely in the same profile — easy work for local, hard work for cloud:

```json
"destinations": {
  "flash": "ollama,qwen3-coder:30b",
  "pro":   "anthropic,claude-opus-5"
}
```

Common local servers' default ports are already accounted for: Ollama `11434`, LM Studio `1234`, llama.cpp `8080`, vLLM `8000` (the last three ride the `openai-chat` group with a `/v1` base_url, also no auth).

Some concrete examples: in a coding session, most turns are easy work — skimming grep results, summarizing a file, drafting a small function. A local 30b model handles those comfortably, for zero tokens. The turns that actually need brain — a 40k-token context review, a cross-file refactor — fall to the cloud key automatically. No switching back and forth; the router picks.

The existing fallback catches the rest: a connection error on flash promotes the request to pro. Local server down, machine just booted with the model still loading — one transparent hop to the cloud, and back to local for the next request. Local-first routing with a cloud safety net, no extra config.

One guard comes with it: a no-auth provider whose address is not loopback prints a warning at serve start. A vLLM on your LAN is legitimate; a forgotten key is more common. And the loopback check parses actual IPs rather than string-matching, so `127.0.0.1.evil.com` does not count as local.

## L4 Became One Rule: The Edit Checkpoint

One routing-layer simplification worth a paragraph. The layer that reacts to what the agent just did used to carry four rules, but the search and bookkeeping ones always fell through to flash anyway — which was already the default. So that layer is now a single rule: **the turn right after code changed goes to pro** — flash drafts, pro reviews. Routing is identical at defaults; config, docs, and the layer's name finally describe the same thing.

## Try It

### Let the agent install it

If you're in Claude Code, Codex, or any other coding agent, tell it:

```text
Read https://github.com/mugpeng/awerouter/blob/main/README.ai.md and follow it to install and configure awerouter.
```

### Or do it yourself

```bash
pip install awerouter

ollama pull qwen3-coder:30b      # local server listens on 127.0.0.1:11434

# providers.json: flash -> local ollama (no auth), pro -> your cloud key

awerouter serve
```

One-line summary: the flash slot no longer asks for a key — your own machine qualifies.

## More from the awerouter Series

- [awerouter: No Fear of DeepSeek Price Hikes — One Sentence Lets Smart Routing Save You Money](https://mp.weixin.qq.com/s/8jucVeQWQRjCIUEXxj-fHQ)
- [awerouter Update: The Dashboard Shows You Exactly How Much You Saved](https://mp.weixin.qq.com/s/V1tPgz-jEekAMRdLMzGZGQ)

## More from mugpeng

awerouter is part of the aweteam ecosystem:

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first skill package manager for 47+ AI coding agents
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Agent profile switcher for Claude Code, Codex, and OpenCode
- **[awerouter](https://github.com/mugpeng/awerouter)** — A smart LLM router that splits requests between Flash and Pro models using structural signals
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — Collect, classify, and restore AI coding sessions; pairs with aweswitch to save configs and launch in one click
- **[aweshare](https://github.com/wehuman01/aweshare)** — Share local Ollama/vLLM or authorized OpenAI/Anthropic backends through a self-hosted hub — a sharing economy for tokens
- **[awewarm](https://github.com/wehuman01/awewarm)** — Subscription window keeper that keeps AI coding plan windows active, locally or via a remote server
