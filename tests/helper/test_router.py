try:
    import unittest2 as unittest
except ImportError: # pragma: no cover
    import unittest

import yaml
import os
import tempfile
import shutil
import cPickle as pickle
import zope.interface

from kitero.helper.router import Router, Interface, QoS
from kitero.helper.interface import IBinder, IStatsProvider

class TestQoSBasic(unittest.TestCase):
    def test_build_empty_qos(self):
        """Build an empty QoS settings"""
        q = QoS("qos1", "My first QoS")
        self.assertEqual(q.name, "qos1")
        self.assertEqual(q.description, "My first QoS")
        self.assertEqual(q.settings, {})

    def test_build_qos(self):
        """Build a regular QoS settings"""
        q = QoS("qos2", "My second QoS", {"bandwidth": "150mbps"})
        self.assertEqual(q.name, "qos2")
        self.assertEqual(q.description, "My second QoS")
        self.assertEqual(q.settings, {"bandwidth": "150mbps"})
        str(q)

    def test_qos_equality(self):
        """QoS settings equality"""
        self.assertEqual(QoS("qos1", "Description", {}),
                         QoS("qos1", "Description", {}))
        self.assertEqual(QoS("qos1", "Description", {"settings": "other"}),
                         QoS("qos1", "Description", {"settings": "other"}))
        self.assertNotEqual(QoS("qos1", "Description", {}),
                         QoS("qos1", "Different description", {}))
        self.assertNotEqual(QoS("qos1", "Description", {}),
                         QoS("qos1", "Description", {"settings": "other"}))
        self.assertNotEqual(QoS("qos1", "Description", {}),
                            QoS("qos2", "Description", {}))
        self.assertNotEqual(QoS("qos1", "Description", {}), "qos1")

    def test_pickle(self):
        """Pickling"""
        self.assertEqual(QoS("qos1", "Description", {"settings": "other"}),
                         pickle.loads(pickle.dumps(
                    QoS("qos1", "Description", {"settings": "other"}))))


class TestInterfaceBasic(unittest.TestCase):
    def test_build_empty_interface(self):
        """Build an empty interface (no QoS)"""
        i = Interface("eth0", "My first interface")
        self.assertEqual(i.name, "eth0")
        self.assertEqual(i.description, "My first interface")
        self.assertEqual(i.qos, {})

    def test_build_interface(self):
        """Build a regular interface"""
        q1 = QoS("100M", "My first QoS")
        q2 = QoS("10M", "My second QoS")
        i = Interface("eth1", "My second interface", {'qos1': q1, 'qos2': q2})
        self.assertEqual(i.name, "eth1")
        self.assertEqual(i.description, "My second interface")
        self.assertEqual(i.qos, {'qos1': q1, 'qos2': q2})
        str(i)

    def test_interface_equality(self):
        """Interface equality"""
        self.assertEqual(Interface("eth0", "My first interface"),
                         Interface("eth0", "My first interface"))
        self.assertNotEqual(Interface("eth0", "My first interface"),
                            Interface("eth0", "My second interface"))
        self.assertNotEqual(Interface("eth0", "My first interface"),
                            Interface("eth1", "My first interface"))
        self.assertEqual(Interface("eth0", "My first interface",
                                   {'qos1': QoS("100M", ""), 'qos2': QoS("10M", "")}),
                         Interface("eth0", "My first interface",
                                   {'qos1': QoS("100M", ""), 'qos2': QoS("10M", "")}))
        self.assertNotEqual(Interface("eth0", "My first interface",
                                      {'qos1': QoS("100M", ""), 'qos2': QoS("10M", "")}),
                            Interface("eth0", "My first interface",
                                      {'qos1': QoS("100M", ""),
                                       'qos2': QoS("10M", "Different")}))
        self.assertNotEqual(Interface("eth0", "My first interface",
                                      {'qos1': QoS("100M", ""),
                                       'qos2':QoS("10M", "")}),
                            "eth0")

    def test_pickle(self):
        """Pickling"""
        i = Interface("eth0", "My first interface",
                      {'qos1': QoS("100M", ""), 'qos2': QoS("10M", "")})
        self.assertEqual(i, pickle.loads(pickle.dumps(i)))
        
