<div align="center">
  <img src="logo/logo.webp" alt="awerouter" width="860">
  <h1>awerouter: 智能 LLM 路由 <a href="https://github.com/Webioinfo01/aweskill"><img src="https://raw.githubusercontent.com/Webioinfo01/aweskill/main/logo/aweskill-badge2.svg" alt="aweskill companion"></a></h1>
  <p><strong>轻量任务走 Flash，复杂决策走 Pro。</strong></p>
  <p>按请求结构信号做确定性路由的同协议透明代理——不猜语义、不用关键词、不跑分类器。支持 Anthropic Messages、OpenAI Chat Completions、OpenAI Responses 三种协议。</p>
  <p>
    <a href="./README.md">English</a> ·
    <strong>简体中文</strong>
  </p>
  <p>
    <a href="https://ko-fi.com/mugpeng"><img src="https://img.shields.io/badge/Ko--fi-Buy%20me%20a%20coffee-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
  </p>
  <p>
    <img src="https://img.shields.io/pypi/v/awerouter?style=flat-square&color=7C3AED" alt="Version">
    <img src="https://img.shields.io/badge/python-%E2%89%A53.9-0EA5E9?style=flat-square" alt="Python">
    <img src="https://img.shields.io/badge/license-MPL--2.0-22C55E?style=flat-square" alt="License">
  </p>
  <p>
    <img src="https://img.shields.io/badge/status-alpha-c96a3d?style=flat-square" alt="Status">
    <img src="https://img.shields.io/badge/install-pip-22C55E?style=flat-square" alt="pip">
    <img src="https://img.shields.io/badge/platform-terminal-334155?style=flat-square" alt="Platform">
    <img src="https://img.shields.io/pypi/dm/awerouter?style=flat-square" alt="Downloads">
    <img src="https://img.shields.io/github/stars/mugpeng/awerouter?style=flat-square" alt="Stars">
  </p>
</div>

> 按结构信号把编码 agent 流量拆分到不同 provider，省钱不降质。同协议透传，不做协议转换。可选的 profile 级 tool-result 压缩（RTK，默认关闭）。

## 支持工具

awerouter 与两个配套工具配合最佳：

