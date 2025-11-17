@echo off
echo 🚀 SecureVPN Android Builder (WSL)
echo ===================================

echo 📱 Запускаем сборку в WSL...
echo.

REM Копируем файлы в WSL и запускаем сборку
wsl bash -c "cd /mnt/c/Users/Medvedushkaa/Desktop/CIrcus/SecureVPN-Android && chmod +x build_apk.sh && ./build_apk.sh"

echo.
echo 🎉 Сборка завершена!
echo 📁 Проверьте папку bin/ для APK файла
pause
