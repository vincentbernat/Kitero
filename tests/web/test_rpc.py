try:
    import unittest2 as unittest
except ImportError:
    import unittest

import threading
import time

from kitero.web import app
from kitero.web.serve import configure
from kitero.web.rpc import RPCClient, RPCException
from kitero.helper.router import Router
from kitero.helper.service import Service

class TestRPCClient(unittest.TestCase):
    def setUp(self):
        r = Router.load({'clients': 'eth0'})
        # Start the service
        self.service = Service({}, r)
        time.sleep(0.2)         # Safety
        # Configure app
        configure(app)

    def tearDown(self):
        # Hack to force close
        RPCClient.clean()
        self.service.stop()

    def atest_normal_operation(self):
        """Request some attributes from the RPC service"""
        threads = []
        def work():
            RPCClient.call("interfaces")
        for c in range(1,10):
            t = threading.Thread(target=work)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def test_reconnection(self):
        """Check if we can reconnect"""
        RPCClient.call("interfaces")
        self.tearDown()
        self.setUp()
        RPCClient.call("interfaces")
        self.tearDown()
        with self.assertRaises(IOError):
            RPCClient.call("interfaces")
        self.setUp()

    def test_exception(self):
        """Check that we get exceptions"""
        with self.assertRaises(RPCException) as e:
            RPCClient.call("unknown")
        str(e.exception)