- **[aweskill](https://aweskill.webioinfo.top/)** — 面向 AI agent 的 CLI skill 包管理器。安装 awerouter skill，让你的 agent 用自然语言管理路由。
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Agent profile 切换器。用指向 awerouter daemon 的 profile 启动 Claude Code、Codex 或 OpenCode 会话。

aweskill 通过管理skills，让 agent **管理**路由；aweswitch 让你**启动**走路由的会话。配置一次 awerouter，之后就能用 `aweswitch <profile>` 把任意 agent 启动到它上面。

## 安装与使用

### 让 AI agent 安装和配置

如果你在 Claude Code、Codex、Cursor 等 coding agent 中工作，直接告诉它：

```text
Read https://github.com/mugpeng/awerouter/blob/main/README.ai.md and follow it to install and configure awerouter.
```

Agent 会安装 CLI、初始化配置、帮你添加 profile，并通过 [aweskill](https://aweskill.webioinfo.top/) 安装 awerouter skill，用于后续路由管理。

**配置完成后你可以这样告诉 agent：**

> "加一个 stepfun 的 flash provider 和一个 pro profile。"
> "列出我的 awerouter profile。"
> "根据 usage 帮我调一下 longContextThreshold。"
> "解释一下我的 usage savings。"

Agent 可以直接运行只读命令（`list`、`config show`、`usage stats`、`usage calibrate`、`usage savings`）并编辑配置，但**不会**运行 `awerouter serve`（常驻 daemon）、`awerouter add`（交互式向导）、`awerouter restore`（覆盖配置文件）、`awerouter usage clean`（删除日志）或 `awerouter self-update`（升级安装）。要启动 daemon，请在你自己的终端运行：

```bash
awerouter serve cc-router-1
```

#### awerouter skill

通过 [aweskill](https://aweskill.webioinfo.top/) 安装 [awerouter skill](https://github.com/mugpeng/awerouter/blob/main/resources/skills/awerouter/SKILL.md)，可以让 AI agent 用自然语言管理路由：

- 列出、查看、添加、编辑路由 profile
- 分别编辑 `providers.json`（端点/密钥）和 `routing.json`（策略）
- 读取 `usage stats` / `usage calibrate` / `usage savings` 并给出阈值调整建议
- 引导配置 `${ENV_VAR}` 引用所需的环境变量

安装后你可以直接告诉 agent："给 openai-chat 分组加一个 GLM provider"、"把 longContextThreshold 调到 12000"、"看看我的 web_search 流量走哪个 provider"，agent 会读取配置、做修改、用 `awerouter config show` / `awerouter list` 验证。

#### 通过 aweswitch 启动

awerouter 配置好后，用一个指向 daemon 的 aweswitch profile，就能启动走智能路由的编码 agent。

**示例：通过 awerouter 启动 OpenCode**

先在一个终端用 openai-chat profile 启动 daemon：

```bash
awerouter serve oc-router-1
```

然后在 aweswitch 配置里加一个指向它的 OpenCode profile：

```json
{
  "profiles": {
    "opencode": {
      "oc-awerouter": {
        "env": {
          "OPENCODE_BASE_URL": "http://127.0.0.1:20128/v1",
          "OPENCODE_API_KEY": "sk-any-non-empty-value",
          "OPENCODE_NAME": "awerouter",
          "OPENCODE_MODEL": "auto"
        }
      }
    }
  }
}
```

```bash
aweswitch oc-awerouter
```

`OPENCODE_MODEL` 设为 `auto` 时，awerouter 按结构信号逐请求路由——上游 provider 收到的是 `routing.json` destinations 里配置的实际 model id，而不是 `auto`。Claude Code 同理，用一个 `anthropic` profile（`ANTHROPIC_MODEL=auto`）即可。

### 手动安装和使用

从 PyPI 安装：

```bash
pip install awerouter
```

快速开始：

```bash
# 1. 初始化配置（生成 ~/.config/awerouter/{providers,routing}.json）
awerouter init                # 也可选内置搭配：awerouter init step-glm / glm-codex / step-glm-mm（见「常见搭配模版」）

# 2. 交互式添加 profile（自动写入两个文件，保证引用一致）
awerouter add
#    或者手改：编辑 providers.json 填密钥（${ENV_VAR}），编辑 routing.json 映射 flash/pro

# 3. 启动 daemon（只有一个 profile 时名字可省）
awerouter serve [cc-router-1]     # 等价简写：awerouter cc-router-1

# 4. 让 CC 指向它 —— serve 启动横幅会直接打印下面这两行
export ANTHROPIC_BASE_URL=http://127.0.0.1:20128
# aweswitch profile 环境变量：ANTHROPIC_MODEL=auto, _HAIKU_=flash, _OPUS_=pro
```

内置模板源码位于 [`src/awerouter/resources/templates/`](src/awerouter/resources/templates/)；`awerouter init <template>` 会将对应文件生成到你的配置目录。已经有配置了？`awerouter init <template> --merge` 把模板里缺的 provider、profile 和 settings 补进现有配置——已有条目一律不覆盖，profile 重名则跳过，新写入的 `imageModel`/`defaultModel` 会打印警告（它们会改变所有 profile 的路由行为）。

## 配置

`~/.config/awerouter/` 下两个文件（`AWEROUTER_CONFIG_DIR` 环境变量覆盖目录）：

**providers.json** — 端点 + 密钥，按线上协议分组（`config show` 自动脱敏）：

```json
{
  "anthropic": {
    "stepfun":   { "base_url": "https://api.stepfun.com/step_plan", "auth": "${STEPFUN_AUTH_TOKEN}" },
    "anthropic": { "base_url": "https://api.anthropic.com",          "auth": "${ANTHROPIC_KEY}" }
  },
  "openai-chat": {
    "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1", "auth": "${STEPFUN_AUTH_TOKEN}" }
  },
  "openai-responses": {
    "openai": { "base_url": "https://api.openai.com/v1", "auth": "${OPENAI_API_KEY}" }
  }
}
```

支持三种协议。`base_url` 沿用各原生客户端的写法——从客户端配置里原样抄过来即可，awerouter 按原生客户端同样的规则拼接端点路径：

| 协议 id | `base_url` 写法 | 端点 |
|---------|----------------|------|
| `anthropic` | `ANTHROPIC_BASE_URL` 风格（不带 `/v1`） | `base_url + /v1/messages` |
| `openai-chat` | `OPENAI_BASE_URL` 风格（含版本段） | `base_url + /chat/completions` |
| `openai-responses` | `OPENAI_BASE_URL` 风格（含版本段） | `base_url + /responses` |

同一家 provider 的两个协议路径往往不同——比如 GLM：Claude 协议客户端用 `https://open.bigmodel.cn/api/anthropic`，chat completions 是 `https://open.bigmodel.cn/api/coding/paas/v4`，responses 是 `https://open.bigmodel.cn/api/v1`。所以每个协议分组各配各的 `base_url`——这也是多协议 profile 要在每个被服务的分组里都列一份 provider 的原因。

鉴权头**根据 `base_url` 自动判断**：`anthropic.com` → `x-api-key`（裸 token）；其他 → `Authorization`（自动补 `Bearer `）。除非启发式判断错了，否则不需要填 `auth_header`。

### 本地模型（免认证）

本地推理服务不需要密钥——`auth` 直接省略，请求会以无认证头的干净形态发往上游：

```json
{
  "anthropic": {
    "ollama":    { "base_url": "http://127.0.0.1:11434" },
    "anthropic": { "base_url": "https://api.anthropic.com", "auth": "${ANTHROPIC_KEY}" }
  },
  "openai-chat": {
    "ollama": { "base_url": "http://127.0.0.1:11434/v1" }
  }
}
```

任何 OpenAI 兼容服务（Ollama、LM Studio、llama.cpp、vLLM）都能挂在 `openai-chat` 组；Ollama ≥ 0.14 原生支持 Anthropic 协议，可以和 Claude Code 同在 `anthropic` 组。注意路径约定与云端一致：`openai-chat` 的 base_url 带 `/v1` 段，`anthropic` 的不带。

本地和云端在同一个 profile 里随意混排——便宜的活给本地，难啃的给云端：

```json
"destinations": {
  "flash": "ollama,qwen3-coder:30b",
  "pro":   "anthropic,claude-opus-5"
}
```

以 Ollama 为例的端到端部署（flash=本地 / pro=云端）：

```bash
ollama pull qwen3-coder:30b      # 本地服务默认监听 127.0.0.1:11434
awerouter serve cc-router-1
export ANTHROPIC_BASE_URL=http://127.0.0.1:20128
```

常见本地服务的默认端口（都走 `openai-chat`、都免认证）：LM Studio `http://127.0.0.1:1234/v1`、llama.cpp `http://127.0.0.1:8080/v1`、vLLM `http://127.0.0.1:8000/v1`。

本地服务没启动时，flash→pro 回退在连接错误时触发，请求透明地落到云端——本地优先、云端兜底，不需要任何额外配置。

防呆：`auth` 为空但 `base_url` **不在**本机的 provider，serve 启动时会打一行警告（`awerouter add` 向导在同情况下会当场确认）。局域网免认证服务是合法场景——警告只提示、不拦截。

### Codex 账号（订阅登录）

`openai-responses` 组里的 `"auth": "codex"` 表示用本地 Codex CLI 的登录态（`$CODEX_HOME/auth.json`，默认 `~/.codex/auth.json`）代替 API key——订阅自带的模型就能和 key 计费的模型混在同一个 flash/pro 路由里：

```json
"openai-responses": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1", "auth": "${STEPFUN_AUTH_TOKEN}" },
  "codex":   { "base_url": "https://chatgpt.com/backend-api/codex", "auth": "codex" }
}
```

```json
"destinations": {
  "flash": "stepfun,step-router-v1",
  "pro":   "codex,gpt-5.6-luna"
}
```

任何说 Responses 协议的客户端（Codex 本身，或任何能配 OpenAI Responses base URL 的 agent）把 base URL 指到 awerouter、随便填个哑 key 即可；真正的 `Authorization: Bearer <access_token>` 和 `chatgpt-account-id` 头由 awerouter 每个请求现盖。针对后端的几个怪癖会做少量归一化：`store` 强制为 `false`（零数据保留，拒绝 `store: true`）、`max_output_tokens` 直接剥掉（会被拒）、后端没有非流式模式——非流式请求在上游以 SSE 运行，回程收敛成单个 JSON 响应（output 条目从流事件重建），流式/非流式客户端都能直接用。

行为要点：

- **只读登录态，不做刷新。** OpenAI 的 refresh token 是单次有效、旋转式的——在这里刷新会把本地 CLI 的登录踢失效，所以刷新职责永远归 CLI。awerouter 每个请求都重读 `auth.json`，遇到上游 401 还会再重读重试一次（通常是 CLI 刚刷新过）。重读后仍然 401 说明登录真的过期了：flash 请求会兜底到带 key 的 pro（每次兜底打印一行，`usage log` 里带 `401-retry` 标记）；只有 pro 也骑同一个 codex 登录时才把 401 透传给客户端。access token 实测约 10 天有效——照常使用 `codex`（或 awewarm 保温）即可保持登录新鲜。
- **感知系统代理。** codex provider 遵循 `https_proxy`/`all_proxy`（和 Codex CLI 遵循的同一组变量）——chatgpt.com 在很多网络下必须走 shell 代理才通。其他 provider 永远直连，行为不变。
- **模型名会漂移。** `gpt-5-codex`/`gpt-5.1-codex` 已被后端 400 拒绝，当前可用的是 CLI 在用的名字（写作本文时是 `gpt-5.6-luna`）。模型名来自 destination 配置，改名只需改 routing.json 一行。
- **没登录？** `auth.json` 缺失或无效时请求返回 503 并提示 `run: codex login`，serve 启动时也会打一行警告。这里刻意不做兜底（区别于会话中途过期）：登录缺失是配置错误，应该立刻暴露——静默落到付费 pro 会把错误和账单一起藏起来。

该哨兵值只允许出现在 `openai-responses` 组——ChatGPT Codex 后端只说 Responses 协议，进不了 `anthropic`/`openai-chat` 的 profile。

### Claude 账号（订阅登录）

`anthropic` 组里的 `"auth": "claude"` 表示用 Claude Pro/Max 订阅登录作为上游——而且这个登录由 awerouter 自己持有：本机**不需要**（也不会借用）Claude Code CLI 的登录态，`awerouter login claude` 走的就是 Claude Code CLI 同款 PKCE 设备授权流程，token 存在 `~/.config/awerouter/claude-auth.json`（权限 0600）。订阅自带的模型就这样和 key 计费的模型混进同一个 flash/pro 路由：

```json
"anthropic": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan", "auth": "${STEPFUN_AUTH_TOKEN}" },
  "claude":  { "base_url": "https://api.anthropic.com", "auth": "claude" }
}
```

```json
"destinations": {
  "flash": "stepfun,step-router-v1",
  "pro":   "claude,claude-opus-4-5"
}
```

```bash
awerouter login claude    # 打开浏览器授权，把回调页显示的 code 粘回来
awerouter logout claude   # 删除本地登录
```

任何说 Anthropic 协议的客户端把 base URL 指到 awerouter、随便填个哑 key 即可（Claude Code 设 `ANTHROPIC_BASE_URL`——CLI 自己的登录完全不受影响，每次 OAuth 登录都是独立会话）。真正的 `Authorization: Bearer <access_token>` 和 OAuth 必需的 `anthropic-beta: oauth-2025-04-20` 标记由 awerouter 每个请求现盖，请求体不做任何改写。行为要点：

- **刷新归 awerouter。** 和 codex 的只读设计正好相反：这个登录属于 awerouter，所以由它刷新——access token 只有几小时有效，用旋转式 refresh token 自动续期，新 token 原子落盘后请求才继续。进程内锁 + 锁下重读避免并发请求重复刷新；另一个 awerouter 进程抢先刷新也能恢复（刷新被拒 + 文件已变 → 直接用赢家的 token）。
- **401 处理与 codex 对称。** 上游 401 先强制刷新重试同一 destination 一次；重试后仍然 401 说明登录失效——flash 请求兜底到带 key 的 pro（每次兜底打印一行，`usage log` 里带 `401-retry` 标记），只有 pro 也骑同一个 claude 登录时才把 401 透传。登录缺失返回 503 并提示 `run: awerouter login claude`，serve 启动时同样打警告——和 codex 一样刻意不做兜底。
- **感知系统代理。** 和 codex provider 一样遵循 `https_proxy`/`all_proxy`——api.anthropic.com 和 platform.claude.com 在很多网络下必须走 shell 代理。
- **线协议会漂移，注意 ToS。** 端点（client id、`platform.claude.com` 授权/换 token，旧的 `console.anthropic.com` 作为 404/405 回退）和头集合都是社区共用的逆向公开契约，随时可能失效；且 Anthropic 2026 年的政策限制第三方工具使用订阅 OAuth token——这是骑你自己的订阅，风险自担。

该哨兵值只允许出现在 `anthropic` 组——订阅后端说的是 Messages 协议。

### 常见搭配模版

`awerouter init` 支持内置模板名，一次生成配套的 `providers.json` + `routing.json`（不传名字即 `default`）。下面三套开箱即用；不想跑命令的话，手抄任意一段到自己的配置里也一样。密钥一律 `${ENV_VAR}` 占位，缺失的环境变量在启动时报错。想把模板并进已有配置，加 `--merge`：只补缺失项，已有的内容一律不碰。

**step-glm** —— 纯 API key 的国产双档：flash 走 StepFun step_plan，pro 走 GLM coding plan。面向说 openai-chat 协议的 agent：

```json
"openai-chat": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1",        "auth": "${STEPFUN_AUTH_TOKEN}" },
  "glm":     { "base_url": "https://open.bigmodel.cn/api/coding/paas/v4", "auth": "${GLM_API_KEY}" }
}
```

```json
"destinations": {
  "flash": "stepfun,step-3.7-flash",
  "pro":   "glm,glm-5.3"
}
```

```bash
awerouter init step-glm      # 需要设置 STEPFUN_AUTH_TOKEN 和 GLM_API_KEY
```

**glm-codex** —— GLM coding plan 消化 flash 流量，ChatGPT 订阅（`"auth": "codex"`，见上文）消化 pro：

```json
"openai-responses": {
  "glm":   { "base_url": "https://open.bigmodel.cn/api/v1",       "auth": "${GLM_API_KEY}" },
  "codex": { "base_url": "https://chatgpt.com/backend-api/codex", "auth": "codex" }
}
```

```json
"destinations": {
  "flash": "glm,glm-5.3-flash",
  "pro":   "codex,gpt-5.6-terra"
}
```

```bash
awerouter init glm-codex     # 需要 GLM_API_KEY，且 codex login 登录过 ChatGPT 订阅
```

**step-glm-mm** —— 多模态侧翼，不做智能分流：非多模态旗舰（GLM coding plan 的 glm-5.3）包揽全部主要工作，只有带图的请求交给多模态 flash（StepFun step-3.7-flash）。厂商与 step-glm 相同，反转全靠 settings。双协议（`["anthropic", "openai-chat"]`）：一个 serve 实例在同一端口同时接 Claude Code *和* openai-chat 系 agent——每种协议走自己的 provider 条目：

```json
"anthropic": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan",      "auth": "${STEPFUN_AUTH_TOKEN}" },
  "glm":     { "base_url": "https://open.bigmodel.cn/api/anthropic", "auth": "${GLM_API_KEY}" }
},
"openai-chat": {
  "stepfun": { "base_url": "https://api.stepfun.com/step_plan/v1",        "auth": "${STEPFUN_AUTH_TOKEN}" },
  "glm":     { "base_url": "https://open.bigmodel.cn/api/coding/paas/v4", "auth": "${GLM_API_KEY}" }
}
```

```json
"settings": {
  "imageModel": "flash",
  "defaultModel": "pro"
}
```

```json
"cc-router-1": {
  "protocol": ["anthropic", "openai-chat"],
  "destinations": {
    "flash": "stepfun,step-3.7-flash",
    "pro":   "glm,glm-5.3"
  }
}
```

```bash
awerouter init step-glm-mm        # 需要设置 STEPFUN_AUTH_TOKEN 和 GLM_API_KEY
# Claude Code:    export ANTHROPIC_BASE_URL=http://127.0.0.1:20128        （不带 /v1）
# openai-chat:    export OPENAI_BASE_URL=http://127.0.0.1:20128/v1       （带 /v1）
```

`imageModel: flash` 把图片护栏改指多模态模型（它的优先级高于档位标签和长文本——pro 看不了的图绝不能送到 pro）；`defaultModel: pro` 翻转了默认兜底（原本 cost-first 落 flash），于是所有纯文本请求都走旗舰。后台档任务仍走 flash。想只用一家？把 flash 改成 GLM 自家的多模态 `glm-5.3-flash`（`https://open.bigmodel.cn/api/v1`）——每个协议组各改一行。

后端模型名会漂移（见「Codex 账号」一节）——改名只需动 routing.json 一行。

**routing.json** — 路由策略，不含密钥（可以进 git）：

```json
{
  "settings": {
    "backgroundModel": "flash",
    "thinkModel": "pro",
    "toolRouting": {
      "webSearch": "pro",
      "edit": "pro"
    },
    "longContextAuto": {
      "percentile": 95,
      "windowDays": 7,
      "minSamples": 50,
      "fallbackThreshold": 8000
    }
  },
  "cc-router-1": {
    "protocol": "anthropic",
    "port": 20128,
    "longContextThreshold": 8000,
    "destinations": {
      "flash": "stepfun,step-3.7-flash",
      "pro":   "anthropic,claude-opus-5"
    }
  },
  "cc-pro-first": {
    "protocol": "anthropic",
    "longContextThreshold": 8000,
    "destinations": {
      "flash": "stepfun,step-3.7-flash",
      "pro":   "anthropic,claude-opus-5"
    },
    "defaultModel": "pro"
  }
}
```

`settings` 可省（默认 `flash`/`pro`）。它定义 CC 发送的档位 model id：background（Haiku 档）、think（Opus 档）；所有按工具路由的规则（含 L1 的 `webSearch`）统一放在 `settings.toolRouting`——旧顶层 `webSearchModel` 仍作为兜底兼容。`imageModel` 重定向图片护栏（默认 `pro`；旗舰不支持多模态时改 `flash`，见 step-glm-mm 模版），`defaultModel` 翻转兜底去向（默认 `flash`；pro 优先的配置改 `pro`）。主循环用 `auto`——由 L3 按难度路由。在 aweswitch profile 里设：`ANTHROPIC_DEFAULT_HAIKU_MODEL=flash`、`ANTHROPIC_MODEL=auto`、`ANTHROPIC_DEFAULT_OPUS_MODEL=pro`。

settings 的每个键也都可以**直接写在 profile 体内**，与 `protocol`/`destinations` 平级（上面的 `cc-pro-first` 只翻转了 `defaultModel`），且只对这一个 profile 生效。缺的键——包括 `toolRouting`/`longContextAuto` 里缺的字段——逐键继承全局 `settings`，所以每个 profile 只调自己不同的部分。`config show <profile>` 会打印该 profile 的生效值（覆盖键平铺在条目里），serve 横幅用一行 `overrides -> ...` 列出覆盖项。

全部 settings 键、默认值与作用（每个键都既可全局配置、也可在 profile 里配置）：

| 键 | 取值 | 默认 | 作用 |
|----|------|------|------|
| `backgroundModel` | model id（如 `flash`、`c1/flash`） | `flash` | L2：带此档位标签的请求走 flash |
| `thinkModel` | model id | `pro` | L2：带此档位标签的请求走 pro |
| `webSearchModel` | `flash` / `pro` | `pro` | L1：声明 `web_search` 工具的请求去向（旧键——设了 `toolRouting.webSearch` 时以它为准） |
| `imageModel` | `flash` / `pro` | `pro` | L1：带图请求去向（能力护栏——优先级高于档位和长度） |
| `defaultModel` | `flash` / `pro` | `flash` | 所有层都不匹配时的兜底去向 |
| `searchResultDiscount` | 0–1 数字 | `0.3` | L3：文件搜索（Grep/Glob/LS）结果 token 的权重；`1` = 关闭 |
| `toolRouting.webSearch` | `flash` / `pro` / `null` | `null` | 覆盖 `webSearchModel` 的 web_search 护栏去向 |
| `toolRouting.edit` | `flash` / `pro` / `null` | `pro` | L4：代码刚被修改后的那一轮去向；`null` 关闭该检查点 |
| `longContextAuto.percentile` | 1–99 | `95` | `"auto"` 阈值取 L3 分布的哪个分位 |
| `longContextAuto.windowDays` | ≥ 1 | `7` | 自动校准的回看窗口（天） |
| `longContextAuto.minSamples` | ≥ 1 | `50` | 窗口内 L3 样本不足此数时用兜底阈值 |
| `longContextAuto.fallbackThreshold` | ≥ 0 | `8000` | 样本不足时的阈值（serve 解析 `"auto"` 前也用它） |

`backgroundModel`/`thinkModel` 填的是自由格式的 model id（客户端实际发送的档位名），不是 `flash`/`pro`。未知键——无论写在 `settings` 还是 profile 体内——加载时直接报错并指明是哪个键，拼错不会静默继承全局值。

`longContextThreshold` 可以是整数，也可以写 `"auto"`：每次 `serve` 启动时，awerouter 取该 profile 自己最近 `windowDays` 天 L3 有效 token 分布的 `percentile` 分位值作为阈值。窗口内 L3 请求数不足 `minSamples`（新 profile、流量清淡）时改用 `fallbackThreshold`。四个参数都在 `settings.longContextAuto` 里，全部可选——横幅每次都会打印选了什么、依据是什么。注意：分位值决定的是 flash/pro 的*分配比例*，不代表 flash 的能力上限——如果你的 flash 模型在超长上下文上明显退化，请继续用固定阈值。

密钥用 `${ENV_VAR}` 引用。缺失的环境变量在启动时报错退出。

> **基于 profile 的路由：** `routing.json` 用 profile id 分组（类似 aweswitch）。`awerouter serve <profile>` 启动其中一个；只有一个 profile 时自动选择。`protocol` 字段把 profile 映射到 providers.json 的分组，并决定它服务哪个端点——serve 横幅按协议打印对应客户端的环境变量（anthropic → Claude Code 的 `ANTHROPIC_BASE_URL`；openai 协议 → `OPENAI_BASE_URL` / Codex `wire_api`）。它可以写单个 id，也可以写列表：`"protocol": ["anthropic", "openai-chat"]` 让一个端口同时服务两种线协议——客户端按端点路径自选（`/v1/messages` 还是 `/v1/chat/completions`），每种协议走自己的 provider 组，且每个 destination provider 必须在每个被服务分组里都存在（各自协议的 `base_url`）。注意：openai 客户端是单 model 配置，L2 档位匹配基本不触发——openai 流量走 L1 + L3，默认 flash。

> **端口分配：** 可选的 `port` 字段为 profile 固定监听端口（`awerouter list` 会显示）；优先级：`--port` 参数 > profile `port` > 默认 20128。显式指定的端口被占用时直接报错退出——客户端写死了它，不能悄悄漂移。不配置端口时，serve 从 20128 起向上找第一个空闲端口：第一个实例拿 20128，下一个 20129，依次顺延——按启动顺序分配，与 profile 无关。一次只跑一个实例的热切换用法：profile 不配端口、客户端固定指向 20128 即可。

## 路由逻辑

first-match-wins 管线，逐请求评估：

| 层 | 信号 | 决策 |
|----|------|------|
| L1 能力护栏 | body 含 `web_search` 工具；含图片内容 | `toolRouting.webSearch`（默认 **pro**；旧顶层 `webSearchModel` 仍兼容）；`settings.imageModel`（默认 **pro**） |
| L2 档位匹配 | `model == c1/flash` 或 `c1/think` | flash / pro |
| L3 难度评分 | token（全部请求内容）超阈值 | **pro**；否则继续 |
| L4 编辑检查点 | 尾部工具批次改写了代码（`edit`/`write`/`apply_patch` 等） | `toolRouting.edit`（默认 **pro**，`null` 关闭） |

CC 的 `/model` 选择器设置 tier model id（c1/flash / c1/pro / c1/think）。awerouter 直接读取该字段做路由——不猜语义、不用关键词、不跑分类器。图片护栏是能力规则而非难度猜测：排在档位标签和长文本之上，`imageModel: flash` 时带图请求无论档位多高、上下文多长都到多模态模型（看不见图的模型绝不能收到图）。所有层都不匹配的请求落到 `settings.defaultModel`（默认 flash——cost-first）。

L4 是后果检查点，不是难度猜测。结构信号看不到*决定*编辑的那一轮——那一轮按它之前的信号路由——但代码刚被改写的**下一轮**是审查轮（验证、继续、交代），所以送 pro：flash 起草，pro 审查。信号取**尾部并行批次**：其中任何一个编辑类调用都会标记该批次（`[Grep, Edit]` 和 `[Edit, Grep]` 结果一致）。shell 包装的调用（codex 的 `exec_command`/`shell`）按命令文本分类——`apply_patch` 算编辑。它排在 L3 之下是刻意的——已超过 `longContextThreshold` 的会话无论刚跑了什么工具都留在 pro，flash 不会拿到可能退化的超长上下文，长上下文这一跨越也保持 flash→pro 单向（阈值以下：编辑检查点轮次走 pro，其余轮次回落 flash）。编辑类覆盖 `Edit`/`Write`/`NotebookEdit`/`apply_patch`/`replace_in_file` 等，大小写不敏感匹配。早期版本在这里还把搜索/机械阶段路由到 flash；由于 flash 本来就是兜底默认，这些规则不改变任何行为，v0.4.8 已移除。

所有按工具路由的规则（含 L1 的 `webSearch`）统一放在 `settings.toolRouting`（`webSearch`/`edit`），serve 横幅用一行 `tool -> ...` 打印生效的映射。

## Token Saver（RTK 省流）

> **⚠️ 试验性功能——所以默认关闭。** 压缩是有损的：超长文件读取只保留头尾 + 函数签名等骨架行（截断标记会注明 offset,模型可据此重读中段）;grep 每文件最多保留 10 条命中;diff 有行数上限。格式识别是启发式的，偶尔会在特殊内容上误判造成信息损失——模型通常会察觉并重读，代价是多一轮。如果发现 agent 行为异常(反复重读同一批文件、漏掉细节),关掉 RTK 或对该会话发送 `X-Awerouter-Token-Saver: off`。实际省了多少可用 `awerouter usage log` 查看。

编码 agent 每轮都重发全部对话历史，其中大头是工具输出——git diff、grep 命中、目录列表、构建日志。profile 可以开启 RTK 压缩，在路由和转发之前原位改写这些文本：

```json
"cc-router-1": {
  "protocol": "anthropic",
  "longContextThreshold": 8000,
  "rtk": true,
  "destinations": { "flash": "stepfun,step-3.7-flash", "pro": "anthropic,claude-opus-5" }
}
```

- **只动 tool result：** 仅压缩 `tool_result` / tool 消息内容，绝不碰用户 prompt 和模型回复。规则式 filter（git diff/status/log、grep、find、tree、ls、构建输出等）自动识别格式并压缩；无法识别的内容、500 字符以下的短输出、错误结果（`is_error`）原样放行。
- **fail-open：** 任何失败（异常、filter 报错）都保持 body 原样，绝不会弄坏请求。注意这只防崩溃，不防启发式误判（见上面的警告）。
- **确定性：** 同样的历史每轮压出同样的字节，provider 的 prompt cache prefix 不会失效。
- **请求级逃生口：** 发送 `X-Awerouter-Token-Saver: off` 可让单个请求不压缩转发（排障、需要完整 diff/日志时用）。
- 压缩发生在路由之前，`/v1/messages/count_tokens` 同样压缩，因此 L3 决策和用量日志与实际计费一致。开启 RTK 后建议重跑 `usage calibrate`——按未压缩流量校准的阈值会过多地触发 pro（`"auto"` 在窗口期后自愈）。

压缩算法设计源自 [rtk](https://github.com/rtk-ai/rtk)（Apache 2.0）及 [9router](https://github.com/decolua/9router) 的 JS 移植版（MIT），本模块为 Python 从零重构版；请求日志会记录每个请求估算省下的 token。

## 命令

```bash
awerouter init [TEMPLATE]             # 从内置模板创建配置（default / step-glm / glm-codex / step-glm-mm）；--merge 把模板补进已有配置
awerouter add                         # 交互式添加 profile（先选类别再选 provider）
awerouter list                        # 列出 profile（名字、协议、端口、flash、pro、阈值）
awerouter serve [PROFILE] [--port N] [--host 127.0.0.1]  # 端口优先级：--port > profile 'port' > 20128
awerouter <PROFILE>                   # serve 的简写
awerouter restore [providers|routing] # 从 .bak 备份恢复配置文件
awerouter self-update [--check]        # 升级到最新 PyPI 版本（--check：只看版本不升级）
awerouter config path                 # 打印两个配置文件路径
awerouter config show [PROFILE]       # 脱敏全量配置；带 PROFILE 只看它的 provider 和条目
awerouter config edit [providers|routing]  # 在 $EDITOR 中打开某个文件（先备份 .bak）
awerouter usage stats
awerouter usage clean                 # 删除已保存的请求日志（需确认）
awerouter usage log [--lines 20] [--all] [--tokens]
awerouter usage tokens
awerouter usage calibrate
awerouter usage savings
```

所有 `usage` 子命令读的是同一份请求日志。`log`、`stats`、`tokens`、`calibrate` 和 `savings` 直接接受 `--since`（`today`、`yesterday`、`7d` 或 `YYYY-MM-DD`，本地时间）和 `--profile`——例如 `awerouter usage stats --since today --profile cc-1`；`clean` 删除全部日志，不接受窗口选项。

`usage stats` 按 profile 汇总：label/destination/provider/model 分组（带百分比）、错误与降级计数、各 destination/provider/model 的延迟分位数（首字节与总时长）、估算请求 token（全部请求内容：messages、system prompt、工具定义与工具 I/O）。`--since` 接受 `today`、`yesterday`、`7d` 或 `YYYY-MM-DD`（本地时间）；`--profile` 只看单个 profile。`usage clean` 确认后删除已保存的日志（`requests.jsonl` 及轮转备份）。`usage log` 原样显示条目——默认最后 20 条，加 `--all` 显示全部；codex 登录重读重试过的请求带 `401-retry` 标记；`--tokens` 把 status/延迟/入站 model 三列换成每条请求的分类型 token 明细（`msg/sys/tools/results/calls/think`），分类型计数之前记录的条目只显示总数。

`config edit` 和 `add` 向导在每次写入前把目标文件快照为 `<名称>.json.bak`；`awerouter restore [providers|routing]` 确认后把备份拷回并校验恢复后的配置。`config path` 打印两个配置文件路径；`config show [PROFILE]` 显示脱敏全量配置，或单个 profile 用到的 provider 与路由条目。

`self-update` 升级已安装的包——pipx 安装走 `pipx upgrade awerouter`，其余走 `pip install --upgrade`；升级后需重启运行中的 serve。每条命令还会在后台线程检查 PyPI（至多一天一次，缓存在配置目录的 `update-check.json`），发现新版本时在命令结束后输出一行提醒——提醒同样一天至多一次；`AWEROUTER_NO_UPDATE_CHECK=1` 可完全关闭检查。serve 启动横幅也会基于缓存检查结果显示更新提示。

`usage calibrate` 展示 L3 流量（受阈值影响的层）的请求 token 分布（统计全部请求内容：messages、system prompt、工具定义与工具 I/O），并在 p90/p95/p99 处建议 `longContextThreshold` 候选值，末尾给出按 `settings.longContextAuto` 策略 `"auto"` 会选的值。跑一段真实流量后执行，再编辑 `routing.json`，或把 profile 改成 `"auto"` 交给 serve 每次启动时自动校准。

`usage tokens` 按内容类型（messages、system prompt、工具定义、工具结果、工具调用参数、thinking）汇总输入 token 的总量与占比——可以看出请求 token 里多少是环境常量（system prompt + 工具定义）、多少是真实对话。

`usage savings` 是 token 记账视图：各档消化了多少输入请求 token、相对「全部直连 pro」的基线卸载了多少 pro 输入 token。cache sensitivity 小节给出卸载量的上下界（Anthropic 体系按缓存读 ~0.1×、写 ~1.25×、TTL 5 分钟折算），并展示你的换档节奏与 TTL 的关系——pro-only 基线若缓存常热，那些 token 本会按缓存读价计费。输出末尾给出代入式金额公式（token 数为实测值）——把你的输入单价（每百万 token）代入 pro/flash 即可直接算出节省金额（输出 token、flash 侧缓存、能力错配导致的额外轮次均未建模）。

## 故障排查

**CC 启动后立刻报 `502 status code (no body)`** —— shell 代理（Clash 等）劫持了回环流量。发往 `127.0.0.1:20128` 的请求被送进代理，而代理的 `127.0.0.1` 是它自己，端口上没人监听，代理就返回空的 502。`serve` 检测到这种情况会在启动时打印警告；在 shell 配置里豁免回环地址即可：

```bash
export no_proxy=127.0.0.1,localhost NO_PROXY=127.0.0.1,localhost
```

然后开新终端、重新启动 CC。

## 开发

```bash
git clone https://github.com/mugpeng/awerouter
cd awerouter
pip install -e ".[dev]"
pytest
```

架构说明、配置语义和发布流程见 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## 赞助与支持

如果 awerouter 帮你省了钱，欢迎支持一下：

- ⭐ 给项目点个 Star — 让更多人看到它。
- ☕ [Ko-fi](https://ko-fi.com/mugpeng) — 请我喝杯咖啡。
- 💬 微信 — 扫描下方收款码。

<p align="center">
  <img src="assets/images/wechat-pay.jpg" alt="微信收款码" width="240">
</p>

> awerouter 是免费开源的，你的支持让它持续维护下去 — 谢谢。

## Awesome 软件生态

awerouter 是一个不断壮大的 "awesome" 工具家族中的一员 — 围绕 AI 编程 agent 打造，local-first、可被 agent 直接操作。

### CLI 工具

- **[aweskill](https://aweskill.webioinfo.top/)** — CLI 优先的技能包管理器，支持 47+ AI 编程 agent。
- **[aweswitch](https://github.com/Webioinfo01/aweswitch)** — Claude Code、Codex、OpenCode 的 agent 配置切换器。
- **[awerouter](https://github.com/mugpeng/awerouter)** — 智能路由器，用结构信号把请求分给 Flash 或 Pro 模型，减少不必要的模型开销。
- **[aweshelf](https://github.com/Webioinfo01/aweshelf)** — 收藏、分类、恢复 AI 编程会话，还能搭配 aweswitch 实现保存配置，一键启动。
- **[aweshare](https://github.com/wehuman01/aweshare)** — 通过自建 Hub 共享本地 Ollama/vLLM，或国产厂商 coding plan，或已授权的 OpenAI/Anthropic 帐号订阅，实现 token 的共享经济。
- **[awewarm](https://github.com/wehuman01/awewarm)** — 订阅窗口保持器，让 AI 编程套餐的窗口持续激活，无论是本地设置，还是通过远程连接的服务器。
- **[awescholar](https://github.com/Webioinfo01/awescholar)** — AI agent 可自主执行的科学文献发现与策展，搜索、标注、筛选和报告学术论文。

### 桌面应用

- **[awedot](https://awedot.wehuman.top/)** — 悬浮球驻留屏幕边缘，实时追踪当前 AI 会话；一键收藏、随时恢复，并可搭配 aweswitch 固定 agent 配置（比如用 GLM 模型启动）。

### Project Collections

- **[Awesome AI Meets Biology](https://github.com/Webioinfo01/Awesome-AI-Meets-Biology)** — AI 在生物学、生物信息学和生物医学研究中应用的精选综述。由 awescholar 驱动。
- **[Awesome AI Virtual Tumor](https://github.com/Webioinfo01/Awesome-AI-Virtual-Tumor)** — 面向虚拟肿瘤建模与仿真的前沿 AI 系统精选合集：静态模型、动态模型、agent、基准与综述。
