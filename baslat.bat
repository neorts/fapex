@echo off
title Apex Tracker - Baslat
cd /d D:\fapex

echo ========================================
echo    APEX TRACKER BASLATICI
echo ========================================
echo.
echo [1/2] Web panel baslatiliyor...
start "Apex Web Panel" python app.py

timeout /t 3 /nobreak >nul

echo [2/2] Discord bot baslatiliyor...
start "Apex Discord Bot" python discord_bot.py

echo.
echo ========================================
echo    TUM PROGRAMLAR BASLATILDI!
echo ========================================
echo.
echo Web Panel: http://127.0.0.1:5000
echo Discord Bot: Cevrimici
echo.
echo Bu pencereyi kapatabilirsiniz.
echo Programları durdurmak icin Ctrl+C kullanin.
echo.
pause
