@echo off
setlocal
set PROJ=C:\Users\kimta\auto_trade_v20

rem --- 안전: 폴더 준비 ---
if not exist "%PROJ%\logs" mkdir "%PROJ%\logs"
if not exist "%PROJ%\news_logs" mkdir "%PROJ%\news_logs"

cd /d "%PROJ%"

echo [START] %DATE% %TIME% >> "%PROJ%\logs\task_news_summary.out"

rem --- 1) 뉴스 요약 파일 생성 ---
py run_news_summary.py 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
py run_news_by_holdings.py 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
py run_news_search.py 금리 환율 삼성전자 --since 1 --out search_%DATE%.md 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"

rem --- 2) 변경분만 커밋/푸시 ---
git add news_logs 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"

for /f %%C in ('git diff --cached --name-only ^| find /c /v ""') do set COUNT=%%C

if "%COUNT%"=="0" (
  echo [INFO] nothing to commit >> "%PROJ%\logs\task_news_summary.out"
) else (
  git commit -m "chore(news): auto save %DATE% %TIME%" 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
  git push 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
)

echo [DONE] %DATE% %TIME% >> "%PROJ%\logs\task_news_summary.out"
endlocal
