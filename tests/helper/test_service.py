try:
    import unittest2 as unittest
except ImportError: # pragma: no cover
    import unittest

import os
import tempfile
import shutil
import logging
import re
import threading
import time
import yaml
import socket
import json
import zope.interface

from kitero.helper.serve import Service
from kitero.helper.router import Router, Interface, QoS
from kitero.helper.interface import IBinder

class TestBadOptions(unittest.TestCase):
    def test_without_args(self):
        """Run the service without arguments"""
        with self.assertRaises(SystemExit) as se:
            Service.run([])
        self.assertNotEqual(se.exception.code, 0)

    def test_with_unknown_args(self):
        """Run the service with incorrect args"""
        with self.assertRaises(SystemExit) as se:
            Service.run(["-y", "squid"])
        self.assertNotEqual(se.exception.code, 0)

    def test_with_incorrect_args(self):
        """Run the service with options not set correctly"""
        with self.assertRaises(SystemExit) as se:
            Service.run(["-l"])
        self.assertNotEqual(se.exception.code, 0)
        with self.assertRaises(SystemExit) as se:
            Service.run(["opt1", "opt2"])
        self.assertNotEqual(se.exception.code, 0)

    def test_with_inexistant_configuration(self):
        """Run the service with a missing configuration file"""
        with self.assertRaises(SystemExit) as se:
            Service.run(["/non/existant/config/file.yaml"])
        self.assertNotEqual(se.exception.code, 0)

class FakeService(Service):
    """Fake service to test start of service through run()"""
    def __init__(self, config, binder=None):
        l = logging.getLogger("kitero.helper.service")
        l.debug("Debug message")
        l.info("Info message")
        l.warning("Warning message")

    def wait(self):
        pass

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
        self.assertEqual(se.exception.code, 0)

    def test_logging_to_syslog(self):
        """Ask to log to syslog"""
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-s", self.conf])
        self.assertEqual(se.exception.code, 0)
        # We can't really check

    def test_logging_to_file(self):
        """Log to a file"""
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-l", self.log, self.conf])
        self.assertEqual(se.exception.code, 0)
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
        self.assertEqual(se.exception.code, 0)
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
        self.assertEqual(se.exception.code, 0)
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
            zope.interface.implements(IBinder)
            def notify(self, event, source, **kwargs): # pragma: no cover
                pass
        with self.assertRaises(SystemExit) as se:
            FakeService.run(["-dd", "-l", self.log, self.conf], binder=Binder())
        self.assertEqual(se.exception.code, 0)

