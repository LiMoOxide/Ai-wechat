# legacy / ntchat 3.6 方案（已废弃，未保留代码）

最初的实现基于 [chatgpt-on-wechat-win](https://github.com/Tishon1532/chatgpt-on-wechat-win)，
使用 ntchat 注入微信 **3.6.0.18**。这条路已经完全走不通，此处只记录结论，**不保留代码**
（完整 fork 不在本仓库范围内）。

## 为什么废弃

1. 微信 3.6.0.18 被腾讯服务端判定版本过低，无法登录
2. 尝试等长替换 `WeChatWin.dll` 中的版本号字符串（3.6.0.18 → 3.9.5.81）绕过拦截：
   - 文件大小与代码偏移完全不变，不影响注入逻辑
   - 但对照组实验证明：**打补丁后微信必然在 20 秒内崩溃**，存在文件自校验
3. 改而尝试运行时修改内存中的版本号：全进程扫描（ASCII / UTF-16 / DWORD 三种形式）
   未发现任何独立版本号字段，命中的全是安装路径里的目录名

结论：hook + 低版本客户端这条路在 2026 年已无工程价值。

## 当时对项目做的两处适配

若你仍然要在这条路上折腾，有两个改动点：

- `config.json`：`use_linkai` 默认为 `true`，必须改成 `false`，否则请求会走 LinkAI 而不是 DeepSeek
- `bridge/bridge.py`：原代码只认 `deepseek-chat` / `deepseek-coder` / `DeepSeek-V2`，
  建议改成 `model_type.startswith("deepseek")`，这样 `deepseek-reasoner` 等新模型也能直接生效
