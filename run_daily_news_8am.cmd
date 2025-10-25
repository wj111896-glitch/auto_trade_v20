@echo off
setlocal

rem === 프로젝트/파이썬 경로 고정 ===
set "PROJ=C:\Users\kimta\auto_trade_v20"
set "PY=C:\Users\kimta\AppData\Local\Programs\Python\Python311\python.exe"

rem === 작업 폴더 강제 전환 (System32 방지) ===
pushd "%PROJ%" || (
  echo [ERR] cannot cd to %PROJ% >> "%PROJ%\logs\task_news_summary.err"
  exit /b 1
)

echo [INFO] Current Working Directory: %CD% >> "%PROJ%\logs\task_news_summary.out"

if not exist "%PROJ%\logs" mkdir "%PROJ%\logs"
if not exist "%PROJ%\news_logs" mkdir "%PROJ%\news_logs"

for /f "usebackq tokens=1,2 delims==" %%A in ("%PROJ%\secrets.env") do set "%%A=%%B"

>>"%PROJ%\logs\task_news_summary.out" echo [START] %DATE% %TIME% CWD=%CD%

"%PY%" "%PROJ%\run_news_summary.py"     1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
"%PY%" "%PROJ%\run_news_by_holdings.py" 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
"%PY%" "%PROJ%\run_news_search.py" 금리 환율 --since 1 --out "search_%DATE%.md" 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"

git -C "%PROJ%" add news_logs 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
for /f %%C in ('git -C "%PROJ%" diff --cached --name-only ^| find /c /v ""') do set COUNT=%%C
if "%COUNT%"=="0" (
  echo [INFO] nothing to commit >> "%PROJ%\logs\task_news_summary.out"
) else (
  git -C "%PROJ%" commit -m "chore(news): auto save %DATE% %TIME%" 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
  git -C "%PROJ%" push 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"
)

"%PY%" "%PROJ%\run_health_check.py" 1>>"%PROJ%\logs\task_news_summary.out" 2>>"%PROJ%\logs\task_news_summary.err"

>>"%PROJ%\logs\task_news_summary.out" echo [DONE] %DATE% %TIME%

popd
endlocal
