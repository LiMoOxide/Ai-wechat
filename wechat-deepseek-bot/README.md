# WeChat DeepSeek Bot

把 DeepSeek 接入个人微信，做成能聊天的 AI 机器人。

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-informational)
![License](https://img.shields.io/badge/license-MIT-green)

一条消息进来 → DeepSeek 生成回复 → 自动发回微信。支持私聊直接对话、群聊 `@` 触发，每个会话独立记忆上下文。

---

## 为什么又造一个轮子

网上主流的微信机器人方案（如 `chatgpt-on-wechat`）大多依赖 **hook / 注入**客户端进程。这条路现在基本走不通了：

| 方案 | 依赖的微信版本 | 现状 |
| --- | --- | --- |
| ntchat（注入 WeChatWin.dll） | 3.6.0.18 | ❌ 该版本已被腾讯禁止登录，改号伪装会触发客户端自校验直接崩溃 |
| wxauto（UIAutomation） | 3.9.x | ❌ 3.9.x 也已被纳入低版本拦截；且项目 2025-10 归档停更 |
| wxauto 用于 4.x | 4.0+ | ❌ 微信 4.1.12+ 改用 Qt 自绘，无障碍节点全部消失，控件树里连输入框都找不到 |
| **本项目（wechatauto-replica）** | **4.1.12+（推荐 4.1.15.53）** | ✅ 可用 |

本项目的绕法：**不碰界面结构**。读消息靠解密微信本地数据库（SQLCipher 4），发消息才短暂驱动界面。因此只要微信不改数据库结构，界面怎么重绘都不受影响。

> 详细的版本踩坑过程见 [docs/wechat-version-guide.md](docs/wechat-version-guide.md)。

## 环境要求

- Windows 10 / 11
- **64 位** Python 3.9+（32 位无法读取 64 位微信进程，会报错）
- 微信 Windows 客户端 **4.1.12+**（官方最新版即可，[下载](https://pc.weixin.qq.com/)）

## 快速开始

```bash
# 1. 准备环境
git clone https://github.com/你的用户名/wechat-deepseek-bot.git
cd wechat-deepseek-bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. 建配置文件并填 Key
copy config.example.json config.json
```

编辑 `config.json`，把 `deepseek_api_key` 换成你的 Key（在 [platform.deepseek.com](https://platform.deepseek.com) 创建）：

```json
{
  "deepseek_api_key": "sk-你的Key",
  "self_nickname": "你的微信昵称",
  ...
}
```

```bash
# 3. 体检（微信需已登录并在运行）
python -m wechatauto doctor

# 4. 启动
python bot.py
```

Windows 用户也可以直接双击 `start.bat`（启动）、`check.bat`（体检）。

## 配置项

复制 `config.example.json` 为 `config.json` 后修改：

| 字段 | 说明 |
| --- | --- |
| `deepseek_api_key` | DeepSeek API Key，必填 |
| `model` | `deepseek-chat`（快）或 `deepseek-reasoner`（会思考，慢） |
| `character_desc` | 人格设定，即 system prompt |
| `temperature` | 生成随机性，默认 0.8 |
| `self_nickname` | **你的微信昵称**，群聊靠 `@昵称` 触发，务必填对 |
| `listen_list` | 监听白名单，留空 = 监听所有会话（含新建会话）。填的是显示名，不是 wxid |
| `group_names` | 按群聊规则处理的群名列表，留空则所有群都适用群规则 |
| `group_keywords` | 群聊关键词前缀，默认 `ai`，如 `ai 今天天气` |
| `private_direct_reply` | 私聊是否免前缀直接回 |
| `max_history_rounds` | 每个会话保留多少轮上下文，默认 8 |
| `clear_memory_commands` | 清空记忆指令，默认 `#清除记忆` |
| `poll_interval` | 轮询间隔（秒），默认 1.0 |
| `reply_prefix` | 回复前缀，留空则不加 |
| `debug` | 打印每条原始消息，排错时开 |
| `verify_send` | 发送后回读数据库确认，更稳但更慢 |

## 触发规则

- **私聊**：直接对话，无需前缀
- **群聊**：`@你的昵称` 或以 `ai` 开头的消息才回复
- 所有会话各自保留独立的对话历史
- 发送 `#清除记忆` 可清空该会话上下文

## 常见问题

**Q：微信登录提示"版本过低"**

必须升级到微信 4.x。3.6 / 3.9 系列目前**全部**被服务端拦截，这不是客户端能绕过去的。如果装了官方最新版仍然提示版本过低，那不是版本问题而是**账号风控**，只能换号。

**Q：体检提示 UIA tree blocked / modules unreadable**

依次排查：是否用了 32 位 Python（必须 64 位）→ 是否装了 `pywin32` → 是否以管理员身份运行 → 是否被安全软件拦截（把 Python 和微信加白名单）。

**Q：能收到消息但发不出去**

发送消息需要驱动微信窗口，因此**不能锁屏、窗口不能最小化**。

**Q：群里 @ 它没反应**

检查 `self_nickname` 是否和你在群里显示的昵称完全一致。不确定可以先开 `debug: true`，看日志里打印的原始消息内容。

## 局限

- 只能在 Windows 上跑
- 发送走界面模拟，工作时**桌面不能被锁定**，且微信窗口会被切到前台
- 本地数据库结构若被微信更新，读消息可能需要等上游库适配
- 无 `chatgpt-on-wechat` 那套插件生态（画图、天气、卡片等），本项目只做聊天

## 免责声明

本项目通过读取本地数据库与模拟界面操作实现，**不属于微信官方开放能力**，存在账号限制或封禁风险。请仅用于学习和自用场景，建议使用小号，不要在重要群聊开启。作者不对使用后果负责。

## 致谢

- [wechatauto-replica](https://github.com/fanyuantaier/wechatauto-replica) — 微信 4.x 自动化核心
- [DeepSeek](https://platform.deepseek.com) — 大模型 API

发布到 GitHub 前记得替换 [LICENSE](LICENSE) 里的 `Your Name`。
