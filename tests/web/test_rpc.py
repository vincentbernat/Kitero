try:
    import unittest2 as unittest
except ImportError:
    import unittest

import threading
import time

from kitero.web.rpc import RPCClient
from kitero.helper.router import Router
from kitero.helper.service import Service

class TestRPCClient(unittest.TestCase):
    def setUp(self):
        r = Router.load({'clients': 'eth0'})
        # Start the service in a separate thread
        self.service = Service({}, r)
        self.thread = threading.Thread(target=self.service.start)
        self.thread.start()
        time.sleep(0.2)         # Safety

    def tearDown(self):
        self.service.server.close()
        self.thread.join()

    def test_normal_operation(self):
        """Request some attributes from the RPC service"""
        threads = []
        def work():
            RPCClient.get("get_interfaces")()
        for c in range(1,10):
            t = threading.Thread(target=work)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def test_reconnection(self):
        """Check if we can reconnect"""
        RPCClient.get("get_interfaces")()
        self.tearDown()
        self.setUp()
        RPCClient.get("get_interfaces")()
        self.tearDown()
        with self.assertRaises(IOError):
            RPCClient.get("get_interfaces")()