class TestRouterBasic(unittest.TestCase):
    def test_empty_router(self):
        """Create an empty router"""
        r = Router("eth0")
        self.assertEqual(r.incoming, "eth0")
        self.assertEqual(r.interfaces, {})
        self.assertEqual(r.clients, {})

    def test_router(self):
        """Create a complete router"""
        q1 = QoS("100M", "My first QoS")
        q2 = QoS("10M", "My second QoS")
        i1 = Interface("LAN", "My second interface", {'qos1': q1, 'qos2': q2})
        i2 = Interface("WAN", "My third interface", {'qos1': q1})
        r = Router("eth0", interfaces={'eth1': i1, 'eth2': i2})
        self.assertEqual(r.incoming, "eth0")
        self.assertEqual(r.clients, {})
        self.assertEqual(r.interfaces, {'eth1': i1, 'eth2': i2})

    def test_router_with_shared_interface(self):
        """Try to create router with duplicate interfaces"""
        i1 = Interface("LAN", "My second interface")
        i2 = Interface("WAN", "My third interface")
        with self.assertRaises(ValueError):
            r = Router("eth0", interfaces={'eth0': i1, 'eth1': i2})

    def test_bind_client(self):
        """Client binding"""
        q1 = QoS("100M", "My first QoS")
        q2 = QoS("10M", "My second QoS")
        i1 = Interface("LAN", "My second interface", {'qos1': q1, 'qos2': q2})
        i2 = Interface("WAN", "My third interface", {'qos1': q1})
        r = Router("eth0", interfaces={'eth1': i1, 'eth2': i2})
        r.bind("192.168.15.2", "eth1", "qos2")
        r.bind("192.168.15.3", "eth2", "qos1")
        r.bind("192.168.15.4", "eth1", "qos2")
        self.assertEqual(r.clients["192.168.15.2"], ('eth1', 'qos2'))
        self.assertEqual(r.clients["192.168.15.3"], ('eth2', 'qos1'))
        self.assertEqual(r.clients["192.168.15.4"], ('eth1', 'qos2'))

    def test_bind_inexistant(self):
        """Client binding to inexistant interface or QoS"""
        q1 = QoS("100M", "My first QoS")
        q2 = QoS("10M", "My second QoS")
        i1 = Interface("LAN", "My second interface", {'qos1': q1, 'qos2': q2})
        i2 = Interface("WAN", "My third interface", {'qos1': q1})
        r = Router("eth0", interfaces={'eth1': i1, 'eth2': i2})
        with self.assertRaises(KeyError):
            r.bind("192.168.15.2", "eth3", "qos2")
        with self.assertRaises(KeyError):
            r.bind("192.168.15.2", "eth2", "qos2")

    def test_double_bind_client(self):
        """Try to bind a client twice"""
        q1 = QoS("100M", "My first QoS")
        i1 = Interface("LAN", "My third interface", {'qos1': q1})
        r = Router("eth0", interfaces={'eth2': i1})
        r.bind("192.168.15.2", "eth2", "qos1")
        r.bind("192.168.15.3", "eth2", "qos1")
        with self.assertRaises(ValueError):
            r.bind("192.168.15.3", "eth2", "qos1")
        self.assertEqual(r.clients["192.168.15.2"], ('eth2', 'qos1'))
        self.assertEqual(r.clients["192.168.15.3"], ('eth2', 'qos1'))

    def test_unbind_client(self):
        """Unbind a client"""""
        q1 = QoS("100M", "My first QoS")
        i1 = Interface("WAN", "My third interface", {'qos1': q1})
        r = Router("eth0", interfaces={'eth2': i1})
        r.bind("192.168.15.2", "eth2", "qos1")
        r.bind("192.168.15.3", "eth2", "qos1")
        r.unbind("192.168.15.2")
        with self.assertRaises(KeyError):
            r.clients["192.168.15.2"]
        self.assertEqual(len(r.clients), 1)
        r.unbind("192.168.15.2")
        self.assertEqual(len(r.clients), 1)

    def test_equality(self):
        """Test equality of two routers"""
        q1 = QoS("100M", "My first QoS")
        q2 = QoS("10M", "My second QoS")
        i1 = Interface("LAN", "My second interface", {'qos1': q1, 'qos2': q2})
        i2 = Interface("WAN", "My third interface", {'qos1': q1})
        r = Router("eth0", interfaces={'eth1': i1, 'eth2': i2})
        self.assertEqual(r, Router("eth0", interfaces={
                    'eth1': Interface("LAN", "My second interface",
                                      {'qos1': QoS("100M", "My first QoS"),
                                       'qos2': q2}),
                    'eth2': Interface("WAN", "My third interface", {'qos1': q1})
                    }))
        self.assertNotEqual(r, Router("eth0",
                                      interfaces={
                    'eth1': Interface("LAN", "My second interface",
                                      {'qos1': QoS("100M", "My first QoS"),
                                       'qos2': q2}),
                    'eth3': Interface("WAN", "My third interface", {'qos1': q1})
                    }))
        self.assertNotEqual(r, Router("eth0", interfaces={
                    'eth1': Interface("LAN", "My second interface",
                                      {'qos3': QoS("3G", "My first QoS"), 'qos2': q2}),
                    'eth2': Interface("WAN", "My third interface", {'qos1': q1})
                    }))
        self.assertNotEqual(r, Router("eth0"))
        self.assertNotEqual(r, "eth0")
        # With equality, clients are not considered
        r.bind("192.168.15.3", "eth2", "qos1")
        self.assertEqual(r, Router("eth0", interfaces={
                    'eth1': Interface("LAN", "My second interface",
                                      {'qos1': QoS("100M", "My first QoS"),
                                       'qos2': q2}),
                    'eth2': Interface("WAN", "My third interface", {'qos1': q1})
                    }))

    def test_pickle(self):
        """Pickling"""
        q1 = QoS("100M", "My first QoS")
        q2 = QoS("10M", "My second QoS")
        i1 = Interface("LAN", "My second interface", {'qos1': q1, 'qos2': q2})
        i2 = Interface("WAN", "My third interface", {'qos1': q1})
        r = Router("eth0", interfaces={'eth1': i1, 'eth2': i2})
        self.assertEqual(r, pickle.loads(pickle.dumps(r)))
        self.assertEqual(r.clients, pickle.loads(pickle.dumps(r)).clients)
        r.bind("192.168.15.2", "eth2", "qos1")
        self.assertEqual(r, pickle.loads(pickle.dumps(r)))
        self.assertEqual(r.clients, pickle.loads(pickle.dumps(r)).clients)

