# awerouter设计哲学3：配置不问你答不上来的问题

![awerouter](../../../logo/logo.png)

大多数工具把配置当考卷：拍脑袋选一个"多长算长"的魔法数字；把 API key 和路由策略塞进同一个文件，再纠结哪段敢提交进 git；回答一堆自己本来答不上来的问题，然后祈祷默认值是靠谱的。

用量看板那篇讲的是怎么读 awerouter 的数据。这篇讲数据底下那个更安静的设计决定：**配置里的每个问题，要么只有你能回答，要么可以靠测量回答——awerouter 拼了命不问第二种。**

这个原则在两处看得见摸得着：两文件拆分，和自己校准的阈值。

GitHub：[github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## 两个文件：花钱的，和聪明的

awerouter 的配置沿一条线劈开：`providers.json` 放花钱的东西——端点和 API key；`routing.json` 放聪明的东西——profile、flash/pro 映射、阈值。

这个拆分不是为了整洁，它决定了每个文件能干什么：

- `providers.json` 永远不需要离开你的机器，配置层面处处配合：key 写成 `${环境变量}` 引用而不是明文，`config show` 打印时一律脱敏，`config edit` 每次写入前先存一份 `.bak`，改坏了 `awerouter restore` 能退回去。
- `routing.json` 里没有任何秘密，所以可以提交进 git。你的路由策略——你真正反复调试、搞坏又修好的那部分——从此有了版本、能看 diff、换台机器 `git clone` 就能带走。

最后这点最值钱。一个你不敢提交的配置文件，多半也备份不好。策略进了 git 之后，"我的路由器是怎么配的"这个问题就有了带历史的答案：每次实验是一个 diff，每次回滚是一次 checkout。

而且这道墙是强制的，不是倡议：`config show` 会交叉校验 routing 里的目的地和 providers 里的条目，引用写错在加载时就报错，而不是等到第一个请求才炸；`add` 向导一步写两个文件，保证两边始终对得上。拆成两个文件，是因为合成一个就必然二选一：要么可分享但不安全，要么安全但没法分享。

## 路由器唯一需要的那个数字

四层路由里，真正需要"判断力"的旋钮只有一个：长上下文阈值。"多少 token 算难？"——每个用阈值路由器的用户都会被问这个问题，而没有人答得上来。8000 token 难吗？一个塞满 grep 输出的搜索密集会话，不难；横跨十二个文件的紧凑重构，可能就难了。

把这个问题放进配置，等于把路由器的活儿外包给用户。awerouter 分两步把它收了回来：

**第一步，先摆证据。** `usage calibrate` 画出你自己的 L3 流量——你的会话实际产生的有效 token 分布——于是问题从"多少听起来合理"变成"我的流量实际落在哪儿"。你是对着自己历史的直方图选，不是照抄 README 里的数字。真实跑起来长这样（一台日常重度使用的机器，7 天窗口）：

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

这张表最值钱的是中间那段：每个候选阈值后面直接跟着后果——选 8000，22% 的请求上 pro；选 20000，只剩 9%。你选的不是一个数字，是一张账单。最后那行是 auto 自己的答案：你最重的那 5% 请求的分界线，就是它要的阈值。

**第二步，干脆不选了。** 把阈值设成 `"auto"`，awerouter 在每次 serve 启动时从你自己的流量里推导：取该 profile 过去一段窗口里 L3 有效 token 分布的 95 分位——你最重的那 5% 请求，按定义就是你想交给强模型的那批。样本还不够？先用靠谱的默认值，并且明说。启动横幅会打印选了什么、为什么，这个数字从不沉默。

两个细节保证 `"auto"` 不耍滑头：

- **启动时定死，进程内不再变。** 一个会话中途漂移的阈值，会让请求在两层之间反复横跳，还会把服务商的缓存前缀搅得一团糟。所以数值在开端口前确定，下一次 serve 再重新推导。校准在重启之间是连续的，在单次运行内是稳定的。
- **量的是你真发出去的流量。** 开了 RTK 压缩，阈值就从压缩后的请求里重新推导——和实际计费的是同一批字节。路由器测量它所路由的那个世界，不是某个理想化的世界。

注意配置里发生了什么：其中最难的问题——唯一需要判断力的那个——变成了一次测量。`"auto"`，一个词的事。

## 剩下的，都是你的

把能测量的都减掉，`routing.json` 里剩的是一串只有你能做的决定：用哪些服务商、哪些模型、谁当 flash 谁当 pro。这些是钱包问题。再多流量分析也推不出你持有哪些订阅、信任哪家服务商——配置留下它们，是因为本来就该留。

整条原则一句话说完：**配置可以问你拥有什么、偏好什么；不可以问能测量出来的东西。** 策略进 git，密钥不出机器，唯一的魔法数字从你自己的流量里长出来。文件里剩下的，都是你答得上来的。

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
- **[aweshare](https://github.com/wehuman01/aweshare)** — 通过自建 Hub 共享本地 Ollama/vLLM 后端、国内编程计划或授权的 OpenAI/Anthropic 订阅 — token 的共享经济。
- **[awewarm](https://github.com/wehuman01/awewarm)** — 订阅窗口保温器，保持 AI 编程套餐窗口激活，适用于本地设置和远程 hub 服务器。
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — 可由 AI agent 操作的科学文献发现和整理工具。

### 桌面应用

- **[awedot](https://awedot.wehuman.top/)** — 屏幕边缘的浮动球体跟踪当前 AI 会话：一键收藏，随时恢复，并可与 aweswitch 配合固定 agent 配置（例如使用 GLM 模型重新启动）。

### 项目集合

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — AI 在生物学、生物信息学和生物医学研究中应用的精选综述。由 awescholar 驱动。
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — 用于虚拟肿瘤建模和模拟的最先进 AI 系统精选集合：静态模型、动态模型、agent、基准测试和综述。
