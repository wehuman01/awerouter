# awerouter update: The Image Bridge — Eyes for a Text-Only Flagship

![awerouter](../../../logo/logo.png)

awerouter's multimodal sidekick (the `step-glm-mm` template) always had an awkward edge: the flagship glm-5.3 does all the text work, while image-bearing requests go to the multimodal step-3.7-flash. The idea is sound — the image guard is a capability rule, and a model that cannot see images must never receive them. But once an image enters a session it stays in the history, the guard fires on every turn, and **the whole session is pinned to flash from then on**. You paste one error screenshot, and the next forty turns of pure-text refactoring all run on flash — no matter how strong your flagship is, the session never comes back.

The image bridge in v0.5.4 (`imageBridge`) cuts that chain: flash looks at the image and reports back in text, and the session returns to the flagship.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## How the Bridge Fires

The key distinction is between a **fresh upload this turn** and **images that only live in history**. An image in the final message means a model genuinely needs to see it now — it still routes to flash natively to look and answer. A text-only final message with images back in the history is where the bridge steps in:

1. awerouter has the multimodal flash (the destination `imageModel` points at) transcribe each **distinct** image once — the caption prompt asks for ALL visible text verbatim (code, UI labels, errors, paths), then layout and notable visual details;
2. the image blocks in the request body are replaced in place with the transcription, shaped like `[Image 1, transcribed by step-3.7-flash] ...`;
3. the rewrite happens **before** compression and routing, and the request runs the normal four-layer pipeline — no images left, the guard does not fire, and the session typically lands on the flagship (`defaultModel`). Even `/v1/messages/count_tokens` sees the rewritten body, so estimates match what is actually sent.

So a session now looks like: the turn with the image goes to flash to look; every turn after that carries flash's transcription back to the flagship. Transcriptions are cached by image content for the process lifetime — each distinct image is transcribed once, restarted processes start fresh — and the cache key carries the provider and model name, so switching destinations never passes one model's transcription off as another's.

The failure path is honest: any caption call that fails (network, non-200, empty response) leaves the request body untouched, and the image guard routes the whole turn to flash as before. You pay one extra call, but **an image is never sent to a model that cannot see it** — that invariant outranks everything. Codex subscription logins (SSE-only backend, cannot serve a non-streaming caption call) skip the bridge entirely; their behavior is unchanged.

## Costs and Limits

The fine print first — which is why it ships off by default, opt-in:

- Each distinct image costs one extra flash call (caption output capped at 2048 tokens); the first bridged turn pays a few seconds of latency, later ones hit the cache.
- The flagship reads flash's **transcription**, not the image — second-hand eyes. Pixel-exact comparison and dense-screenshot precision top out at transcription quality. Turns that genuinely need to look were routed to flash anyway.

## Configuration

The `step-glm-mm` template turns it on by default (as of v0.5.4); three settings lines are the whole trick:

```json
"settings": {
  "imageModel": "flash",
  "defaultModel": "pro",
  "imageBridge": true
}
```

Copy the three lines into any existing config — the full template is not required. One practical tip: `imageBridge`, like every settings key, can also live in a single profile's body — the right place when only that profile has a multimodal `imageModel`. A global switch makes every profile transcribe via its own `imageModel`; a text-only one fails every caption call and falls back, one wasted upstream call per attempt.

## Try It

### Let the agent install it

If you're in Claude Code, Codex, or any other coding agent, tell it:

```text
Read https://github.com/mugpeng/awerouter/blob/main/README.ai.md and follow it to install and configure awerouter.
```

### Or do it yourself

```bash
pip install -U awerouter        # needs v0.5.4+

awerouter init step-glm-mm      # requires STEPFUN_AUTH_TOKEN and GLM_API_KEY

awerouter serve
```

The new banner line tells you it's live:

```text
image bridge  -> on (stepfun/step-3.7-flash transcribes history images to text)
```

To verify: paste an image and ask about it (that turn goes to flash), then ask a text-only follow-up in the same session — the serve log prints `bridge: ... transcribed image ...`, and `awerouter usage log` shows that turn's destination as the flagship. The session really came back.

One-line summary: image turns go to the model that can see; every other turn returns to the flagship — with no chain in between.

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
