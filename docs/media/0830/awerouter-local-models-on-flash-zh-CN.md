# awerouter更新：把本地模型放上flash

![awerouter](../../../logo/logo.png)

awerouter 的路由过去默认一件事：阶梯两端都是 API key——flash 配便宜 key，pro 配强力 key。可你手里最便宜又够用的模型，可能压根不在任何 API 后面——它就跑在你自己的机器上，硬件钱早就付过了。

变化就在这里：providers.json 里的 `auth` 现在可以不填。任何本地推理服务都能坐进协议分组，和 key 型服务商并排，请求以不带认证头的干净形态发往上游，一切都走原来那个透明代理。

GitHub：[github.com/mugpeng/awerouter](https://github.com/mugpeng/awerouter)

## 本地模型：不需要 key

Ollama、LM Studio、llama.cpp、vLLM 都能挂进来。如今 Ollama 原生支持 Anthropic 协议，所以连 Claude Code 的 profile 也能把本地模型放上 flash。配置长这样：

```json
{
  "anthropic": {
    "ollama":    { "base_url": "http://127.0.0.1:11434" },
    "anthropic": { "base_url": "https://api.anthropic.com", "auth": "${ANTHROPIC_KEY}" }
  }
}
```

本地和云端在同一个 profile 里随意混排——轻活给本地，难啃的给云端：

```json
"destinations": {
  "flash": "ollama,qwen3-coder:30b",
  "pro":   "anthropic,claude-opus-5"
}
```

常见本地服务的默认端口都帮你对好了：Ollama `11434`、LM Studio `1234`、llama.cpp `8080`、vLLM `8000`（后三家走 `openai-chat` 组，base_url 带 `/v1` 段，同样免认证）。

举点实际的例子：一次编程会话里，大多数轮次其实是轻活——翻一遍 grep 结果、总结一个文件、给个小函数起个草稿，这些交给本地的 30b 模型绰绰有余，一个 token 都不花；真正要动脑的轮次——四万 token 的上下文审查、跨文件的复杂重构——自动落到云端 key 上。不用你切来切去，路由自己挑。

降级机制也现成接得住：flash 连不上时，请求自动升到 pro。本地服务没启动、机器刚开机模型还没加载好，都透明地跳一次云端，下个请求又回到本地。本地优先、云端兜底，不需要任何额外配置——安全网本来就在那儿。

配套有一道护栏：免认证服务商的地址如果不是 loopback，serve 启动时会打印警告。局域网里的 vLLM 是正经用途，但忘填 key 更常见。loopback 检测解析的是真实 IP 而不是字符串匹配，所以 `127.0.0.1.evil.com` 不会被骗过去。

## L4 简化成了一条规则：编辑检查点

路由分层里顺带一提的简化。原本负责"回应智能体刚做了什么"的那一层带着四条规则，但其中搜索类和记账类的规则最终都会落到 flash——而 flash 本来就是默认值。所以那一层现在只剩一条规则：**刚改完代码的下一轮交给 pro**——flash 起草，pro 审查。默认配置下路由结果完全一致；只是配置、文档和这一层的名字，终于说的是同一件事。

## 上手试试

### 让智能体帮你装

如果你在 Claude Code、Codex 或任何其他编程智能体里，对它说：

```text
阅读 https://github.com/mugpeng/awerouter/blob/main/README.ai.md，按照说明安装并配置 awerouter。
```

### 或者自己动手

```bash
pip install awerouter

ollama pull qwen3-coder:30b      # 本地服务默认监听 127.0.0.1:11434

# providers.json：flash 放本地 ollama（免认证），pro 放你的云端 key

awerouter serve
```

一句话总结：flash 的位置不再要求 key——你自己的机器也算数。

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
