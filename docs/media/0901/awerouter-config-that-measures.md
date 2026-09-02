# awerouter: Design Philosophy 3 — A Config Should Never Ask What It Can Measure

![awerouter](../../../logo/logo.png)

Most tools treat configuration as a quiz. Pick a magic number for "how long is too long". Paste your API keys into the same file as your routing strategy, and decide which parts you dare commit to git. Answer questions you have no basis to answer, and hope the defaults were sane.

The analytics post already showed how to read awerouter's usage views. This one is about a quieter design decision underneath them: **every question in the config is either answerable only by you, or answerable by measurement — and awerouter tries hard not to ask the second kind.**

Two places where this shows up in the flesh: the two-file split, and the threshold that tunes itself.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## Two Files: What Costs Money vs. What Is Clever

awerouter's configuration is split down one line: `providers.json` holds what costs money — endpoints and API keys; `routing.json` holds what is clever — profiles, flash/pro mappings, thresholds.

The split is not tidiness. It decides what you can do with each file:

- `providers.json` never needs to leave your machine, and the config surface respects that: keys are written as `${ENV_VAR}` references rather than inlined plaintext, `config show` prints them redacted, and `config edit` snapshots the file to `.bak` before every write, so `awerouter restore` can undo a bad edit.
- `routing.json` contains no secret, so it can be committed. Your routing strategy — the thing you actually iterated on, tuned, broke and fixed — is versioned, diffable, and portable to the next machine with a `git clone`.

That last point is the one worth paying for. A config file you are afraid to commit is a config file you back up badly. Once strategy lives in git, "how is my router set up?" has an answer with history — every experiment is a diff, every rollback is a checkout.

And the split is enforced, not suggested: `config show` cross-validates routing destinations against providers, so a typo'd reference fails at load instead of on the first request, and the `add` wizard writes both files in the same step to keep them consistent. Two files, because one file would have to be either shareable and unsafe, or safe and unsharable.

## The One Number the Router Needs

The four-layer router has exactly one dial that involves judgment: the long-context threshold. "How many tokens make a request difficult?" — that is the question every user of a threshold-based router gets asked, and nobody has an answer. Is 8,000 tokens hard? For a search-heavy session full of grep dumps, no. For a dense refactor across twelve files, maybe.

Asking that question in config is outsourcing the router's job. Two steps took it back:

**First, show the evidence.** `usage calibrate` plots your own L3 traffic — the distribution of effective token counts your sessions actually produce — so the question stops being "what sounds reasonable?" and becomes "where does my traffic actually sit?" You pick from a histogram of your own history instead of a number from a README. On a heavily used machine, over a 7-day window, it looks like this:

```text
L3 request-token distribution (412 requests):
  (all request content: messages, system prompt, tool definitions, tool I/O)
  (file-search tool results weighed at 30%)
  min:     980   p50:    6400   p75:   11200
  p90:   21500   p95:   34800   p99:   61000   max:   88400

if you set longContextThreshold to:
    8000   → 78% flash, 22% pro
   12000   → 84% flash, 16% pro
   20000   → 91% flash,  9% pro
   34800   → 95% flash,  5% pro

'auto' would set: 34,800  (p95 of 412 L3 requests, last 7d)
```

The middle block is the valuable part: every candidate threshold comes with its consequence attached — pick 8,000 and 22% of requests go to pro; pick 20,000 and only 9% do. You are not choosing a number, you are choosing a bill. And the last line is `"auto"`'s own answer: the boundary of your heaviest 5% of requests is exactly the threshold it wants.

**Then, stop picking.** Set the threshold to `"auto"` and awerouter derives it from your own traffic at every serve start: the 95th percentile of the profile's L3 effective-token distribution over a trailing window — your heaviest 5% of requests are, by definition, the ones you wanted on the strong tier. Not enough samples yet? It falls back to a sane default and says so. The banner at startup prints what was picked and why, so the number is never silent.

Two details keep `"auto"` honest:

- **It resolves once, at startup, and holds for the process lifetime.** A threshold that drifts mid-session would flip requests between tiers unpredictably and shred provider cache prefixes. So the value is fixed when the socket opens, and re-derived the next time you serve. Calibration is continuous across restarts, never wobbly within one.
- **It reads the traffic you actually send.** Turn on RTK compression and the threshold re-derives from compressed requests — the same ones that get billed. The router measures the world it routes, not some idealized one.

Notice what happened to the config: the hardest question in it — the only one requiring judgment — became a measurement. `"auto"` is one word now.

## What Is Left Is Yours

Subtract everything measurable, and what remains in `routing.json` is a short list of decisions only you can make: which providers, which models, which one is flash and which is pro. Those are wallet questions. No amount of traffic analysis can tell you which subscription you hold or which provider you trust — the config keeps them because it should.

That is the whole test, stated plainly: **a config may ask you what you own and what you prefer. It may not ask you what can be measured.** Strategy lives in git, keys never leave the machine, and the one magic number grows out of your own traffic. Nothing left in the file that you cannot answer.

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
- **[aweshare](https://github.com/wehuman01/aweshare)** — Share local Ollama/vLLM backends, domestic coding plans, or authorized OpenAI/Anthropic subscriptions through a self-hosted hub — a sharing economy for tokens.
- **[awewarm](https://github.com/wehuman01/awewarm)** — Subscription window warmer that keeps AI coding-plan windows active, for local setups and through a remote hub server.
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — AI-agent-operable scientific literature discovery and curation.

### Desktop Apps

- **[awedot](https://awedot.wehuman.top/)** — A floating orb at your screen edge keeps track of the current AI session: bookmark it in one click, resume anytime, and pair with aweswitch to pin the agent's config (e.g., relaunch with the GLM model).

### Project Collections

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — A curated survey of AI applications in biology, bioinformatics, and biomedical research. Powered by awescholar.
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — A curated collection of state-of-the-art AI systems for virtual tumor modeling and simulation: static models, dynamic models, agents, benchmarks, and reviews. 
