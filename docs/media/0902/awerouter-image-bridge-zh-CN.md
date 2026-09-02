# awerouter更新：图片桥接，给纯文本旗舰一双眼睛

![awerouter](../../../logo/logo.png)

awerouter 的多模态侧翼（`step-glm-mm` 模板）一直有个尴尬：旗舰 glm-5.3 包揽全部文本工作，带图的请求交给多模态的 step-3.7-flash——思路没错，图片护栏是能力规则，看不见图的模型绝不能收到图。可图一旦进了会话就留在历史消息里，护栏每一轮都触发，**整个会话从此钉死在 flash 上**。你贴了一张报错截图，接下来的四十轮纯文本重构全在 flash 上跑，旗舰再强也接不回来。

v0.5.4 的图片桥接（`imageBridge`）把这条锁链剪断了：flash 看完图转述成文字，会话回到旗舰。

GitHub：[github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## 桥接是怎么发生的

关键区分是**本轮新传的图**和**只剩历史的图**。最后一条消息里有图，说明模型这一轮真要看——照旧原生路由给 flash，让它看图作答。最后一条消息是纯文本、图只在历史里，桥接才出手：

1. awerouter 让多模态的 flash（`imageModel` 指向的 destination）把每张**不同的**图片转写一次——转写提示词要求逐字转录图里所有可见文本（代码、UI 标签、报错、路径），再描述布局和视觉细节；
2. 请求体里的图片块被原地替换成转写文本，长这样：`[Image 1, transcribed by step-3.7-flash] ...`；
3. 改写发生在压缩和路由**之前**，请求照常走四层管线——没有图了，护栏不触发，会话典型落到旗舰（`defaultModel`）。连 `/v1/messages/count_tokens` 看到的都是改写后的请求体，估算和实发一致。

于是会话的形态变成：贴图那一轮 flash 看图，之后每一轮旗舰带着 flash 的转述继续干活。转写按图片内容缓存在进程内存——同一张图只转写一次，重启后重来；转写缓存键里带 provider 和模型名，换了 destination 绝不会把 A 模型的转述冒充 B 模型的。

失败路径是诚实的：任何一次转写调用失败（网络、非 200、空响应），请求体保持原样，图片护栏照旧把整轮路由给 flash。多付一次调用，但**绝不把图发给看不见图的模型**——这条不变量优先于一切。codex 订阅登录（SSE-only 后端，没法服务非流式转写调用）直接跳过桥接，行为不变。

## 成本与边界

把丑话说在前面，这也是它默认关闭、opt-in 的原因：

- 每张不同的图片多付一次 flash 调用（转写输出上限 2048 token）；第一个桥接轮承担几秒延迟，之后命中缓存。
- 旗舰看到的是 flash 的**转述**，不是图本身——这是双二手的眼睛。像素级比对、密集截图精读这类活儿，上限就是转写质量。真需要看图的轮次，本来就路由给了 flash。

## 配置

`step-glm-mm` 模板已默认开启（v0.5.4 起），三行 settings 就是全部：

```json
"settings": {
  "imageModel": "flash",
  "defaultModel": "pro",
  "imageBridge": true
}
```

已有的配置抄这三行进去就行，不需要整个模板。一个实用建议：`imageBridge` 和其他 settings 键一样可以只写在某个 profile 体内——当只有个别 profile 拥有多模态 `imageModel` 时就该这么用，全局开启会让每个 profile 都用自己的 `imageModel` 去转写，纯文本的每次都失败再回退，白白多付调用。

## 上手试试

### 让智能体帮你装

如果你在 Claude Code、Codex 或任何其他编程智能体里，对它说：

```text
阅读 https://github.com/mugpeng/awerouter/blob/main/README.ai.md，按照说明安装并配置 awerouter。
```

### 或者自己动手

```bash
pip install -U awerouter        # 需要 v0.5.4+

awerouter init step-glm-mm      # 需要设置 STEPFUN_AUTH_TOKEN 和 GLM_API_KEY

awerouter serve
```

启动横幅多出的一行就是开关所在：

```text
image bridge  -> on (stepfun/step-3.7-flash transcribes history images to text)
```

验证方法：贴一张图提问（这轮走 flash），接着在同一会话里问一个纯文本的后续问题——serve 日志打出 `bridge: ... transcribed image ...`，`awerouter usage log` 里这轮的 destination 变成旗舰，会话就真的回来了。

一句话总结：带图的轮次交给看得见图的模型，其余轮次回到旗舰——中间不再有锁链。

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
