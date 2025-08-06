from app import app
from proxy_middleware import ProxyMiddleware
import threading
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get configuration from environment
PORT = int(os.getenv('PORT', 2050))
DOMAIN = os.getenv('DOMAIN', 'bot-bahisfanatik2.visiontech.co')

PROXY_IPS = [
    f'127.0.0.1:{PORT}',
    f'135.181.236.205:{PORT}',
    DOMAIN,
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
        app.run(host='0.0.0.0', port=PORT)
    except Exception as e:
        print(e)
        threading.Timer(10, run_server).start()

if __name__ == "__main__":
    run_server()
