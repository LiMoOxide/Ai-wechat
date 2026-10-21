@echo off
chcp 65001 >nul
cd /d %~dp0
echo ============================================
echo  Check 1/3: DeepSeek API
echo ============================================
python tools\test_deepseek.py
echo.
echo ============================================
echo  Check 2/3: WeChat local database ^& UI tree
echo  (WeChat must be logged in and running)
echo ============================================
python -m wechatauto doctor
echo.
echo ============================================
echo  Check 3/3: recent sessions
echo ============================================
python -m wechatauto sessions
pause