class TestRPCService(unittest.TestCase):
    def setUp(self):
        r = Router.load(yaml.load("""
clients: eth0
interfaces:
  eth1:
    name: LAN
    description: "My first interface"
    qos:
      - qos1
      - qos2
  eth2:
    name: WAN
    description: "My second interface"
    qos:
      - qos1
      - qos3
qos:
  qos1:
    name: 100M
    description: "My first QoS"
    bandwidth: 100mbps
    netem: delay 100ms 10ms distribution experimental
  qos2:
    name: 10M
    description: "My second QoS"
    bandwidth: 10mbps
    netem: delay 200ms 10ms
  qos3:
    name: 1M
    description: "My third QoS"
    bandwidth: 1mbps
    netem: delay 500ms 30ms
"""))
        # Start the service in a separate process
        self.service = Service({}, r)
        time.sleep(0.2)         # Safety

    def test_service_multiple_clients(self):
        """Check if the service is running and accept several clients"""
        clients = []
        threads = []
        for c in range(1, 8):
            # Open connection to RPC
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(('127.0.0.1', 18861))
            clients.append(sock)
        self.i = 0
        def work(c):
            read, write = c.makefile('rb'), c.makefile('wb', 0)
            # ping
            write.write("%s\n" % json.dumps(("ping",)))
            answer = json.loads(read.readline())
            self.assertEqual(answer["status"], 0)
            # bind_client
            write.write("%s\n" % json.dumps(
                    ("bind_client", "192.168.1.5", "eth1", "qos1")))
            answer = json.loads(read.readline())
            self.assertEqual(answer["status"], 0)
            # client
            write.write("%s\n" % json.dumps(
                    ("client", "192.168.1.5")))
            answer = json.loads(read.readline())
            self.assertEqual(answer["status"], 0)
            self.assertEqual(answer["value"], ["eth1", "qos1"])
            c.close()
            self.i = self.i + 1 # global lock
        # Try outside a thread just to check
        work(clients.pop())
        next = clients.pop()
        for c in clients:
            threads.append(threading.Thread(target=work, args=(c,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        work(next)
        self.assertEqual(self.i, 7)

    def test_service_router(self):
        """Grab router information from the service"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 18861))
        read, write = sock.makefile('rb'), sock.makefile('wb', 0)
        write.write("%s\n" % json.dumps(("interfaces",)))
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], 0)
        # We need to compare strings because we cannot compare local
        # and remote dictionary. Rely on sorting
        self.assertEqual(answer["value"], {
                "eth1": {
                    'name': 'LAN',
                    'description': "My first interface",
                    'qos': {
                        'qos1': {
                            'name': '100M',
                            'description': "My first QoS",
                            "bandwidth": "100mbps",
                            "netem": "delay 100ms 10ms distribution experimental" },
                        'qos2': {
                            'name': '10M',
                            'description': "My second QoS",
                            "bandwidth": "10mbps",
                            "netem": "delay 200ms 10ms" }
                        }
                    },
                "eth2": {
                    'name': 'WAN',
                    'description': "My second interface",
                    'qos': {
                        'qos1': {
                            'name': '100M',
                            'description': "My first QoS",
                            "bandwidth": "100mbps",
                            "netem": "delay 100ms 10ms distribution experimental" },
                        'qos3': {
                            'name': '1M',
                            'description': "My third QoS",
                            "bandwidth": "1mbps",
                            "netem": "delay 500ms 30ms" }
                        }
                    }
                })
        sock.close()

    def test_bind_client(self):
        """Bind clients"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 18861))
        read, write = sock.makefile('rb'), sock.makefile('wb', 0)

        def bind(ip, eth, qos):
            write.write("%s\n" % json.dumps(("bind_client", ip, eth, qos)))
            answer = json.loads(read.readline())
            self.assertEqual(answer["status"], 0)
        def unbind(ip):
            write.write("%s\n" % json.dumps(("unbind_client", ip)))
            answer = json.loads(read.readline())
            self.assertEqual(answer["status"], 0)
        def check(ip, value):
            write.write("%s\n" % json.dumps(("client", ip)))
            answer = json.loads(read.readline())
            self.assertEqual(answer["status"], 0)
            self.assertEqual(answer["value"], value)
        def stats():
            write.write("%s\n" % json.dumps(("stats",)))
            answer = json.loads(read.readline())
            self.assertEqual(answer["status"], 0)
            return answer['value']
        self.assertEqual(stats(),
                         {'eth1': {'clients': 0, 'details': {}},
                          'eth2': {'clients': 0, 'details': {}}})
        bind("192.168.1.1", "eth2", "qos3")
        check("192.168.1.1", ["eth2", "qos3"])
        self.assertEqual(stats(),
                         {'eth1': {'clients': 0, 'details': {}},
                          'eth2': {'clients': 1, 'details': {'192.168.1.1': {}}}})
        bind('192.168.1.1', 'eth2', 'qos1')
        check('192.168.1.1', ['eth2', 'qos1'])
        bind('192.168.1.2', 'eth2', 'qos1')
        check('192.168.1.2', ['eth2', 'qos1'])
        self.assertEqual(stats(),
                         {'eth1': {'clients': 0, 'details': {}},
                          'eth2': {'clients': 2, 'details': {'192.168.1.1': {},
                                                             '192.168.1.2': {}}}})
        bind('192.168.1.3', 'eth1', 'qos1')
        check('192.168.1.3', ['eth1', 'qos1'])
        self.assertEqual(stats(),
                         {'eth1': {'clients': 1, 'details': {'192.168.1.3': {}}},
                          'eth2': {'clients': 2, 'details': {'192.168.1.1': {},
                                                             '192.168.1.2': {}}}})
        check('192.168.1.4', None)
        unbind('192.168.1.4')
        check('192.168.1.4', None)
        unbind('192.168.1.1')
        check('192.168.1.1', None)
        sock.close()

    def test_stats(self):
        """Grab stats"""
        # We won't get much since no real binder is attached
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 18861))
        read, write = sock.makefile('rb'), sock.makefile('wb', 0)

    def tearDown(self):
        self.service.stop()

class TestPersistency(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.config = yaml.load("""
clients: eth0
interfaces:
  eth1:
    name: LAN
    description: "My first interface"
    qos:
      - qos1
      - qos2
qos:
  qos1:
    name: 100M
    description: "My first QoS"
    bandwidth: 100mbps
    netem: delay 100ms 10ms distribution experimental
  qos2:
    name: 10M
    description: "My second QoS"
    bandwidth: 10mbps
    netem: delay 200ms 10ms
""")
        self.realSetup()

    def realSetup(self):
        self.router = Router.load(self.config)
        # Start the service in a separate process
        self.service = Service(dict(helper=dict(save=os.path.join(self.temp, "save.pickle"))),
                               self.router)
        time.sleep(0.2)         # Safety

    def test_persistency(self):
        """Test the use of persistency"""
        self.assertEqual(self.router.clients, {})
        self.router.bind("192.168.1.15", "eth1", "qos1")
        self.router.bind("192.168.1.16", "eth1", "qos2")
        self.router.bind("192.168.1.17", "eth1", "qos2")
        self.router.unbind("192.168.1.17")
        self.assertEqual(self.router.clients["192.168.1.15"], ("eth1", "qos1"))
        self.assertEqual(self.router.clients["192.168.1.16"], ("eth1", "qos2"))
        self.service.stop()
        self.realSetup()
        # Clients should have been restored
        self.assertEqual(self.router.clients["192.168.1.15"], ("eth1", "qos1"))
        self.assertEqual(self.router.clients["192.168.1.16"], ("eth1", "qos2"))

    def test_partial_persistency(self):
        """Test the use of persistency when configuration has changed"""
        self.router.bind("192.168.1.15", "eth1", "qos1")
        self.router.bind("192.168.1.16", "eth1", "qos2")
        self.service.stop()
        self.config['interfaces']['eth1']['qos'].remove('qos2')
        del self.config['qos']['qos2']
        self.realSetup()
        self.assertEqual(self.router.clients["192.168.1.15"], ("eth1", "qos1"))
        self.assertNotIn("192.168.1.16", self.router.clients)

    def tearDown(self):
        self.service.stop()
        shutil.rmtree(self.temp)
