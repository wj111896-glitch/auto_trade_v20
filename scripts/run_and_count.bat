@echo off
setlocal
cd /d %~dp0\..

:: ① 로그 파일 이름(날짜/시간 포함)
for /f "tokens=1-3 delims=/- " %%a in ("%date%") do set D=%%a%%b%%c
for /f "tokens=1-2 delims=:." %%h in ("%time%") do set T=%%h%%i
set LOG=logs\daytrade_%D%_%T%.console.log

:: ② 프로그램 실행 + 콘솔 로그 저장
python run_daytrade.py --symbols 005930 000660 035420 --max-ticks 2000 --mode dry --budget 10000000 > "%LOG%" 2>&1

echo.
echo ==== RISK BLOCK COUNTS ====
echo symbol_exposure_cap: 
findstr /C:"symbol_exposure_cap" "%LOG%" | find /C /V ""
echo total_exposure_cap:
findstr /C:"total_exposure_cap"  "%LOG%" | find /C /V ""
echo sector_exposure_cap:
findstr /C:"sector_exposure_cap" "%LOG%" | find /C /V ""
echo risk_block (전체):
findstr /C:"[RISK BLOCK]"        "%LOG%" | find /C /V ""
echo risk_recheck:
findstr /C:"risk_recheck"        "%LOG%" | find /C /V ""

echo.
echo LOG saved to: %LOG%
endlocal
