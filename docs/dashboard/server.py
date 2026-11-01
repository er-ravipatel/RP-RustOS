"""Read-only localhost dashboard. Run from any working directory."""
import functools
import json
import os
import socket
import errno
import sys
from urllib.parse import urlsplit
from executions import load_indexes, report_path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DashboardServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can permit overlapping live listeners and stale responses.
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/docs/tracking.json':
            data = json.loads((ROOT / 'docs/tracking.json').read_text(encoding='utf-8'))
            records, errors = load_indexes(ROOT)
            data['runs'].extend(records)
            data['execution_import_errors'] = errors
            body = json.dumps(data).encode('utf-8')
        elif path.startswith('/execution/') and path.endswith('/report'):
            try:
                identifier = path[len('/execution/'):-len('/report')]
                body = report_path(identifier, ROOT).read_bytes()
            except (ValueError, KeyError, OSError):
                self.send_error(404, 'No valid indexed report')
                return
        else:
            return super().do_GET()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    try:
        server = DashboardServer(('127.0.0.1', 8765), functools.partial(Handler, directory=str(ROOT)))
    except OSError as error:
        if error.errno == errno.EADDRINUSE or getattr(error, 'winerror', None) == 10048:
            print('Port 8765 is already in use. A dashboard may already be running.', file=sys.stderr)
            print('Open http://127.0.0.1:8765/docs/dashboard/', file=sys.stderr)
            print('To restart it, stop the existing dashboard in its terminal with Ctrl+C, then rerun this command.', file=sys.stderr)
            return 1
        raise
    print('RustOS dashboard: http://127.0.0.1:8765/docs/dashboard/')
    print('Read-only; serves repository files on localhost. Ctrl+C stops the server.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
