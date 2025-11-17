@echo off
echo ========================================
echo    SecureVPN GUI Client - Установка
echo ========================================
echo.

:: Проверка Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не установлен!
    echo Скачайте Python с https://python.org
    pause
    exit /b 1
)

echo [INFO] Python найден
echo.

:: Создание виртуального окружения
echo [INFO] Создание виртуального окружения...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось создать виртуальное окружение
    pause
    exit /b 1
)

:: Активация окружения
echo [INFO] Активация окружения...
call venv\Scripts\activate.bat

:: Обновление pip
echo [INFO] Обновление pip...
python -m pip install --upgrade pip

:: Установка зависимостей
echo [INFO] Установка зависимостей...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось установить зависимости
    pause
    exit /b 1
)

echo.
echo ========================================
echo        Установка завершена!
echo ========================================
echo.
echo Для запуска приложения:
echo   1. Активируйте окружение: venv\Scripts\activate.bat
echo   2. Запустите: python main.py
echo.
echo Для сборки в EXE:
echo   python build.py
echo.
pause
