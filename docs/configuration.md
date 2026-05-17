[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# Configuration

Copy the root `.env.example` to `.env` and set:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_CHAT_ID`
- `BRIEFING_OUTPUT_REPO_PATH`
- `BRIEFING_OUTPUT_FILE_PATH`
- `BRIEFING_OUTPUT_TITLE`
- `BRIEFING_OUTPUT_WEB_URL`
- `BRIEFING_PUBLISH_REMOTE`
- `BRIEFING_PUBLISH_BRANCH`
- `BRIEFING_GIT_PUSH`
- `CHAT_BOT_SANDBOX_DIR`

`briefing-bot` writes the generated markdown to the configured output repository and file path.

`chat-bot` stores per-user sessions and logs under its own runtime directories and uses a read-only Codex sandbox for Q&A.

Feishu app setup also needs:

- bot capability enabled
- message send permission
- message receive permission
- event subscription for `im.message.receive_v1`
- long connection enabled for the event delivery mode
