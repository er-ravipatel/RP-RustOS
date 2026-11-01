import json
from http.server import ThreadingHTTPServer
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from server import Handler, ROOT, DashboardServer
from executions import load_indexes


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


class DashboardHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = DashboardServer(('127.0.0.1', 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_tracking_response_merges_explicit_runs_without_caching(self):
        with urlopen(self.base + '/docs/tracking.json', timeout=5) as response:
            data = json.load(response)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        rows, errors = load_indexes(ROOT)
        self.assertTrue({r['id'] for r in rows}.issubset({r['id'] for r in data['runs']}))
        self.assertEqual(errors, data['execution_import_errors'])

    def test_indexed_report_is_accessible(self):
        rows, _ = load_indexes(ROOT)
        links = [p for r in rows if r['status']=='passed' for p in r['evidence'] if p.startswith('execution/')]
        if not links:
            self.skipTest('No production reports recorded in this checkout')
        with urlopen(self.base + '/' + links[-1], timeout=5) as response:
            report = json.load(response)
        self.assertEqual(report['operation'], 'verify')
        self.assertTrue(report['complete'])

    def test_unregistered_or_unsafe_report_id_is_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + '/execution/e-invalid/report', timeout=5)
        self.assertEqual(caught.exception.code, 404)

    def test_second_listener_on_same_port_is_rejected(self):
        with self.assertRaises(OSError):
            DashboardServer(('127.0.0.1', self.server.server_port), QuietHandler)


if __name__ == '__main__':
    unittest.main()
