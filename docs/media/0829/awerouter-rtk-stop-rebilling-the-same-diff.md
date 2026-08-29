# awerouter update: Stop Re-Billing the Same Git Diff Every Turn

![awerouter](../../../logo/logo.png)

Here is a fact about coding agents that pricing pages do not mention: an agent resends its entire history on every turn. The grep that ran in turn 3 is still sitting in the request at turn 30 — full text — and your provider bills it again, twenty-seven more times.

awerouter already sends the cheap traffic to cheap models. But even a cheap model charges for the same 80 KB of build log over and over. Routing fixes *where* tokens go; it does nothing about *how many* there are.

So awerouter grew an answer: RTK compression. It ships off by default — when you want it, opt in per profile with `"rtk": true`, and verbose tool output — git diffs, git status, grep hits, directory trees, file-read dumps, build logs — gets rewritten in place, before routing, before the request is billed. Same agent, same session, a fraction of the tokens.

Full credit where it is due: the compression pipeline is inspired by [rtk](https://github.com/rtk-ai/rtk) (Apache 2.0) and [9router](https://github.com/decolua/9router)'s JS port (MIT), reimplemented in Python from scratch. And it had to diverge in one respect — rtk is a local CLI that can tee raw output to disk before compressing, so a wrong guess is recoverable; a network proxy sees the bytes once. No recovery path means detection must be stricter, and that constraint shaped several of the guards below.

Here is how it works — and which details decide whether it actually saves you money.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## Only Compress What It Should

RTK recognizes tool output by type — git diff, git status, git log, grep hits, directory trees, build logs, line-numbered file reads — and each type gets its own compression. The rules have to be picky, and one near-miss says why: a pattern meant for git-status porcelain matched any line with deep indentation, and a Claude Code file read came within one regex of being rewritten into a single "clean — nothing to commit" line. The matcher now remembers what git users take for granted: real porcelain never has both status slots blank.

The principle fits on one line: a missed compression only wastes savings; a wrong one destroys what the model needed to see.

## The Skeleton: Cut the Middle, Keep the Shape

The blunt way to shrink a 2000-line dump is head + tail, discard the middle. The model sees what the file starts with, how it ends, and a hole.

The update keeps a **skeleton** of that hole: up to 60 signature, import, and declaration lines survive from the truncated middle, deduped. So instead of a blind gap, the model sees the file's structure — and, crucially, *knows what it did not see*. When it actually needs a cut function, the marker tells it exactly where to look: `re-read with offset=N`.

Lossy compression with an escape hatch for the reader. That is the difference between summarizing a file and hiding it.

## Idempotency: Same History In, Same Bytes Out

This one sounds boring and is load-bearing. Tool results are resent every turn — which is exactly what prompt caching bills on. If compression produces even one byte of drift between passes, the provider's cache prefix breaks and you pay full price again, the exact thing compression was saving.

So RTK treats determinism as a hard requirement: identical history must compress to identical bytes, every turn. Compressed text carries uniform markers, and anything already carrying a marker is left alone; per-format line caps sit below the detection gates, so already-compacted output never re-enters compression. The cache prefix survives.

## Savings You Can See

RTK savings were logged from day one and shown nowhere. Now every usage view carries them: a shared header prints `rtk: saved N input tokens (x/y requests compressed)` when anything was compressed, per-request entries show `rtk=+N`, and the savings view adds an rtk block noting it stacks with flash offload — the router sends traffic to the cheap tier, and compression makes even that tier smaller.

Nothing prints when nothing was compressed. A feature that is off should look off.

## The Contract: Fail Open, Opt Out, Recalibrate

- **Fail open**: compression is wrapped so that any internal error returns the original text. A compressor may under-save; it must never break a request.
- **Opt out**: any single request can skip compression with `X-Awerouter-Token-Saver: off`. Heuristics have limits; you keep the veto.
- **Recalibrate**: compressed requests change the token counts the long-context threshold reads, so after enabling rtk, run `usage calibrate` once. A threshold tuned on uncompressed traffic will over-trigger the pro tier.

RTK is experimental, which is why it ships off by default — without touching your config, nothing changes. It rewrites your tool output, and honesty about that is part of the design.

## Try It

### Let the agent install it

If you're in Claude Code, Codex, or any other coding agent, tell it:

```text
Read https://github.com/mugpeng/awerouter/blob/main/README.ai.md and follow it to install and configure awerouter.
```

### Or do it yourself

```bash
pip install awerouter

# In your profile, opt in:
#   { "rtk": true, ... }

# Then recalibrate thresholds on the compressed traffic
awerouter usage calibrate

# And watch what compression saves
awerouter usage savings
```

One-line summary: the router used to decide where your tokens go — now it can also decide how many of them there need to be.

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
