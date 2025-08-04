#!/bin/bash

echo "Fenomenbet Sistem Kontrol Scripti"
echo "================================"

if [ ! -d "env" ]; then
    echo "❌ Virtual environment (env) bulunamadı!"
    echo "   Python virtual environment oluşturun:"
    echo "   python -m venv env"
    exit 1
else
    echo "✅ Virtual environment mevcut"
fi

source env/bin/activate

PYTHON_VERSION=$(python -V 2>&1)
echo "ℹ️ Python versiyonu: $PYTHON_VERSION"

echo "📦 Gereksinim paketleri kontrol ediliyor..."
pip freeze > installed_requirements.txt
MISSING_PACKAGES=0

while IFS= read -r requirement
do
    if ! grep -q "^$requirement\$" installed_requirements.txt; then
        echo "❌ Eksik paket: $requirement"
        MISSING_PACKAGES=1
    fi
done < requirements.txt

rm installed_requirements.txt

if [ $MISSING_PACKAGES -eq 1 ]; then
    echo "⚠️ Eksik paketler bulundu. Güncellemek için:"
    echo "   pip install -r requirements.txt"
else
    echo "✅ Tüm gereksinim paketleri kurulu"
fi

DIRS_TO_CHECK=("data" "export")

for dir in "${DIRS_TO_CHECK[@]}"
do
    if [ ! -d "$dir" ]; then
        echo "📁 $dir dizini oluşturuluyor..."
        mkdir -p "$dir"
    fi
    
    if [ -w "$dir" ]; then
        echo "✅ $dir dizini yazılabilir"
    else
        echo "❌ $dir dizini yazılabilir değil!"
        echo "   Düzeltmek için: chmod 755 $dir"
    fi
done

REQUIRED_FILES=("app.py" "main.py" "SeleniumSession.py")

for file in "${REQUIRED_FILES[@]}"
do
    if [ -f "$file" ]; then
        echo "✅ $file mevcut"
    else
        echo "❌ $file bulunamadı!"
    fi
done

echo "================================"
echo "Sistem kontrolleri tamamlandı!"
