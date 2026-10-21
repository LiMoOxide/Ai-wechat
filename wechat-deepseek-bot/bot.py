# encoding:utf-8
"""
微信 DeepSeek 机器人 —— 微信 4.x 版（基于 wechatauto-replica）

与 3.9 版(bot.py)的区别：
  微信 4.x 用 Qt 自绘界面，传统 UIAutomation 拿不到控件树（wxauto 因此失效）。
  本版改为：读消息走"解密本地数据库"，发消息走"UIA 热激活 + OCR 回退"。
  好处是不受低版本登录限制，用官方最新版微信即可。

运行前提：
  1. 安装并登录微信 4.1.12+（推荐 4.1.15.53），保持窗口打开、不要锁屏
  2. 先跑 体检.bat 确认数据库密钥和控件树正常
  3. python bot_wx4.py
"""
import json
import os
import queue
import sys
import threading
import time
import traceback

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit(
            "找不到 config.json\n"
            "请先把 config.example.json 复制为 config.json，并填写 deepseek_api_key\n"
            "Windows: copy config.example.json config.json\n"
            "Linux/Mac: cp config.example.json config.json"
        )
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
GROUP_NAMES = CFG.get("group_names", [])          # 留空 = 所有群都按群规则
GROUP_KEYWORDS = CFG.get("group_keywords", ["ai"])
PRIVATE_DIRECT = CFG.get("private_direct_reply", True)
MAX_ROUNDS = int(CFG.get("max_history_rounds", 8))
CLEAR_CMDS = CFG.get("clear_memory_commands", ["#清除记忆"])
REPLY_PREFIX = CFG.get("reply_prefix", "")
POLL = float(CFG.get("poll_interval", 1.0))
DEBUG = bool(CFG.get("debug", False))
VERIFY_SEND = bool(CFG.get("verify_send", False))

histories = {}          # {会话username: [{"role":..,"content":..}]}
hist_lock = threading.Lock()
send_queue = queue.Queue()


