[English](deployment.md) | [简体中文](deployment.zh-CN.md)

# Deployment

1. Create a Python virtual environment at the repository root.
2. Install dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env` and fill in the Feishu and output settings.
4. Run `briefing-bot/scripts/run_briefing.py` to test generation.
5. Run `chat-bot/scripts/feishu_reply.py` to test Feishu event handling.
6. Install the systemd units from the repository-level `systemd/` directory.

Bootstrap command:

```bash
briefing-bot/scripts/setup_env.sh
```

The repository includes separate services for:

- scheduled briefing generation
- long-running Feishu message reply handling
