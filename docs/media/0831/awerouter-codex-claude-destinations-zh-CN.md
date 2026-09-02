# awerouter更新：codex和claude订阅登录当上路由目的地

![awerouter](../../../logo/logo.png)

上一篇《awerouter更新：把本地模型放上flash》把本地模型放上了 flash 的位置；这篇是它的后续，轮到另一半：你已经付费的订阅。ChatGPT 订阅（通过 Codex CLI 的登录）和 Claude Pro 套餐，现在都能成为路由目的地——订阅登录和 API key 并排写进 providers.json，订阅自带的模型就能混进 flash/pro 路由，像任何其他服务商一样。

GitHub：[github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## 订阅登录：codex 和 claude 都能当目的地

两种订阅都能当路由目的地了，运作方式不同——这点我们如实说。

**codex**：providers.json 里把 auth 字段写成 `"codex"`，awerouter 就借用你本地 Codex CLI 的登录，ChatGPT 订阅自带的模型直接接进路由。它刻意不做一件事：替你续期登录。因为 OpenAI 的登录凭证是一次性的——谁续期谁接管，awerouter 要是抢着续，你本地 CLI 就被踢下线了。所以 awerouter 只在每次请求时读一眼 CLI 的登录文件，续期永远由 CLI 自己完成。

**claude**：把 auth 字段写成 `"claude"`，用的是 awerouter 自己持有的登录——在浏览器里完成一次设备码授权就行，不依赖本地 Claude Code CLI。正因为这个登录归 awerouter 所有，它才敢放手自动续期：凭证快过期就悄悄换新，几个请求同时赶上续期也不会打架。

有一条边界要提前说清：订阅目的地只能坐进它对应协议的 profile——codex 目的地属于 openai-responses，claude 目的地属于 anthropic。awerouter 是同协议直通，不做协议翻译，所以 ChatGPT 订阅和 Claude 订阅没法在同一份路由里一个当 flash 一个当 pro；想同时用两份订阅，就是两个客户端各指各的 profile。

出了问题两者的兜底一致：请求被拒（401）且重试无效，说明登录本身失效了——flash 有带 key 的去处就降级过去；压根没配登录，则直接报错并提示去跑 `codex login` 或 `awerouter login claude`，而不是默默拿付费 pro 硬撑。最后一句丑话：Anthropic 不允许第三方把订阅 token 挪作他用，这套玩法骑在你自己的订阅上，风险自担，接口也可能变。

## API、订阅、本地，随便串

到这里，flash/pro 的位置上可以坐三种东西了：API key 的云服务商、登录的订阅账号、免认证的本地模型。降级机制横跨所有种类：本地挂了跳云端 key，订阅登录失效了跳带 key 的服务商。举几个搭法：

- **能省则省**：flash = 本地 Ollama，pro = 便宜的 GLM key。轻活全部本地包办，一分不花；偶尔的硬活按量付费。
- **订阅最大化**：flash = GLM coding plan（key），pro = ChatGPT 订阅。日常扛量靠便宜的 key，硬骨头交给订阅里最强的模型。
- **双订阅，各归各**：订阅只能坐进自己协议的 profile——Codex 的 flash/pro 都指向 ChatGPT 订阅，Claude Code 的都指向 Claude 订阅，两份订阅各扛一个客户端，providers.json 里一个 key 都不用写。
- **飞机上也能干**：flash = 本地小模型，pro = 本地大模型。全程离线，断网、飞行模式，会话照样跑完。

阶梯怎么搭，看你的套餐和你的机器。

## 上手试试

### 让智能体帮你装

如果你在 Claude Code、Codex 或任何其他编程智能体里，对它说：

```text
阅读 https://github.com/mugpeng/awerouter/blob/main/README.ai.md，按照说明安装并配置 awerouter。
```

### 或者自己动手

```bash
pip install awerouter

codex login               # codex 目的地用的就是这份登录
awerouter login claude    # 浏览器设备码登录，归 awerouter 所有

awerouter serve
```

一句话总结：路由表里的位置，现在可以由 API key、订阅账号、本地模型任意填补——你已经拥有的算力，路由器都用得上。

## awerouter 系列文章

- [awerouter：不怕deepseek 涨价，一句话让智能路由给你省钱](https://mp.weixin.qq.com/s/8jucVeQWQRjCIUEXxj-fHQ)
- [awerouter 更新: 数据看板告诉你省了多少](https://mp.weixin.qq.com/s/V1tPgz-jEekAMRdLMzGZGQ)

## Awesome 生态系统

aweshare 是一个不断壮大的 "awesome" 工具家族的一部分 — CLI 优先、本地优先，可由 AI agent 操作。

### CLI 工具

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI 优先的技能包管理器，支持 47+ AI 编程 agent。
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Claude Code、Codex 和 OpenCode 的 agent 配置切换器。
- **[awerouter](https://github.com/mugpeng/awerouter)** — 智能路由器，使用结构信号在 Flash 和 Pro 模型之间分配请求，减少不必要的模型开销。
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — 收藏、分类和恢复 AI 编程会话；与 aweswitch 配合保存配置并一键启动。
- **[aweshare](https://github.com/wehuman01/aweshare)** — 通过自建 Hub 共享本地 Ollama/vLLM 后端、国内编程计划或授权的 OpenAI/Anthropic 订阅 — token 的共享经济。新增：`consumer list --ping` 为消费者提供每个产品的端到端证明（RESULT / TIME / DETAIL），`--ping-table` 在运行完成后呈现清晰的 FAIL/OK 摘要；hub 为每个消费者每天完成完整的 ping 循环（默认 10 次），可通过 `probeBudget` / `hub limits NAME --probe-budget N` 调整。
- **[awewarm](https://github.com/wehuman01/awewarm)** — 订阅窗口保温器，保持 AI 编程套餐窗口激活，适用于本地设置和远程 hub 服务器。
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — 可由 AI agent 操作的科学文献发现和整理工具。

### 桌面应用

- **[awedot](https://awedot.wehuman.top/)** — 屏幕边缘的浮动球体跟踪当前 AI 会话：一键收藏，随时恢复，并可与 aweswitch 配合固定 agent 配置（例如使用 GLM 模型重新启动）。

### 项目集合

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — AI 在生物学、生物信息学和生物医学研究中应用的精选综述。由 awescholar 驱动。
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — 用于虚拟肿瘤建模和模拟的最先进 AI 系统精选集合：静态模型、动态模型、agent、基准测试和综述。
