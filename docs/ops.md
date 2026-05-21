[English](ops.md) | [简体中文](ops.zh-CN.md)

# Operations

Run commands from the repository root:

```bash
cd /home/wuchao/ai/feishu-bots
```

## Service aliases

- `chat`: `chat-bot.service`
- `brief`: `briefing-bot.timer` and `briefing-bot.service`
- `all`: both services

## Common commands

```bash
make on chat
make off chat
make status chat

make on brief
make off brief
make status brief

make on all
make off all
make status all

make run-brief
```

## Direct script usage

The Make targets call the repository-level helper script:

```bash
./svc on chat
./svc off brief
./svc status all
./svc run-brief
```

## Notes

- `chat` controls the long-running Feishu reply service.
- `brief` controls the daily timer. `make run-brief` triggers one immediate briefing run.
- These commands use `sudo` when needed.
