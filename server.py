"""Local-only HTTP application. No third-party runtime dependencies."""
import argparse
import json
import mimetypes
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import store

STATIC = Path(__file__).parent / 'static'
MAX_BODY = 2_000_000


def handler(database):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, kind='application/json'):
            if kind == 'application/json':
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed:
                return self.send(403, {'error': 'Invalid host'})
            route = urlsplit(self.path).path
            try:
                if route == '/api/comparisons':
                    return self.send(200, store.queue(database))
                if route == '/api/summary':
                    return self.send(200, store.summary(database))
                if route == '/api/export':
                    return self.send(200, {'schema_version': 1, 'reviews': store.export(database)})
                if route.startswith('/api/comparisons/'):
                    return self.send(200, store.comparison(database, int(route.rsplit('/', 1)[1])))
                files = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
                if route not in files:
                    return self.send(404, {'error': 'Not found'})
                file = STATIC / files[route]
                return self.send(200, file.read_bytes(), mimetypes.guess_type(file)[0] + '; charset=utf-8')
            except LookupError as exc:
                self.send(404, {'error': str(exc)})
            except ValueError:
                self.send(400, {'error': 'Invalid comparison ID'})

        def do_POST(self):
            # Reject cross-origin form submissions and DNS-rebinding hostnames.
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed:
                return self.send(403, {'error': 'Invalid host'})
            origin = self.headers.get('Origin')
            if origin and origin not in {'http://' + host for host in allowed}:
                return self.send(403, {'error': 'Cross-origin writes are blocked'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(415, {'error': 'Send application/json'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BODY:
                    return self.send(413, {'error': 'Body must be between 1 byte and 2 MB'})
                item = json.loads(self.rfile.read(length))
                route = urlsplit(self.path).path
                if route == '/api/import':
                    return self.send(201, {'imported': store.ingest(database, item)})
                if route.startswith('/api/reviews/'):
                    return self.send(201, store.review(database, int(route.rsplit('/', 1)[1]), item))
                self.send(404, {'error': 'Not found'})
            except LookupError as exc:
                self.send(404, {'error': str(exc)})
            except FileExistsError as exc:
                self.send(409, {'error': str(exc)})
            except (ValueError, UnicodeError) as exc:
                self.send(400, {'error': str(exc)})
            except sqlite3.Error:
                self.send(500, {'error': 'Database error; see local server logs'})
                raise
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='pairwise.sqlite3')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--seed', type=Path, help='Import a JSON comparison array, then exit')
    args = parser.parse_args()
    store.initialize(args.db)
    if args.seed:
        print('Imported', store.ingest(args.db, json.loads(args.seed.read_text())))
    else:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(args.db))
        print(f'Pairwise Lab: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