class TestRouterLoad(unittest.TestCase):
    def test_load(self):
        """Load router from YAML representation"""
        doc = """
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
    name: "100M"
    description: "My first QoS"
    bandwidth: 100mbps
    netem: delay 100ms 10ms distribution experimental
  qos2:
    name: "10M"
    description: "My second QoS"
    bandwidth: 10mbps
    netem: delay 200ms 10ms
  qos3:
    name: "1M"
    description: "My third QoS"
    bandwidth: 1mbps
    netem: delay 500ms 30ms
"""
        r = Router.load(yaml.load(doc))
        self.assertEqual(r.incoming, "eth0")
        self.assertEqual(r.clients, {})
        self.assertEqual(r.interfaces["eth1"],
                         Interface("LAN", "My first interface",
                                    qos={'qos1': QoS("100M", "My first QoS",
                                             {"bandwidth": "100mbps",
                                              "netem": "delay 100ms 10ms distribution experimental"}),
                                         'qos2': QoS("10M", "My second QoS",
                                             {"bandwidth": "10mbps",
                                              "netem": "delay 200ms 10ms"})}))
        self.assertEqual(r.interfaces["eth2"],
                         Interface("WAN", "My second interface",
                                   qos={'qos1': QoS("100M", "My first QoS",
                                            {"bandwidth": "100mbps",
                                             "netem": "delay 100ms 10ms distribution experimental"}),
                                        'qos3': QoS("1M", "My third QoS",
                                            {"bandwidth": "1mbps",
                                             "netem": "delay 500ms 30ms"})}))
        self.assertEqual(len(r.interfaces), 2)

    def test_load_unknown_qos(self):
        """Load router from YAML with unknown QoS"""
        doc = """
clients: eth0
interfaces:
  eth1:
    name: LAN
    description: "My first interface"
    qos:
      - qos3
"""
        with self.assertRaises(KeyError):
            r = Router.load(yaml.load(doc))

    def test_load_with_missing(self):
        """Load router with missing information"""
        doc = """
interfaces:
  eth1:
    description: "My first interface"
"""
        with self.assertRaises(ValueError):
            r = Router.load(yaml.load(doc))

    def test_load_minimal(self):
        """Load router with minimal information"""
        doc = """
clients: eth0
"""
        r = Router.load(yaml.load(doc))
        self.assertEqual(r.interfaces, {})
        self.assertEqual(r.incoming, "eth0")
        self.assertEqual(r.clients, {})

    def test_load_almost_minimal(self):
        """Load router with almost minimal information"""
        doc = """
clients: eth0
interfaces:
  eth1:
    name: LAN
    description: "My first interface"
"""
        r = Router.load(yaml.load(doc))
        self.assertEqual(r.interfaces, {'eth1': Interface("LAN", "My first interface")})
        self.assertEqual(r.incoming, "eth0")
        self.assertEqual(r.clients, {})

