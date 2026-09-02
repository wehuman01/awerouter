# awerouter: Routing That Costs Nothing to Decide

![awerouter](../../../logo/logo.png)

Most "smart" LLM routers are smart the expensive way. They run an LLM classifier over your request to decide where it should go. Or they match keywords against a curated list. Or they replay conversation history into a scoring function.

All of these share a hidden cost. The classifier burns tokens on every request — tokens you pay for, on top of the request itself. The keyword list adds latency and drifts out of date. The scoring function needs your conversation history, which means it is reading things it should not need to read.

And all of them guess. A classifier can be wrong in both directions. A wrong routing decision is either wasted money or degraded quality — invisible to you either way.

awerouter routes from structure. The shape of a request — what tools it declares, what model id it carries, how many tokens it holds, what the agent just did — is enough signal to route well. And reading that shape is free.

GitHub: [github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## Four Questions, Zero Tokens

Every request goes through a first-match-wins pipeline. Four layers, each asking one question, each cheaper to answer than the last:

**Can flash even do this?** If the request declares a `web_search` tool, the question is capability, not difficulty. Many cheap providers do not support it. Route to a provider that can.

**What tier did the client pick?** Claude Code's `/model` picker already classifies tasks: background work versus think work. When the client sends `"flash"` or `"pro"` as the model id — the default tier labels, renameable in settings — that is an instruction, not a signal to interpret. Route accordingly.

**How big is this?** Token count against a threshold. If the request carries more content than the dial allows — or contains an image — route to the strong tier. This is the only layer that estimates difficulty, and the estimate is a tape measure, not a classifier.

**Did code just change?** Structure cannot see the turn that decides an edit — by the time a tool call exists to read, the decision is already made. What it can do is react: the turn right after an edit is the review turn — verify the diff, decide the next file. That turn goes to the strong tier; the cheap one drafts, the strong one reviews. The trailing batch of tool calls is an honest signal, and it costs nothing to read.

If no layer fires, the default is the cheap tier. Innocent until proven expensive.

## The Signal Is Already in the Request

Here is the core insight: everything the router needs to decide is already present in the request body, before a single byte goes upstream.

- The `tools` array tells you what capabilities the request needs.
- The `model` field tells you what tier the client chose.
- The message content tells you how much context is in play.
- The trailing batch of tool calls tells you whether code just changed.

None of this requires interpretation. None of it requires a model call. The router reads the structure, makes a decision, and forwards the request — all in the time it takes to make one local HTTP round-trip.

## Not All Tokens Are Equally Hard

One detail worth knowing: the token count is not a raw sum. File-search results — grep matches, glob listings, directory trees — are bulk mechanical data. They inflate a request's size but add almost nothing to its reasoning difficulty.

A context stuffed with two hundred file paths is big, but it is not hard. If the router compared raw size, every search-heavy session would get promoted on the weight of its file listings alone — paying pro prices for an overgrown `ls` output.

So search-result tokens are counted at a discount before the threshold comparison. The router measures the portion of the context that actually stresses a model. Measure difficulty, not tonnage. And none of the dials are locked: the search-result discount, the long-context threshold, and the other routing parameters all live in your config, ready to be tuned for your own model mix and workload.

## The Router Does Not Read Your Conversations

The most unusual constraint in the design: the response body is opaque. The router never parses, buffers, or inspects the bytes that come back from upstream — they stream from provider to client untouched. The one thing it reads is the status code, and only to know whether a cheap-tier failure deserves rescue by the strong tier. That reading costs nothing either.

This forecloses an entire category of "smarter" routers — ones that read the output, judge its quality, and adjust routing in a feedback loop. Without reading responses, there is no ground truth on quality, so there is no honest way to build a quality-sensitive router. awerouter does not pretend otherwise.

Instead, every decision comes from facts measurable before the first byte. Zero classification cost. The honesty is the design.

## Every Decision Has a Name

Every routed request gets a label: `webSearch`, `background`, `think`, `longContext`, `image`, `toolEdit`, `default` — plus `→fallback` when a cheap-tier failure was rescued.

When you look at your usage analytics and see 70% `default` and 14% `longContext`, you are not looking at a black box's verdicts. You are looking at exactly which question fired, for every request, with a record kept of each one.

A router that guessed would have to justify itself with vibes. A router that measures only has to show its work — and it does.

## The Bet, Restated

The structure of a request tells you enough about its cost and difficulty. Reading that structure is free. A router should never pay — in tokens, latency, or risk — to make a decision it can make for nothing.

Four questions, ordered from certainty to guesswork, with a cheap default and one-way safety doors. No classifier. No keywords. No oracle. Just measurement, honestly bounded.

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
