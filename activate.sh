#!/bin/bash

# Python 3.12.6 kurulumu için gerekli paketler
sudo yum update -y
sudo yum install -y gcc openssl-devel bzip2-devel libffi-devel zlib-devel wget make

# Python 3.12.6 kaynak kodunu indir ve kur
cd /tmp
wget https://www.python.org/ftp/python/3.12.6/Python-3.12.6.tgz
tar xzf Python-3.12.6.tgz
cd Python-3.12.6
./configure --enable-optimizations
sudo make altinstall
python3.12 --version

# Virtual environment oluştur
cd /root/bot.visiontech.co
python3.12 -m venv env

# Virtual environment'ı aktif et
source env/bin/activate

# Gerekli sistem paketlerini kur
sudo yum install -y wget unzip

# Chrome kurulumu
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
sudo yum install -y ./google-chrome-stable_current_x86_64.rpm

# ChromeDriver kurulumu
CHROME_VERSION=$(google-chrome --version | cut -d ' ' -f 3 | cut -d '.' -f 1)
wget -N "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}.0.6261.94/linux64/chromedriver-linux64.zip"
unzip -o chromedriver-linux64.zip
sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver

# Xvfb kurulumu ve başlatma (Sanal X server)
sudo yum install -y xorg-x11-server-Xvfb
Xvfb :99 -ac &
export DISPLAY=:99

# Pip'i güncelle ve gereksinimleri kur
python -m pip install --upgrade pip
pip install -r requirements.txt

# Uygulama klasörlerini oluştur
mkdir -p data
mkdir -p export

# Uygulama izinlerini ayarla (CentOS'ta apache kullanıcısı)
sudo chown -R apache:apache data
sudo chown -R apache:apache export

# Gunicorn kur
pip install gunicorn

# Flask uygulamasını başlat
export FLASK_APP=app.py
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 app:app