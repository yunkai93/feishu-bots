[English](README.md) | [简体中文](README.zh-CN.md)

# Feishu Bots

`feishu-bots` 是一个面向开源发布的自托管飞书机器人仓库，目前包含两个独立产品：

- `briefing-bot`：采集、生成、发布并推送每日 AI 早报
- `chat-bot`：提供私聊问答，支持每个用户独立会话与日志

这个仓库按正式产品代码库来组织，不是个人脚本堆。运行时密钥、日志、会话状态、缓存都不会进 Git。

## 运行前置

- Python 3.11+
- Git
- 服务器上可用的 Codex CLI
- 已开启机器人能力的飞书自建应用

## 产品

### briefing-bot

`briefing-bot` 会抓取精选 AI、Agent、大模型与设计媒体资讯，生成简洁早报，写入可配置的 markdown 目标文件，可选推送到 Git，并把同样的内容通过飞书卡片发到群里。

见 [briefing-bot/README.md](briefing-bot/README.md)。

### chat-bot

`chat-bot` 负责飞书消息事件接入与私聊问答。每个用户都有独立会话文件和独立日志。机器人被明确限制为纯问答模式，不提供服务器控制能力。

见 [chat-bot/README.md](chat-bot/README.md)。

## 仓库结构

```text
feishu-bots/
├── briefing-bot/
├── chat-bot/
├── shared/
├── systemd/
├── docs/
├── .env.example
├── requirements.txt
└── LICENSE
```

## 文档

- [配置说明](docs/configuration.zh-CN.md)
- [部署说明](docs/deployment.zh-CN.md)
- [路线图](docs/roadmap.zh-CN.md)
- [English Docs](README.md)

## 文档语言切换

仓库采用英文、简体中文两套 markdown 文件。每份主文档顶部都提供语言切换链接，直接在 GitHub 页面内即可切换。

## 运行时规则

这个仓库不会提交：

- `.env`
- 日志
- 运行状态
- 虚拟环境
- 缓存

## License

MIT