class TestRouterObserver(unittest.TestCase):
    def setUp(self):
        q1 = QoS("100M", "My first QoS")
        q2 = QoS("10M", "My second QoS")
        i1 = Interface("LAN", "My second interface", {'qos1': q1, 'qos2': q2})
        i2 = Interface("WAN", "My third interface", {'qos1': q1})
        self.router = Router("eth0", interfaces={'eth1': i1, 'eth2': i2})

    def test_register_observer(self):
        """Register an observer and receive events"""
        last = {}
        class Observer(object):
            zope.interface.implements(IBinder)
            def notify(self, event, source, **kwargs):
                last['event'] = event
                last['source'] = source
                last['args'] = kwargs
        self.router.register(Observer())
        self.router.bind("192.168.15.2", "eth2", "qos1")
        self.assertEqual(last['event'], 'bind')
        self.assertEqual(last['source'], self.router)
        self.assertEqual(last['args']['client'], '192.168.15.2')
        self.assertEqual(last['args']['interface'], 'eth2')
        self.assertEqual(last['args']['qos'], 'qos1')
        self.router.bind("192.168.15.3", "eth2", "qos1")
        self.assertEqual(last['event'], 'bind')
        self.assertEqual(last['source'], self.router)
        self.assertEqual(last['args']['client'], '192.168.15.3')
        self.assertEqual(last['args']['interface'], 'eth2')
        self.assertEqual(last['args']['qos'], 'qos1')
        self.router.unbind("192.168.15.3")
        self.assertEqual(last['event'], 'unbind')
        self.assertEqual(last['source'], self.router)
        self.assertEqual(last['args']['client'], '192.168.15.3')

    def test_register_not_observer(self):
        """Register something which is not an observer"""
        last = {}
        class Observer(object):
            def notify(self, event, source, **kwargs):
                """Will not be called"""
        with self.assertRaises(ValueError):
            self.router.register(Observer())

    def test_register_several_observers(self):
        """Register several observers"""
        events = {}
        class Observer(object):
            zope.interface.implements(IBinder)
            def notify(self, event, source, **kwargs):
                events[self] = event
        obs1 = Observer()
        obs2 = Observer()
        obs3 = Observer()
        self.router.register(obs1)
        self.router.register(obs2)
        self.router.register(obs3)
        self.router.bind("192.168.15.2", "eth2", "qos1")
        self.assertEqual(events, {obs1: 'bind',
                                  obs2: 'bind',
                                  obs3: 'bind'})

    def test_observer_pickling(self):
        """Check if observers are notified on unpickling"""
        temp = tempfile.mkdtemp()
        try:
            testfile = os.path.join(temp, "testfile.txt")
            self.router.register(PickableObserver(testfile))
            self.router.bind("192.168.15.2", "eth2", "qos1")
            self.assertEqual(file(testfile).read(), "bind\n")
            r = pickle.loads(pickle.dumps(self.router))
            self.assertEqual(self.router, r)
            self.assertEqual(self.router.clients, r.clients)
            self.assertEqual(file(testfile).read(), "bind\nbind\n")
        finally:
            shutil.rmtree(temp)

    def test_stats(self):
        """Register an observer that also implements IStatsProvider"""
        class Observer(object):
            zope.interface.implements(IBinder, IStatsProvider)
            def notify(self, event, source, **kwargs):
                """Do nothing"""
            def stats(self):
                return {'eth1': {'up': 47, 'down': 255},
                        'eth2': {'clients': 2, 'details': {'172.14.15.16': {'up': 1, 'down': 2}}}}
        self.assertEqual(self.router.stats,
                         {'eth1': {'clients': 0, 'details': {}},
                          'eth2': {'clients': 0, 'details': {}}})
        self.router.register(Observer())
        self.assertEqual(self.router.stats,
                         {'eth1': {'clients': 0, 'up': 47, 'down': 255, 'details': {}},
                          'eth2': {'clients': 0, 'details': {}}})

class PickableObserver(object):
    zope.interface.implements(IBinder)
    def __init__(self, target):
        self.target = target
    def notify(self, event, source, **kwargs):
        target = file(self.target, "a+")
        target.write("%s\n" % event)
        target.close
