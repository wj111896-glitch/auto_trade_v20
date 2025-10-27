@echo off
setlocal

rem === 고정 경로 ===
set "PROJ=C:\Users\kimta\auto_trade_v20"
set "PY=C:\Users\kimta\AppData\Local\Programs\Python\Python311\python.exe"

rem === 로그 폴더 ===
if not exist "%PROJ%\logs" mkdir "%PROJ%\logs"

rem === 폴더 이동 (한 줄 처리) ===
pushd "%PROJ%" || (echo [ERR] cd fail>"%PROJ%\logs\news_8am.log" & exit /b 1)

echo [START] %date% %time% > "%PROJ%\logs\news_8am.log"

rem 1) 텔레그램 파이프 점검용 간단 알림
"%PY%" "%PROJ%\tools\news_8am_simple.py" >> "%PROJ%\logs\news_8am.log" 2>&1

rem 2) 요약 2종
"%PY%" "%PROJ%\run_news_summary.py"     >> "%PROJ%\logs\news_8am.log" 2>&1
"%PY%" "%PROJ%\run_news_by_holdings.py" >> "%PROJ%\logs\news_8am.log" 2>&1

rem 3) 키워드 검색 (파일명 안전 태그)
set "DATE_TAG=%DATE: =_%"
set "DATE_TAG=%DATE_TAG:/=-%"
set "DATE_TAG=%DATE_TAG:.=-%"
"%PY%" "%PROJ%\run_news_search.py" "금리" "환율" --since 1 --out "search_%DATE_TAG%.md" >> "%PROJ%\logs\news_8am.log" 2>&1

rem 4) git 저장 (괄호 없이)
git -C "%PROJ%" add news_logs >> "%PROJ%\logs\news_8am.log" 2>&1
for /f %%C in ('git -C "%PROJ%" diff --cached --name-only ^| find /c /v ""') do set COUNT=%%C
if "%COUNT%"=="0" (
  echo [INFO] nothing to commit>>"%PROJ%\logs\news_8am.log"
) else (
  git -C "%PROJ%" commit -m "chore-news: auto save %DATE% %TIME%" >> "%PROJ%\logs\news_8am.log" 2>&1
  git -C "%PROJ%" push >> "%PROJ%\logs\news_8am.log" 2>&1
)

rem 5) health check
"%PY%" "%PROJ%\run_health_check.py" >> "%PROJ%\logs\news_8am.log" 2>&1

echo [DONE] %date% %time% >> "%PROJ%\logs\news_8am.log"

popd
endlocal

