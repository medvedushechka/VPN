#!/usr/bin/env python3
"""
Создание ICO файла из PNG логотипа для Windows приложения
"""

from PIL import Image
import os

def create_ico_from_png():
    """Создание ICO файла из PNG"""
    
    png_path = "assets/logo.png"
    ico_path = "assets/icon.ico"
    
    if not os.path.exists(png_path):
        print(f"❌ Файл {png_path} не найден!")
        return False
    
    try:
        # Открываем PNG файл
        img = Image.open(png_path)
        
        # Конвертируем в RGBA если нужно
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Создаем разные размеры для ICO
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        
        # Сохраняем как ICO с множественными размерами
        img.save(ico_path, format='ICO', sizes=sizes)
        
        print(f"✅ ICO файл создан: {ico_path}")
        
        # Проверяем размер файла
        size_kb = os.path.getsize(ico_path) / 1024
        print(f"📊 Размер файла: {size_kb:.1f} КБ")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания ICO: {e}")
        return False

def update_build_script():
    """Обновление скрипта сборки для использования ICO"""
    
    build_file = "build.py"
    
    try:
        with open(build_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Заменяем ссылку на иконку
        content = content.replace(
            '--icon=icon.ico',
            '--icon=assets/icon.ico'
        )
        
        with open(build_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Скрипт сборки обновлен")
        
    except Exception as e:
        print(f"❌ Ошибка обновления скрипта: {e}")

if __name__ == "__main__":
    print("🎨 Создание иконки для Windows приложения...")
    
    if create_ico_from_png():
        update_build_script()
        print("\n🎉 Готово! Теперь можно собирать EXE с красивой иконкой.")
        print("💡 Запустите: python build.py")
    else:
        print("\n❌ Не удалось создать иконку.")
        print("💡 Убедитесь что файл assets/logo.png существует.")
