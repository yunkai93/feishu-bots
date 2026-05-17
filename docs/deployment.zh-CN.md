[English](deployment.md) | [简体中文](deployment.zh-CN.md)

# 部署说明

1. 在仓库根目录创建 Python 虚拟环境。
2. 安装 `requirements.txt` 里的依赖。
3. 把 `.env.example` 复制为 `.env`，填写飞书与输出目标配置。
4. 运行 `briefing-bot/scripts/run_briefing.py` 验证早报生成。
5. 运行 `chat-bot/scripts/feishu_reply.py` 验证飞书事件接收与回复。
6. 安装仓库根目录 `systemd/` 下的服务模板。

初始化环境可以直接执行：

```bash
briefing-bot/scripts/setup_env.sh
```

仓库提供两类服务：

- 定时早报生成
- 常驻飞书消息回复