def log(*a):
    print("[%s]" % time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- DeepSeek
def ask_deepseek(history):
    messages = [{"role": "system", "content": CHARACTER_DESC}] + history
    body = {"model": MODEL, "messages": messages,
            "temperature": TEMPERATURE, "stream": False}
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + API_KEY}
    r = requests.post(BASE_URL, headers=headers, json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError("DeepSeek API %s: %s" % (r.status_code, r.text[:200]))
    return r.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------- 规则判断
def is_group(username, display):
    """群聊 username 形如 xxx@chatroom"""
    if "@chatroom" in (username or ""):
        return True
    return display in GROUP_NAMES


def is_text_msg(mtype):
    if isinstance(mtype, int):
        return mtype == 1
    return str(mtype) in ("文本", "Text", "text")


def should_reply(username, display, content, from_self):
    if from_self or not content:
        return False
    if content in CLEAR_CMDS:
        return True
    if is_group(username, display):
        if SELF_NICKNAME and ("@" + SELF_NICKNAME) in content:
            return True
        for kw in GROUP_KEYWORDS:
            if kw and content.lower().startswith(kw.lower()):
                return True
        return False
    return PRIVATE_DIRECT


def strip_trigger(username, display, content):
    q = content
    if is_group(username, display):
        if SELF_NICKNAME:
            q = q.replace("@" + SELF_NICKNAME, "")
        for kw in GROUP_KEYWORDS:
            if q.lower().startswith(kw.lower()):
                q = q[len(kw):]
                break
    return q.strip()


# ---------------------------------------------------------------- 发送线程
def sender_loop():
    """串行发送：GUI 操作不能并发，统一排队"""
    from wechatauto.guia import quick_send
    while True:
        item = send_queue.get()
        if item is None:
            return
        who, text = item
        try:
            resp = quick_send(text, who, verify=VERIFY_SEND)
            ok = getattr(resp, "ok", None)
            if ok is False:
                log("发送失败 -> %s : %s" % (who, getattr(resp, "message", resp)))
            else:
                log("已回复 %s: %s" % (who, text[:60].replace("\n", " ")))
        except Exception as e:
            log("发送异常 -> %s: %s" % (who, e))
            traceback.print_exc()
        time.sleep(0.4)


# ---------------------------------------------------------------- 消息处理
def handle_message(db, msg, self_wxid):
    username = msg.get("username") or ""
    content = (msg.get("content") or "").strip()
    display = db.get_nickname(username)

    if content in CLEAR_CMDS:
        with hist_lock:
            histories[username] = []
        send_queue.put((display, "记忆已清除～"))
        log("清除记忆:", display)
        return

    question = strip_trigger(username, display, content)
    if not question:
        return

    with hist_lock:
        history = histories.setdefault(username, [])
        history.append({"role": "user", "content": question})
        if len(history) > MAX_ROUNDS * 2:
            history = history[-MAX_ROUNDS * 2:]
            histories[username] = history

    try:
        reply = ask_deepseek(history)
    except Exception as e:
        log("DeepSeek 调用失败:", e)
        reply = "我这边开小差了，稍等一下再问我吧～"

    with hist_lock:
        history.append({"role": "assistant", "content": reply})
    if REPLY_PREFIX:
        reply = REPLY_PREFIX + reply
    send_queue.put((display, reply))


def make_callback(db, self_wxid):
    def on_msg(msg, lst):
        try:
            sender = msg.get("sender_username") or msg.get("sender_id")
            from_self = (str(sender) == str(self_wxid))
            mtype = msg.get("type")
            username = msg.get("username") or ""
            content = (msg.get("content") or "").strip()
            display = db.get_nickname(username)

            if DEBUG:
                log("RAW %s | type=%s | from_self=%s | %s: %s"
                    % (display, mtype, from_self,
                       sender, content[:50].replace("\n", " ")))

            if not is_text_msg(mtype):
                return
            if not should_reply(username, display, content, from_self):
                return

            log("收到 %s: %s" % (display, content[:60].replace("\n", " ")))
            handle_message(db, msg, self_wxid)
        except Exception:
            log("回调出错:")
            traceback.print_exc()
    return on_msg


def main():
    if not API_KEY.startswith("sk-"):
        log("请在 config.json 里填写 deepseek_api_key")
        return 1

    try:
        from wechatauto import WeChatDB
        from wechatauto.db import Listener
    except ImportError as e:
        log("缺少 wechatauto-replica：%s" % e)
        log("请先运行：pip install wechatauto-replica winsdk pypinyin")
        return 1

    log("正在读取微信本地数据库（请确认微信 4.x 已登录并在运行）...")
    try:
        db = WeChatDB()
        info = db.get_self_info()
    except Exception as e:
        log("连接微信失败:", e)
        log("请确认：微信 4.x 已启动并登录，且窗口未被最小化/锁屏")
        return 1

    self_wxid = info.get("username", "")
    log("已连接微信账号: %s (wxid=%s)" % (info.get("nick_name") or info.get("remark"), self_wxid))
    if not SELF_NICKNAME:
        log("提示：config.json 的 self_nickname 未填，群聊 @触发可能失效（当前昵称=%s）"
            % (info.get("nick_name") or "?"))

    threading.Thread(target=sender_loop, daemon=True).start()

    lst = Listener(db, interval=POLL)
    cb = make_callback(db, self_wxid)

    if LISTEN_LIST:
        for name in LISTEN_LIST:
            u = db.username_by_nickname(name) or name
            lst.add_listener(u, cb)
            log("监听:", name, "->", u)
    else:
        lst.add_all(cb, discover=True)
        log("监听：所有会话（含新建会话）")

    lst.start()
    log("机器人已启动，等消息进来...（Ctrl+C 退出）")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("正在退出...")
        lst.stop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
