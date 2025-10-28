@echo off
set BASE=C:\Users\kimta\auto_trade_v20
cd /d %BASE%
set PY=C:\Python310-32\python.exe

if not exist "%BASE%\news_logs\cron" mkdir "%BASE%\news_logs\cron"

"%PY%" -X utf8 -m tests.smoke_news >> "%BASE%\news_logs\cron\news_8am.log" 2>&1
