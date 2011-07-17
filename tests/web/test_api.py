try:
    import unittest2 as unittest
except ImportError:
    import unittest

import flask
import yaml
import json
import time

from kitero.web import app
from kitero.web.rpc import RPCClient
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
    delay: 100ms 10ms distribution experimental
  qos2:
    name: 10M
    description: "My second QoS"
    bandwidth: 10mbps
    delay: 200ms 10ms
"""))
        self.service = Service({}, r) # helper
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
        rv = self.app.get("/api/1.0/interface")
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
                                        {'delay': '100ms 10ms distribution experimental',
                                         'bandwidth': '100mbps',
                                         'name': '100M',
                                         'description': 'My first QoS'},
                                    'qos2':
                                        {'delay': '200ms 10ms',
                                         'bandwidth': '10mbps',
                                         'name': '10M',
                                         'description': 'My second QoS'}},
                                   'name': 'LAN',
                                   'description': 'My first interface'}})

    def test_bind(self):
        """Try to bind some clients."""
        # First client
        rv = self.app.put("/api/1.0/interface/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.15"})
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
        # Second client
        rv = self.app.put("/api/1.0/interface/eth1/qos2",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.mimetype, 'application/json')
        result = json.loads(rv.data)
        self.assertEqual(result['status'], 0)
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
        rv = self.app.put("/api/1.0/interface/eth1/qos1",
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
        rv = self.app.get("/api/1.0/interface/eth1/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        rv = self.app.post("/api/1.0/interface/eth1/qos1",
                           environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 200)
        rv = self.app.put("/api/1.0/current",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 405)

    def test_inexistant_bind(self):
        """Try to bind to incorrect interfaces"""
        rv = self.app.put("/api/1.0/interface/eth3/qos1",
                          environ_overrides={"REMOTE_ADDR": "192.168.1.16"})
        self.assertEqual(rv.status_code, 500)

    def test_inexistant_api(self):
        """Call inexistant API"""
        rv = self.app.get("/api/1.0/notexists")
        self.assertEqual(rv.status_code, 404)
        rv = self.app.get("/api/1.1/notexists")
        self.assertEqual(rv.status_code, 404)
        rv = self.app.get("/api/1.1/current")
        self.assertEqual(rv.status_code, 404)
