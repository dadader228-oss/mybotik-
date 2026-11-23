@echo off
chcp 65001 >nul
echo ========================================
echo   BOT STORE - Telegram Bot
echo ========================================
echo.

if not exist .env (
    echo [!] Файл .env не найден.
    echo     Скопируйте .env.example в .env и заполните BOT_TOKEN и ADMIN_IDS
    pause
    exit /b 1
)

echo Установка зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo Ошибка установки зависимостей.
    pause
    exit /b 1
)

echo.
echo Запуск бота...
python main.py
pause
