#!/bin/bash

# Virtual environment'ı aktif et
source env/bin/activate

# Uygulama klasörlerini kontrol et ve oluştur
mkdir -p data
mkdir -p export

# İzinleri kontrol et ve düzelt
sudo chown -R www-data:www-data data
sudo chown -R www-data:www-data export

# Eski gunicorn process'lerini temizle
pkill gunicorn

# IP adresini al ve göster
PUBLIC_IP=$(curl -s ifconfig.me)
echo "------------------------------------------------"
echo "API Erişim Noktaları:"
echo "------------------------------------------------"
echo "Swagger UI: http://fenomen.cacsoft.com:2008/apidocs"
echo "veya: http://$PUBLIC_IP:2008/apidocs"
echo "------------------------------------------------"
echo "API Endpoint örnekleri:"
echo "GET  http://fenomen.cacsoft.com:2008/api/getUserData/<username>"
echo "POST http://fenomen.cacsoft.com:2008/api/getUserList"
echo "------------------------------------------------"

# Flask uygulamasını başlat (wsgi.py üzerinden)
export FLASK_APP=wsgi.py
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:2008 wsgi:app --timeout 120 --reload --access-logfile - --error-logfile -
