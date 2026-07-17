@echo off
rem Докачка зимних данных до победы: winter_fetch_daily.py кэширует каждый чанк,
rem поэтому повторный запуск качает только недостающее. При 429 (лимит Open-Meteo)
rem ждём 15 минут и пробуем снова.
cd /d "%~dp0.."

:loop
py scripts\winter_fetch_daily.py 2020 2026 && goto done
echo.
echo Лимит Open-Meteo или сеть — повтор через 15 минут (Ctrl+C — прервать)...
timeout /t 900
goto loop

:done
echo.
echo Готово: data\processed\winter_daily_features.csv собран полностью.
