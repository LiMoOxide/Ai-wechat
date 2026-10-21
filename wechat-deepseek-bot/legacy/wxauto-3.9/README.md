# legacy / wxauto 3.9 方案（已废弃，仅存档）

这是本项目的早期实现，基于 [wxauto](https://github.com/cluic/wxauto) 的 UI 自动化。

**不再推荐使用**，原因见 [docs/wechat-version-guide.md](../../docs/wechat-version-guide.md)：

1. 依赖的微信 3.9.x 现已同样被服务端阻止登录（提示"版本过低"）
2. wxauto 项目已于 2025-10-28 归档停更
3. wxauto 已从 PyPI 下架，只能从 GitHub 源码安装

如果要在微信 3.9.x 上使用：

```bash
pip install git+https://github.com/cluic/wxauto.git
python bot.py
```

配置项与项目根目录的 `bot.py` 完全一致（`wx.SendMsg` 改为 GUI 自动发送）。

保留此目录仅供对比参考，新用户请直接用根目录的主程序。
