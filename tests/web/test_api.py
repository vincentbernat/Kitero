try:
    import unittest2 as unittest
except ImportError: # pragma: no cover
    import unittest

import flask
import yaml
import json
import time

from kitero.web import app
from kitero.web.rpc import RPCClient
from kitero.web.serve import configure
from kitero.helper.router import Router
from kitero.helper.service import Service

class TestApi(unittest.TestCase):
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
"""))
        self.service = Service({}, r) # helper
        configure(app, dict(web=dict(expire=2)))
        self.app = app.test_client() # web
        time.sleep(0.1)

    def tearDown(self):
        RPCClient.clean()
        self.service.stop()

    def test_current(self):
        """Grab current settings."""
        rv = self.app.get("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.15"})
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
        self.assertIn('time', result)
        self.assertEqual(result['value'], dict(ip='192.168.1.15'))

    def test_interfaces(self):
        """Get the list of interfaces."""
        rv = self.app.get("/api/1.0/interfaces")
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['value'],
                         {'eth2': {'qos': {},
                                   'name': 'WAN',
                                   'description': 'My second interface'},
                          'eth1': {'qos': 
                                   {'qos1':
                                        {'netem': 'delay 100ms 10ms distribution experimental',
                                         'bandwidth': '100mbps',
                                         'name': '100M',
                                         'description': 'My first QoS'},
                                    'qos2':
                                        {'netem': 'delay 200ms 10ms',
                                         'bandwidth': '10mbps',
                                         'name': '10M',
                                         'description': 'My second QoS'}},
                                   'name': 'LAN',
                                   'description': 'My first interface'}})

    def test_bind(self):
        """Try to bind some clients."""
        # First client
        rv = self.app.put("/api/1.0/bind/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.15"})
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['value'], { 'ip': '192.168.1.15',
                                            'interface': 'eth1',
                                            'qos': 'qos1' })
        # Second client
        rv = self.app.put("/api/1.0/bind/eth1/qos2",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['value'], { 'ip': '192.168.1.16',
                                            'interface': 'eth1',
                                            'qos': 'qos2' })
        # Check first
        rv = self.app.get("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.15"})
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['value'], dict(ip='192.168.1.15',
                                               interface='eth1',
                                               qos='qos1'))
        # Check second
        rv = self.app.get("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
        self.assertEqual(result['value'], dict(ip='192.168.1.16',
                                               interface='eth1',
                                               qos='qos2'))
        # Rebind second client
        rv = self.app.put("/api/1.0/bind/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        rv = self.app.get("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16',
                                               interface='eth1',
                                               qos='qos1'))

    def test_post_put_get(self):
        """Bind with POST and GET, get current with PUT"""
        rv = self.app.get("/api/1.0/bind/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        rv = self.app.post("/api/1.0/bind/eth1/qos1",
                           environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        rv = self.app.put("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 405)

    def test_inexistant_bind(self):
        """Try to bind to incorrect interfaces"""
        rv = self.app.put("/api/1.0/bind/eth3/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 500)

    def test_unbind(self):
        """Try to unbind a client"""
        rv = self.app.put("/api/1.0/bind/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16',
                                               interface='eth1',
                                               qos='qos1'))
        rv = self.app.put("/api/1.0/unbind",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16'))
        # Double unbind
        rv = self.app.put("/api/1.0/unbind",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.25"})
        rv = self.app.put("/api/1.0/unbind",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.25"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.25'))

    def test_inexistant_api(self):
        """Call inexistant API"""
        rv = self.app.get("/api/1.0/notexists")
        self.assertEqual(rv.status_code, 404)
        rv = self.app.get("/api/1.1/notexists")
        self.assertEqual(rv.status_code, 404)
        rv = self.app.get("/api/1.1/current")
        self.assertEqual(rv.status_code, 404)

    def test_expiration(self):
        """Test expiration"""
        rv = self.app.put("/api/1.0/bind/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16',
                                               interface='eth1',
                                               qos='qos1'))
        time.sleep(1)
        # Not expired
        rv = self.app.get("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16',
                                               interface='eth1',
                                               qos='qos1'))
        time.sleep(2.5)
        # Expired
        rv = self.app.get("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16'))
        # Rebind
        rv = self.app.put("/api/1.0/bind/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16',
                                               interface='eth1',
                                               qos='qos1'))
        time.sleep(0.2)
        # Not expired
        rv = self.app.get("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'], dict(ip='192.168.1.16',
                                               interface='eth1',
                                               qos='qos1'))

    def test_stats(self):
        """Test statistics"""
        rv = self.app.get("/api/1.0/stats")
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'],
                         {'eth1': {'clients': 0, 'details': {}},
                          'eth2': {'clients': 0, 'details': {}}})
        rv = self.app.put("/api/1.0/bind/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        # Try to get stats now, we will get the same result!
        when = result['time']
        rv = self.app.get("/api/1.0/stats")
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'],
                         {'eth1': {'clients': 0, 'details': {}},
                          'eth2': {'clients': 0, 'details': {}}})
        self.assertEqual(result['time'], when)
        # Wait a bit
        time.sleep(2)
        rv = self.app.get("/api/1.0/stats")
        self.assertEqual(rv.status_code, 200)
        result = json.loads(rv.data)
        self.assertEqual(result['value'],
                         {'eth1': {'clients': 1,
                                   'details': {'192.168.1.16': {}}},
                          'eth2': {'clients': 0, 'details': {}}})
