# awerouter联动：两个工具，一条命令

![awerouter](../../../logo/logo.png)

双厨狂喜的联动时刻，是属于它和[Webioinfo01/aweswitch: CLI proxy for switching AI model profiles (Claude Code, Codex, etc.)](https://github.com/Webioinfo01/aweswitch) 。

本地路由器不好写的那一半，没人愿意写。路由本身已经解决：四层、结构信号、零 token。剩下的是最后一公里——让一个真实的会话站到守护进程面前。在正确的 shell 里、在客户端启动之前，导出这几个环境变量，还不能踩到它们当前指向的东西。然后换下一个 agent 再来一遍，而它要的变量名还不一样。教程写到 `export ANTHROPIC_BASE_URL=...` 就收尾了，总感觉少了点什么。

这些导出有时候会出错，会腐烂。它们留在错误的终端里。它们指向一个重启后换了端口的守护进程。它们渗进从未请求过它们的会话。

解法不是给路由器再加一个功能，而是你手边可能早已有的那个工具。

GitHub：[github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## 另一半早已存在

[aweswitch](https://github.com/Webioinfo01/aweswitch) 是一个会话启动器。profile 存在一个 JSON 文件里（`~/.config/aweswitch/config.json`）；`aweswitch <profile>` 启动 agent，并把该 profile 的环境冻结进新进程。已打开的会话保持它们启动时的样子，不同终端可以并排运行不同 profile。

注意这个契合的形状。awerouter 对世界的全部要求是：一个会话启动时必须指向 `127.0.0.1:<port>` 并设好这几个环境变量。aweswitch 的全部工作是：用恰好这几个环境变量启动一个会话。两个工具里没有一行代码知道对方的存在。整份契约就是 localhost 加一个端口号。所谓"天然联动"，就是这个样子——两个各做一件事的工具，在一个 socket 上相遇。

## 五行配置，零秘密

aweswitch 配置里一个面向 awerouter 的 profile，完整如下：

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

这个 token 是 `"xxx"`——不是为本文打码，就是字面值。守护进程剥掉所有流入的认证头，在每个请求上盖上游提供商的真实凭证，所以启动 profile 里根本不携带任何秘密。在一整份满是 `${PROVIDER_TOKEN}` 引用的配置文件里，为了符合aweswitch 的占位要求。

model 那几行是层级接线：`auto` 走主干道，按难度逐请求路由；`flash` 和 `pro` 把 Claude Code 的后台与深度思考档位映射到路由器的层级标签上。`serve` 横幅会打印出这几行——粘贴一次，从此不再想起。

## 每个 Agent，同一个模式

每个 agent 用自己的环境变量名重复同一个模式，比如opencode：

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

再比如则是，Codex 用 `OPENAI_BASE_URL` 和 `OPENAI_MODEL` 依样画葫芦，指向一个以其 Responses 通信格式服务的守护进程。每个守护进程实例服务一个 profile；端口号就是 aweswitch profile 为会话挑选坐骑的方式。同时启动多个守护进程，它们按启动顺序排到 20128、20129……上；必须固定端口的 profile 在 `routing.json` 里钉上 `port`，被占用时就大声报错。而一个请求打到达成协议不符的守护进程时，得到的是一个点名的 400——"这个 profile 说 anthropic，这个端点服务 openai-chat"——一个你能据此行动的错误，而不是一堆乱码字节。

## 一个会话，多把钥匙

这对组合胜过任一工具单打独斗的最深层原因在这里。一个会话环境只装得下一个 token。但被路由的会话，廉价轮次去 StepFun、困难轮次去 Anthropic——不同的提供商，不同的钥匙。任何启动器都表达不了这件事，因为凭证被选定的时刻，早于任何人知道这个请求长什么样。

路由器是唯一能逐请求挑选凭证的地方，就在选定目的地的同一瞬间。这就是为什么 `"xxx"` 不是在藏一个秘密，而是在标记一个已经不活在会话里的决策。

## 路由器知道是谁在敲门

每个客户端都会在 `User-Agent` 里自报家门。awerouter 把它归一化——`claude-code`、`codex`、`opencode`——并写进请求日志，于是 `awerouter usage stats` 按标签、按 agent、按 profile 拆分流量。每个经 aweswitch 启动的会话都在分析里单独现身，零逐会话配置：你能看到 claude-code 的会话大多走 `default`，而 opencode 那个滑进了 `longContext`，然后据此调整各自的 profile。

## 分工

aweswitch 路由会话，awerouter 路由请求。一个决定进程指向哪里；另一个决定每个请求去向何方。启动器冻结一个环境；路由器在每一轮上改写 model id 和凭证。

总共两条命令：

```bash
awerouter serve cc-router-1    # 一次，丢在角落的终端里
aweswitch cc-awerouter         # 每个会话
```

没有胶水代码。没有钩子。没有耦合——整个集成就是一个环境变量和一个端口号。各自只做一件事的工具，在 localhost 的 socket 上组合，而这套组合比大多数功能都顺滑。

## awerouter 系列文章

- [awerouter：不怕deepseek 涨价，一句话让智能路由给你省钱](https://mp.weixin.qq.com/s/8jucVeQWQRjCIUEXxj-fHQ)
- [awerouter 更新: 数据看板告诉你省了多少](https://mp.weixin.qq.com/s/V1tPgz-jEekAMRdLMzGZGQ)



## 更多来自 mugpeng

awerouter 是 aweteam 生态的一部分：

- **[aweskill](https://aweskill.webioinfo.top/)** — 以 CLI 为核心的技能包管理器，支持 47 款以上的 AI 编程智能体
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — AI 编程智能体配置方案切换器，支持 Claude Code、Codex 和 OpenCode；启动会话时自动指向 awerouter 守护进程
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — 支持配置方案感知恢复的 AI 编程会话管理器
- **[awerouter](https://github.com/mugpeng/awerouter)** — 智能大语言模型路由器，自动利用结构信号将智能体请求分配到快速低价的轻量模型或能力更强的旗舰提供商，平衡成本、延迟与推理质量
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — 面向 Awesome 列表的自动化科学文献发现与整理工具
