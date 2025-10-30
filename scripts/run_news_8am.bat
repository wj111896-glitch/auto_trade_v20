@echo off
setlocal
REM 1) 배치파일 위치 기준으로 프로젝트 루트 고정
pushd "%~dp0\.."
set "BASE=%CD%"

REM 2) 로그 폴더 보장
if not exist "%BASE%\news_logs\cron" mkdir "%BASE%\news_logs\cron"

REM 3) Python 런처로 실행(버전 상관없이 안전) + UTF-8 고정
py -X utf8 -m tests.smoke_news >> "%BASE%\news_logs\cron\news_8am.log" 2>&1

popd
endlocal
