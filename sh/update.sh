#!/bin/bash

# Virtual environment'ı aktif et
source env/bin/activate

# Chrome ve Chromedriver güncelleme
sudo apt update
sudo apt install -y xvfb

# Chrome sürümünü al
CHROME_VERSION=$(google-chrome --version | cut -d ' ' -f 3)
MAJOR_VERSION=$(echo $CHROME_VERSION | cut -d '.' -f 1)

# ChromeDriver'ı indir ve kur (tam sürüm numarası ile)
wget -N "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"
unzip -o chromedriver-linux64.zip
sudo mv -f chromedriver-linux64/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver

# Test et
chromedriver --version

# Xvfb yeniden başlat
pkill Xvfb
Xvfb :99 -ac &
export DISPLAY=:99

# İzinleri kontrol et
sudo chown -R www-data:www-data data
sudo chown -R www-data:www-data export

# Gereksinimleri güncelle
pip install --upgrade -r requirements.txt

echo "Güncelleme tamamlandı!"
