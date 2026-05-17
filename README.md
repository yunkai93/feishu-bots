[English](README.md) | [简体中文](README.zh-CN.md)

# Feishu Bots

`feishu-bots` is an open-source self-hosted repository for two focused Feishu bot products:

- `briefing-bot`: collect, distill, publish, and push a daily AI briefing
- `chat-bot`: provide private-chat Q&A with isolated per-user sessions and logs

The repository is structured as a real product codebase rather than a personal automation dump. Runtime secrets, logs, sessions, and caches stay out of Git.

## Prerequisites

- Python 3.11+
- Git
- Codex CLI available on the server
- A Feishu custom app with bot capability enabled

## Products

### briefing-bot

`briefing-bot` fetches curated AI, agent, model, and design-media updates, generates a concise daily briefing, writes the result to a configurable markdown target, optionally pushes it to Git, and sends a Feishu card to a group.

See [briefing-bot/README.md](briefing-bot/README.md).

### chat-bot

`chat-bot` handles Feishu message events and supports private Q&A mode. Each user gets an isolated session file and log. The bot is intentionally limited to read-only conversational behavior and has no server-control capability.

See [chat-bot/README.md](chat-bot/README.md).

## Repository Layout

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

## Documentation

- [Configuration](docs/configuration.md)
- [Deployment](docs/deployment.md)
- [中文文档入口](README.zh-CN.md)

## Language Switching

This repository uses separate English and Simplified Chinese markdown files. Each main document includes a language switch link at the top so the reader can move between the two versions directly on GitHub.

## Runtime Policy

This repository never commits:

- `.env`
- logs
- runtime state
- virtual environments
- caches

## License

MIT
