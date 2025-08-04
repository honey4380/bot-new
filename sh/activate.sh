#!/bin/bash

# Python 3.12.6 kurulumu
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# Virtual environment oluştur
python3.12 -m venv env

# Virtual environment'ı aktif et
source env/bin/activate

# Gerekli sistem paketlerini kur
sudo apt install -y wget unzip build-essential libssl-dev libffi-dev

# Chrome ve Chromedriver kurulumu
sudo apt update
sudo apt install -y wget unzip xvfb

# Chrome kurulumu
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt --fix-broken install -y

# ChromeDriver kurulumu
CHROME_VERSION=$(google-chrome --version | cut -d ' ' -f 3 | cut -d '.' -f 1)
wget -N "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$CHROME_VERSION.0.6261.94/linux64/chromedriver-linux64.zip"
unzip -o chromedriver-linux64.zip
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver

# Xvfb başlat (Sanal X server)
Xvfb :99 -ac &
export DISPLAY=:99

# Pip'i güncelle ve gereksinimleri kur
python -m pip install --upgrade pip
pip install -r requirements.txt

# Uygulama klasörlerini oluştur
mkdir -p data
mkdir -p export

# Uygulama izinlerini ayarla
sudo chown -R www-data:www-data data
sudo chown -R www-data:www-data export

# Flask uygulamasını başlat
export FLASK_APP=app.py
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 app:app
