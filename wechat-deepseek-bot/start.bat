@echo off
chcp 65001 >nul
cd /d %~dp0

if not exist config.json (
    echo [!] no config.json found
    echo     copying config.example.json -^> config.json
    copy config.example.json config.json >nul
    echo [!] please edit config.json and fill in deepseek_api_key, then run again
    pause
    exit /b 1
)

echo ============================================
echo  WeChat DeepSeek Bot
echo  requirements: WeChat 4.1.12+ logged in,
echo  window visible, screen unlocked
echo ============================================
python bot.py
pause
