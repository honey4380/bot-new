from app import app
from proxy_middleware import ProxyMiddleware
import threading
import os
import sys

PROXY_IPS = [
    '127.0.0.1:2050',
    '135.181.236.205:2050',
    "bot-bahisfanatik2.visiontech.co",
]

app.wsgi_app = ProxyMiddleware(app.wsgi_app, PROXY_IPS)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

def run_server():
    try:
        app.run(host='0.0.0.0', port=2050)
    except Exception as e:
        print(e)
        threading.Timer(10, run_server).start()

if __name__ == "__main__":
    run_server()
