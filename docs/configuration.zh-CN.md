[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# 配置说明

把根目录 `.env.example` 复制为 `.env`，然后至少填写：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_CHAT_ID`
- `BRIEFING_OUTPUT_REMOTE_URL`
- `BRIEFING_OUTPUT_FILE_PATH`
- `BRIEFING_OUTPUT_TITLE`
- `BRIEFING_OUTPUT_WEB_URL`
- `BRIEFING_PUBLISH_REMOTE`
- `BRIEFING_PUBLISH_BRANCH`
- `BRIEFING_GIT_PUSH`
- `CHAT_BOT_SANDBOX_DIR`

`briefing-bot` 会把生成后的 markdown 推送到你配置的 Git 远端仓库，并写入指定文件路径。

`chat-bot` 会把每个用户的会话与日志保存在自己的运行目录里，并通过只读 Codex 沙箱提供纯问答能力。

飞书应用侧还需要确认：

- 已开启机器人能力
- 已具备发送消息权限
- 已具备接收消息事件权限
- 已订阅 `im.message.receive_v1`
- 事件订阅方式使用长连接
