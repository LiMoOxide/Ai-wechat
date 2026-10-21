# encoding:utf-8
"""
微信 DeepSeek 机器人（基于 wxauto UI 自动化 + DeepSeek API）

特点：不 hook、不注入、不改微信任何文件，因此不会被微信的文件自校验拦截，
      也不需要低版本微信（支持 3.9.x，能正常登录）。

运行前提：
  1. 安装并登录微信 3.9.x，保持窗口打开（不要最小化、不要关闭）
  2. python bot.py
"""
import json
import os
import sys
import time
import traceback

import requests
from wxauto import WeChat

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


CFG = load_config()
API_KEY = CFG.get("deepseek_api_key", "")
MODEL = CFG.get("model", "deepseek-chat")
BASE_URL = CFG.get("deepseek_base_url", "https://api.deepseek.com/v1/chat/completions")
TEMPERATURE = CFG.get("temperature", 0.8)
CHARACTER_DESC = CFG.get("character_desc", "你是智能助手。")
SELF_NICKNAME = CFG.get("self_nickname", "").strip()
LISTEN_LIST = CFG.get("listen_list", [])
AUTO_ADD = CFG.get("auto_add_new_session", True)
GROUP_NAMES = CFG.get("group_names", [])
GROUP_KEYWORDS = CFG.get("group_keywords", ["ai"])
PRIVATE_DIRECT = CFG.get("private_direct_reply", True)
MAX_ROUNDS = int(CFG.get("max_history_rounds", 8))
CLEAR_CMDS = CFG.get("clear_memory_commands", ["#清除记忆"])
POLL = float(CFG.get("poll_interval", 1.5))
REPLY_PREFIX = CFG.get("reply_prefix", "")

# 每个会话独立的对话历史：{会话名: [{"role":..,"content":..}]}
histories = {}
listened = set()


def log(*a):
    print("[%s]" % time.strftime("%H:%M:%S"), *a, flush=True)


def ask_deepseek(history):
    """调用 DeepSeek，返回回复文本"""
    messages = [{"role": "system", "content": CHARACTER_DESC}] + history
    body = {
        "model": MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "stream": False,
    }
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY}
    r = requests.post(BASE_URL, headers=headers, json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError("DeepSeek API %s: %s" % (r.status_code, r.text[:200]))
    return r.json()["choices"][0]["message"]["content"].strip()


def is_group(name):
    return name in GROUP_NAMES


def should_reply(name, content):
    """判断是否该回复"""
    if content.startswith("[") or not content:
        return False  # 图片/表情/文件等非文本消息
    if content in CLEAR_CMDS:
        return True
    if is_group(name):
        hit = False
        if SELF_NICKNAME and ("@" + SELF_NICKNAME) in content:
            hit = True
        for kw in GROUP_KEYWORDS:
            if kw and kw in content:
                hit = True
                break
        return hit
    return PRIVATE_DIRECT


def strip_trigger(name, content):
    """去掉触发词，得到真正的问题"""
    q = content
    if is_group(name):
        if SELF_NICKNAME:
            q = q.replace("@" + SELF_NICKNAME, "")
        for kw in GROUP_KEYWORDS:
            if q.lower().startswith(kw.lower()):
                q = q[len(kw):]
                break
    return q.strip()


def handle_message(wx, name, content):
    content = content.strip()
    if content in CLEAR_CMDS:
        histories[name] = []
        wx.SendMsg("记忆已清除～", name)
        log("清除记忆:", name)
        return

    question = strip_trigger(name, content)
    if not question:
        return

    history = histories.setdefault(name, [])
    history.append({"role": "user", "content": question})
    # 只保留最近 N 轮
    if len(history) > MAX_ROUNDS * 2:
        history = history[-MAX_ROUNDS * 2:]
        histories[name] = history

    try:
        reply = ask_deepseek(history)
    except Exception as e:
        log("DeepSeek 调用失败:", e)
        reply = "我这边开小差了，稍等一下再问我吧～"

    history.append({"role": "assistant", "content": reply})
    if REPLY_PREFIX:
        reply = REPLY_PREFIX + reply
    wx.SendMsg(reply, name)
    log("回复 %s: %s" % (name, reply[:60].replace("\n", " ")))


def ensure_listen(wx, name):
    if name in listened:
        return
    try:
        wx.AddListenChat(name)
        listened.add(name)
        log("开始监听:", name)
    except Exception as e:
        log("监听失败 %s: %s" % (name, e))


def main():
    if not API_KEY.startswith("sk-"):
        log("请在 config.json 里填写 deepseek_api_key")
        return 1

    log("正在连接微信窗口（请确保微信已登录且窗口可见）...")
    try:
        wx = WeChat()
    except Exception as e:
        log("连接微信失败:", e)
        log("请确认：微信 3.9.x 已启动并登录，且没有最小化")
        return 1
    log("已连接微信")

    for name in LISTEN_LIST:
        ensure_listen(wx, name)

    log("机器人已启动，等消息进来...")
    while True:
        try:
            if AUTO_ADD:
                try:
                    new_sessions = wx.GetSessionList(newmessage=True)
                    for name in new_sessions:
                        ensure_listen(wx, name)
                except Exception as e:
                    log("扫描会话列表失败:", e)

            msgs = wx.GetListenMessage()
            for chat, msg_list in (msgs or {}).items():
                name = getattr(chat, "who", str(chat))
                for m in msg_list or []:
                    try:
                        if getattr(m, "type", "") != "friend":
                            continue  # 忽略自己发的/系统/时间消息
                        content = (getattr(m, "content", "") or "").strip()
                        if not should_reply(name, content):
                            continue
                        log("收到 %s: %s" % (name, content[:60].replace("\n", " ")))
                        handle_message(wx, name, content)
                    except Exception as e:
                        log("处理单条消息出错:", e)
                        traceback.print_exc()
        except KeyboardInterrupt:
            log("已退出")
            return 0
        except Exception as e:
            log("主循环出错:", e)
            traceback.print_exc()
        time.sleep(POLL)


if __name__ == "__main__":
    sys.exit(main())
