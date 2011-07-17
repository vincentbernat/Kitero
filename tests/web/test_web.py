try:
    import unittest2 as unittest
except ImportError:
    import unittest

import threading
import time
import urllib2

from kitero.web import app
from kitero.web.serve import run

class TestStatic(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client() # web

    def test_index(self):
        """Request index"""
        rv = self.app.get("/")
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'text/html')

class TestWebServer(unittest.TestCase):
    def test_serve(self):
        """Launch web server"""
        t = threading.Thread(target=run)
        t.setDaemon(True)
        t.start()
        time.sleep(0.2)
        content = urllib2.urlopen("http://127.0.0.1:8187/")
        headers = content.info()
        self.assertEqual(content.getcode(), 200)
        self.assertEqual(headers['Content-Type'], 'text/html; charset=utf-8')
        # No way to stop the server, let it die (as long this is the
        # only test to use it, we should be fine)
