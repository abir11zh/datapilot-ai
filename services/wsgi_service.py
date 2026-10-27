"""WSGI adapter for the existing request dispatcher (no duplicated API routes)."""
from email.message import Message
from http import HTTPStatus
from io import BytesIO
from types import SimpleNamespace


def create_application(port):
    from app import Application

    class Request(Application):
        def __init__(self, environ):
            self.headers = Message()
            for key, value in environ.items():
                if key.startswith('HTTP_'):
                    self.headers[key[5:].replace('_', '-')] = value
            for key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                if environ.get(key):
                    self.headers[key.replace('_', '-')] = environ[key]
            self.path = environ.get('PATH_INFO', '/')
            if environ.get('QUERY_STRING'):
                self.path += '?' + environ['QUERY_STRING']
            self.rfile = environ['wsgi.input']
            self.wfile = BytesIO()
            self.server = SimpleNamespace(server_port=port)
            self.response_headers = []
            self.status = '200 OK'

        def send_response(self, code):
            self.status = f'{code} {HTTPStatus(code).phrase}'

        def send_header(self, key, value):
            self.response_headers.append((key, value))

        def end_headers(self):
            pass

    def application(environ, start_response):
        request = Request(environ)
        method = environ.get('REQUEST_METHOD', 'GET')
        if method in {'GET', 'HEAD'}:
            request.do_GET()
        elif method == 'POST':
            request.do_POST()
        else:
            request.reply({'error': 'Method not allowed.'}, 405)
        start_response(request.status, request.response_headers)
        return [b'' if method == 'HEAD' else request.wfile.getvalue()]

    return application
