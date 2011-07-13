try:
    import unittest2 as unittest
except ImportError:
    import unittest

import os
import tempfile
import shutil
import logging
import re
import threading
import time
import rpyc
import yaml

from kitero.helper.service import Service
from kitero.helper.router import Router, Interface, QoS

class TestBadOptions(unittest.TestCase):
    def test_without_args(self):
        """Run the service without arguments"""
        with self.assertRaises(SystemExit) as se:
            Service.run([])
        self.assertNotEqual(se.exception, 0)

    def test_with_unknown_args(self):
        """Run the service with incorrect args"""
        with self.assertRaises(SystemExit) as se:
            Service.run(["-y", "squid"])
        self.assertNotEqual(se.exception, 0)

    def test_with_incorrect_args(self):
        """Run the service with options not set correctly"""
        with self.assertRaises(SystemExit) as se:
            Service.run(["-l"])
        self.assertNotEqual(se.exception, 0)
        with self.assertRaises(SystemExit) as se:
            Service.run(["opt1", "opt2"])
        self.assertNotEqual(se.exception, 0)

    def test_with_inexistant_configuration(self):
        """Run the service with a missing configuration file"""
        with self.assertRaises(SystemExit) as se:
            Service.run(["/non/existant/config/file.yaml"])
        self.assertNotEqual(se.exception, 0)

class FakeService(Service):
    """Fake service to test start of service through run()"""
    def __init__(self, config, binder=None):
        l = logging.getLogger("kitero.helper.service")
        l.debug("Debug message")
        l.info("Info message")
        l.warning("Warning message")
        self.server = None

class TestGoodOptions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.mkdtemp()
        self.conf = os.path.join(temp, "config")
        self.log = os.path.join(temp, "log")
        c = file(self.conf, "w")
        c.write("""
router:
  clients: eth0
""")
        c.close()
        # We need to reset logging module...
        for h in [logging.root.handlers[:]]:
            logging.root.removeHandler(h)
            logging.root.setLevel(logging.WARNING)
        self.re = re.compile(r"^[^ ]+ [^ ]+ kitero.helper.service\[\d+\] (\w+): (.*)")

    def tearDown(self):
        shutil.rmtree(os.path.dirname(self.conf))

    def test_start_without_arguments(self):
        """Run with just an empty config file"""
        with self.assertRaises(SystemExit) as se:
            FakeService.run([self.conf])
        self.assertEqual(se.exception, 0)

    def test_logging_to_syslog(self):
        """Ask to log to syslog"""
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-s", self.conf])
        self.assertEqual(se.exception, 0)
        # We can't really check

    def test_logging_to_file(self):
        """Log to a file"""
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-l", self.log, self.conf])
        self.assertEqual(se.exception, 0)
        gotwarn = False
        for line in file(self.log):
            mo = self.re.match(line)
            self.assertIsNotNone(mo)
            self.assertEqual(mo.group(1), "WARNING")
            if mo.group(2) == "Warning message":
                gotWarn = True
        self.assertTrue(gotWarn)

    def test_debugging(self):
        """Enable debugging"""
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-d", "-l", self.log, self.conf])
        self.assertEqual(se.exception, 0)
        logs = file(self.log).read().split("\n")
        gotinfo = False
        for line in file(self.log):
            mo = self.re.match(line)
            self.assertIsNotNone(mo)
            self.assertIn(mo.group(1), ["WARNING", "INFO"])
            if mo.group(2) == "Info message":
                gotinfo = True
        self.assertTrue(gotinfo)

    def test_more_debugging(self):
        """Enable more debugging"""
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-dd", "-l", self.log, self.conf])
        self.assertEqual(se.exception, 0)
        gotdebug = False
        for line in file(self.log):
            mo = self.re.match(line)
            self.assertIsNotNone(mo)
            self.assertIn(mo.group(1), ["WARNING", "INFO", "DEBUG"])
            if mo.group(2) == "Debug message":
                gotdebug = True
        self.assertTrue(gotdebug)

    def test_attach_binder(self):
        """Attach a binder to service"""
        class Binder(object):
            def notify(self, event, source, **kwargs):
                pass
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-dd", "-l", self.log, self.conf], binder=Binder)
        self.assertEqual(se.exception, 0)

class TestRPCService(unittest.TestCase):
    def setUp(self):
        r = Router.load(yaml.load("""
clients: eth0
interfaces:
  eth1:
    description: "My first interface"
    qos:
      - qos1
      - qos2
  eth2:
    description: "My second interface"
    qos:
      - qos1
      - qos3
qos:
  qos1:
    description: "My first QoS"
    bandwidth: 100mbps
    delay: 100ms 10ms distribution experimental
  qos2:
    description: "My second QoS"
    bandwidth: 10mbps
    delay: 200ms 10ms
  qos3:
    description: "My third QoS"
    bandwidth: 1mbps
    delay: 500ms 30ms
"""))
        # Start the service in a separate process
        self.service = Service({}, r)
        self.thread = threading.Thread(target=self.service.start)
        self.thread.start()
        time.sleep(0.2)         # Safety

    def test_service_multiple_clients(self):
        """Check if the service is running and accept several clients"""
        clients = []
        threads = []
        for c in range(1, 50):
            clients.append(rpyc.connect('127.0.0.1', 18861))
        def work(c):
            c.ping()
            c.root.bind("192.168.1.5", "eth1", "qos1")
            self.assertEqual(c.root.get_client("192.168.1.5"), ("eth1", "qos1"))
            c.close()
        for c in clients:
            threads.append(threading.Thread(target=work, args=c))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_service_router(self):
        """Grab router information from the service"""
        c = rpyc.connect('127.0.0.1', 18861)
        c.ping()
        interfaces = c.root.get_interfaces()
        # We need to compare strings because we cannot compare local
        # and remote dictionary. Rely on sorting
        self.assertEqual(str(interfaces), str({
                "eth1": {
                    'description': "My first interface",
                    'qos': {
                        'qos1': {
                            'description': "My first QoS",
                            "bandwidth": "100mbps",
                            "delay": "100ms 10ms distribution experimental" },
                        'qos2': {
                            'description': "My second QoS",
                            "bandwidth": "10mbps",
                            "delay": "200ms 10ms" }
                        }
                    },
                "eth2": {
                    'description': "My second interface",
                    'qos': {
                        'qos1': {
                            'description': "My first QoS",
                            "bandwidth": "100mbps",
                            "delay": "100ms 10ms distribution experimental" },
                        'qos3': {
                            'description': "My third QoS",
                            "bandwidth": "1mbps",
                            "delay": "500ms 30ms" }
                        }
                    }
                }))
        c.close()

    def test_bind_client(self):
        """Bind clients"""
        c = rpyc.connect('127.0.0.1', 18861)
        c.ping()
        c.root.bind_client('192.168.1.1', 'eth2', 'qos3')
        self.assertEqual(c.root.get_client('192.168.1.1'), ('eth2', 'qos3'))
        c.root.bind_client('192.168.1.1', 'eth2', 'qos1')
        self.assertEqual(c.root.get_client('192.168.1.1'), ('eth2', 'qos1'))
        c.root.bind_client('192.168.1.2', 'eth2', 'qos1')
        self.assertEqual(c.root.get_client('192.168.1.2'), ('eth2', 'qos1'))
        c.root.bind_client('192.168.1.3', 'eth1', 'qos1')
        self.assertEqual(c.root.get_client('192.168.1.3'), ('eth1', 'qos1'))
        self.assertEqual(c.root.get_client('192.168.1.4'), None)
        c.close()
        

    def tearDown(self):
        self.service.server.close()
        self.thread.join()
