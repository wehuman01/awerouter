# awerouter更新：让rtk从请求源头替你省钱

![awerouter](../../../../logo/logo.png)

有个事实，模型定价页从来不会告诉你：编程智能体每一轮都会把完整历史重发一遍。第 3 轮跑的那次 grep，到第 30 轮还一字不差地躺在请求里，而服务商就为它收了二十七次钱。

awerouter 早就把简单的活儿派给了便宜的模型。可再便宜的模型，也不会对同一段 80 KB 的构建日志免单。路由管的是钱花在哪个模型上，管不了 token 本身有多少。

于是 awerouter 给出了自己的答案：RTK 压缩。它默认关闭——想用的时候，在 profile 里加一行 `"rtk": true`，冗长的工具输出——git diff、git status、grep 命中、目录树、文件读取内容、构建日志——就会在路由之前、计费之前被就地瘦身。同一个智能体，同一个会话，token 只剩零头。

来源必须说清楚：这套压缩管线参考了 [rtk](https://github.com/rtk-ai/rtk)（Apache 2.0）和 [9router](https://github.com/decolua/9router) 的 JS 移植版（MIT），在 awerouter 里用 Python 从零重写。有一点不得不和它做得不一样——rtk 是本地 CLI，压缩前可以把原始输出落盘备份，猜错了还能找回；而代理只经手这串字节一次，没有回头路。没有退路，检测就必须更严，下面好几道护栏都是被这个约束逼出来的。

下面说说它是怎么工作的——以及哪些细节，决定了它到底能不能真省下钱。

GitHub：[github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## 只压该压的

RTK 靠一组检测规则认出工具输出的类型——git diff、git status、git log、grep 命中、目录树、构建日志、带行号的文件读取——每种类型有自己的压缩方式。规则必须非常挑剔，一个踩过的坑就能说明为什么：有条本该匹配 git-status porcelain 的规则，把缩进很深的行也当成了命中，Claude Code 读回来的文件差点被改写成一行"clean — nothing to commit"。现在的匹配器记住了这条常识：真正的 porcelain 输出，两个状态位绝不会同时留空。

原则只有一条：宁可漏压，不可错压。漏压只是没省到钱，错压是把模型要看的东西改没了。

## 切掉中间，留个骨架

要把 2000 行输出压短，最粗暴的办法就是留头留尾、扔掉中间。模型看得见文件的开头和结尾，中间那段却完全看不见。

这次更新在切掉的中间留了一份**骨架**：最多 60 行签名、import 和声明语句会从中段保留下来，去过重。模型看到的不再是空白，而是文件的结构——更关键的是，它*清楚自己漏掉了什么*。等它真需要一个被切掉的函数时，标记会指路：`re-read with offset=N`。

有损压缩，但给读的人留了退路。"概括一个文件"和"把文件藏起来"，差别就在这里。

## 压缩不能弄坏缓存

这条听着最不起眼，其实最要命。工具结果每一轮都要重发——而 prompt 缓存计费的依据恰恰就是这些字节。只要压缩在两轮之间多出一个字节的漂移，服务商的缓存前缀立刻作废，你又得付全价——省下的钱原路退了回去。

所以 RTK 有条硬要求：同样的历史，每一轮必须压出同样的字节。压缩过的文本都带上统一的标记，凡是已带标记的内容一律不再碰；各类输出的行数上限都压在触发门槛之内，压过的结果不会二次进入压缩。缓存前缀稳稳保住。

## 省了多少，看得见

RTK 省了多少，从第一天起就在记录，可哪儿都不显示。现在每个用量视图都能看到它：只要这个窗口里有压缩发生，公共页头就会打印 `rtk: saved N input tokens (x/y requests compressed)`，逐条记录里多出 `rtk=+N`，节省视图里也添了个 rtk 区块，注明这笔节省可以和 flash 卸载叠加——路由把流量送去了便宜的层，压缩再让这一层的请求小上一号。

没压缩就什么都不打印。没开的功能，就该有没开的样子。

## 三条底线：出错放行、随时退出、重新校准

- **出错放行**：压缩全程裹着一层保护，内部出任何错都退回原文。压缩器可以省得少，但绝不能弄坏请求。
- **随时退出**：任何一个请求只要带上 `X-Awerouter-Token-Saver: off`，就能跳过压缩。自动识别总有看走眼的时候，否决权在你手里。
- **重新校准**：压缩改动了长上下文阈值所看到的 token 数，所以开了 rtk 之后记得跑一次 `usage calibrate`——拿未压缩流量调出来的阈值，会让 pro 层被频繁误触发。

RTK 还是实验性功能，这也是它默认关闭的原因——不动配置，就完全不生效。它会改写你的工具输出，README 里明明白白写着——把这一点讲清楚，本身就是设计的一部分。

## 上手试试

### 让智能体帮你装

如果你在 Claude Code、Codex 或任何其他编程智能体里，对它说：

```text
阅读 https://github.com/mugpeng/awerouter/blob/main/README.ai.md，按照说明安装并配置 awerouter。
```

### 或者自己动手

```bash
pip install awerouter

# 在 profile 里加一行开关：
#   { "rtk": true, ... }

# 然后在压缩后的流量上重新校准阈值
awerouter usage calibrate

# 看看压缩省了多少
awerouter usage savings
```

一句话总结：路由器过去决定 token 去哪儿，现在还管得住有多少 token 值得发出去。

## awerouter 系列文章

- [awerouter：不怕deepseek 涨价，一句话让智能路由给你省钱](https://mp.weixin.qq.com/s/8jucVeQWQRjCIUEXxj-fHQ)
- [awerouter 更新: 数据看板告诉你省了多少](https://mp.weixin.qq.com/s/V1tPgz-jEekAMRdLMzGZGQ)

## 更多来自 mugpeng

awerouter 是 aweteam 生态的一部分：

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI 优先的技能包管理器，支持 47+ AI 编程 agent
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Claude Code、Codex、OpenCode 的 agent 配置切换器
- **[awerouter](https://github.com/mugpeng/awerouter)** — 智能路由器，用结构信号把请求分给 Flash 或 Pro 模型，减少不必要的模型开销
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — 收藏、分类、恢复 AI 编程会话，还能搭配aweswitch 实现保存配置，一键启动
- **[aweshare](https://github.com/wehuman01/aweshare)** — 通过自建 Hub 共享本地 Ollama/vLLM 或已授权的 OpenAI/Anthropic 后端，实现token 的共享经济
- **[awewarm](https://github.com/wehuman01/awewarm)** — 订阅窗口保持器，让 AI 编程套餐的窗口持续激活，无论是本地设置，还是通过远程连接的服务器
