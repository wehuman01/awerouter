# awerouter update: Codex and Claude Logins as Routing Destinations

![awerouter](../../../logo/logo.png)

The last post, "awerouter update: Put a Local Model on Flash", put a local model on the flash slot; this one is its follow-up, and it goes after the other half: the subscriptions you already pay for. A ChatGPT plan (through the Codex CLI login) and a Claude Pro plan can both become routing destinations now — subscription logins sit in providers.json next to API keys, and the subscription's own models mix into flash/pro routing like any other provider.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## Subscriptions: Codex and Claude Logins as Destinations

Both subscriptions can be routing destinations now, and they work differently — honestly so.

**Codex**: set `"auth": "codex"` on a provider, and awerouter borrows your local Codex CLI's login, so the models your ChatGPT plan includes join the routing. One thing it deliberately never does: renew that login for you. OpenAI's login credentials are single-use — whoever renews them takes ownership, and if awerouter raced ahead, your local CLI would find itself logged out. So awerouter just re-reads the CLI's login file on every request, and renewal stays entirely with the CLI.

**Claude**: set `"auth": "claude"`, and you use a login that awerouter itself owns — one device-code authorization in your browser, no local Claude Code CLI involved. Because the login belongs to awerouter, it can afford to renew automatically: fresh credentials quietly replace expiring ones, and several requests hitting a renewal at the same time don't trip over each other.

One boundary to state up front: a subscription destination can only sit in a profile that speaks its own protocol — codex destinations belong to openai-responses profiles, claude destinations to anthropic profiles. awerouter is a same-protocol passthrough and does no protocol translation, so a ChatGPT subscription and a Claude subscription cannot share one routing table as flash and pro; to use both plans, each client points at its own profile.

When things go wrong, both behave the same: a rejected request (401) that survives a retry means the login itself is dead — flash falls back to a key-based destination if one exists; with no login configured at all, you get a clear error telling you to run `codex login` or `awerouter login claude`, instead of silently burning a paid pro. The honest caveat: Anthropic restricts third-party use of subscription tokens — this rides your own subscription, at your own risk, and the wire contract can drift.

## API Keys, Subscriptions, Local Models — Chain Them Freely

By now the flash/pro slots can be filled by three kinds of compute: key-based cloud providers, logged-in subscriptions, and no-auth local models. The fallback ladder crosses all three kinds: local down hops to a cloud key, a dead subscription login falls back to a key-based provider. A few ways to set it up:

- **Spend as little as possible**: flash = local Ollama, pro = a cheap GLM key. Easy work is handled locally for free; the occasional hard job pays by the token.
- **Maximize the subscription**: flash = GLM coding plan (key), pro = ChatGPT subscription. The cheap high-volume key carries daily traffic; the subscription's strongest model takes the hard parts.
- **Two subscriptions, one each**: a subscription can only sit in its own protocol's profile — Codex's flash and pro both point at the ChatGPT plan, Claude Code's both point at the Claude plan, each client carried by its own subscription with no key in providers.json.
- **Work offline**: flash = a small local model, pro = a big local model. The whole session runs on a plane or with the network unplugged.

Build the ladder that fits your plan and your machine.

## Try It

### Let the agent install it

If you're in Claude Code, Codex, or any other coding agent, tell it:

```text
Read https://github.com/mugpeng/awerouter/blob/main/README.ai.md and follow it to install and configure awerouter.
```

### Or do it yourself

```bash
pip install awerouter

codex login               # the codex destination rides this login
awerouter login claude    # browser device login, owned by awerouter

awerouter serve
```

One-line summary: the slots in your routing table can now be filled freely by API keys, subscription logins, and local models — compute you already own, all of it usable.

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
