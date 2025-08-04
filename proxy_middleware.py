import random
from urllib.parse import urlparse

class ProxyMiddleware:
    def __init__(self, app, proxy_ips):
        self.app = app
        self.proxy_ips = proxy_ips

    def __call__(self, environ, start_response):
        server = environ.get('HTTP_HOST', '')
        if not server:
            server_name = random.choice(self.proxy_ips)
            environ['HTTP_HOST'] = server_name
            environ['SERVER_NAME'] = server_name.split(':')[0]
            environ['SERVER_PORT'] = server_name.split(':')[1] if ':' in server_name else '5000'
        return self.app(environ, start_response)
