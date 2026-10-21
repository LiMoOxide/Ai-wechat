# encoding:utf-8
"""
独立验证 DeepSeek 链路是否正常（不需要微信）。

改了 config.json 或换了 Key 之后，先跑这个脚本确认 API 通，
再启动 bot.py 排查问题，可以少绕很多弯路。

用法:
    python tools/test_deepseek.py
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def main():
    if not os.path.exists(CONFIG_PATH):
        print("找不到 config.json，请先 copy config.example.json config.json 并填写 API Key")
        return 1

    cfg = json.load(io.open(CONFIG_PATH, encoding="utf-8"))
    api_key = cfg.get("deepseek_api_key", "")
    if not api_key.startswith("sk-") or "在这里填写" in api_key:
        print("config.json 里的 deepseek_api_key 还没填")
        return 1

    import requests

    url = cfg.get("deepseek_base_url", "https://api.deepseek.com/v1/chat/completions")
    body = {
        "model": cfg.get("model", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": cfg.get("character_desc", "你是智能助手。")},
            {"role": "user", "content": "用一句话说明你是谁"},
        ],
        "temperature": cfg.get("temperature", 0.8),
        "stream": False,
    }
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}

    print("请求 %s ..." % url)
    try:
        r = requests.post(url, headers=headers, json=body, timeout=120)
    except Exception as e:
        print("网络请求失败:", e)
        return 1

    if r.status_code != 200:
        print("API 返回 %s: %s" % (r.status_code, r.text[:300]))
        return 1

    reply = r.json()["choices"][0]["message"]["content"].strip()
    print("调用成功，回复内容：")
    print("  " + reply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
