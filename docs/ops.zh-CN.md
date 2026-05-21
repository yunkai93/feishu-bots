[English](ops.md) | [简体中文](ops.zh-CN.md)

# 运维操作

命令在仓库根目录执行：

```bash
cd /home/wuchao/ai/feishu-bots
```

## 服务代号

- `chat`：`chat-bot.service`
- `brief`：`briefing-bot.timer` 和 `briefing-bot.service`
- `all`：两个服务一起

## 常用命令

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

## 直接调用脚本

这些 `make` 命令底层调用的是仓库根目录脚本：

```bash
./svc on chat
./svc off brief
./svc status all
./svc run-brief
```

## 说明

- `chat` 控制常驻的飞书回复服务。
- `brief` 控制定时早报。`make run-brief` 用于立刻手动跑一次早报。
- 需要权限时，这些命令会自动使用 `sudo`。
