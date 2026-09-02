# awerouter update: Stop Re-Billing the Same Git Diff Every Turn

![awerouter](../../../logo/logo.png)

Here is a fact that pricing pages never mention: every turn, a coding agent resends its entire history — full text, all of it. The grep from turn 3 sits untouched in the request at turn 30, and your provider bills for it twenty-seven more times.

awerouter already routes simple work to cheap models. But routing decides *where* tokens go — not *how many*. The same 80 KB build log gets billed over and over, even at the cheapest rate.

So we added RTK compression. Enable it per profile with `"rtk": true`, and long tool outputs — git diffs, grep hits, directory listings, build logs — get compressed in place before routing and before billing. Same session, a fraction of the tokens.

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

## Awesome Ecosystem

aweshare is part of a growing family of "awesome" tools — CLI-first, local-first, and operable by AI agents.

### CLI Tools

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI-first skill package manager supporting 47+ AI coding agents.
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Agent profile switcher for Claude Code, Codex, and OpenCode.
- **[awerouter](https://github.com/mugpeng/awerouter)** — Smart router that splits requests between Flash and Pro models using structural signals, cutting unnecessary model spend.
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — Bookmark, categorize, and restore AI coding sessions; pairs with aweswitch to save profiles and launch with one command.
- **[aweshare](https://github.com/wehuman01/aweshare)** — Share local Ollama/vLLM backends, domestic coding plans, or authorized OpenAI/Anthropic subscriptions through a self-hosted hub — a sharing economy for tokens. New: `consumer list --ping` gives consumers end-to-end proof of every offering (RESULT / TIME / DETAIL), and `--ping-table` renders a clean FAIL/OK summary once the run completes; hub budgets complete ping cycles per consumer per day (default 10), tunable via `probeBudget` / `hub limits NAME --probe-budget N`.
- **[awewarm](https://github.com/wehuman01/awewarm)** — Subscription window warmer that keeps AI coding-plan windows active, for local setups and through a remote hub server.
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — AI-agent-operable scientific literature discovery and curation.

### Desktop Apps

- **[awedot](https://awedot.wehuman.top/)** — A floating orb at your screen edge keeps track of the current AI session: bookmark it in one click, resume anytime, and pair with aweswitch to pin the agent's config (e.g., relaunch with the GLM model).

### Project Collections

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — A curated survey of AI applications in biology, bioinformatics, and biomedical research. Powered by awescholar.
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — A curated collection of state-of-the-art AI systems for virtual tumor modeling and simulation: static models, dynamic models, agents, benchmarks, and reviews. 
