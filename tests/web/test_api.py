try:
    import unittest2 as unittest
except ImportError:
    import unittest

import threading
import time
import cherrypy
import urllib2
import yaml
import json

from kitero.web.root import KiteroWebService
from kitero.helper.router import Router
from kitero.helper.service import Service

class TestApi10(unittest.TestCase):
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
  qos1:
    description: "My first QoS"
    bandwidth: 100mbps
    delay: 100ms 10ms distribution experimental
  qos2:
    description: "My second QoS"
    bandwidth: 10mbps
    delay: 200ms 10ms
"""))
        # Start the service in a separate process
        self.service = Service({}, r)
        self.sthread = threading.Thread(target=self.service.start)
        self.sthread.start()
        # Start CherryPy
        self.wthread = threading.Thread(target=KiteroWebService.run,
                                        args=({'web': { 
                        'advanced': { 'global': {'environment': 'embedded'}}}},))
        self.wthread.start()
        time.sleep(0.2)         # Safety

    def test_api(self):
        """Various test on the API"""
        # First, a simple request to get our current bind.
        content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/current")
        headers = content.info()
        output = content.read()
        output = json.loads(output)
        self.assertEqual(content.getcode(), 200)
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(output, {'ip': '127.0.0.1'})
        # The same request with a slash
        content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/current")
        self.assertEqual(content.getcode(), 200)
        # The index page
        content = urllib2.urlopen("http://127.0.0.1:8187/")
        self.assertEqual(content.getcode(), 200)
        # Inexistant requests
        for url in ["/api/1.0/curren", "/a", "/api", "/api/1.1", "/api/1.0"]:
            with self.assertRaises(urllib2.HTTPError) as he:
                content = urllib2.urlopen("http://127.0.0.1:8187/%s" % url)
            self.assertNotEqual(he.exception.code, 200)
        # Get the interfaces
        content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/interface")
        headers = content.info()
        output = content.read()
        output = json.loads(output)
        self.assertEqual(content.getcode(), 200)
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(output, {
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
                    'qos': {}
                    }
                })
        # Bind our client to one interface
        # With GET
        with self.assertRaises(urllib2.HTTPError) as he:
            content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/interface/eth1/qos1")
        self.assertEqual(he.exception.code, 405)
        # With POST
        content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/interface/eth1/qos1", "")
        headers = content.info()
        output = content.read()
        output = json.loads(output)
        self.assertEqual(content.getcode(), 200)
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(output, { 'ip': '127.0.0.1', 'interface': 'eth1', 'qos': 'qos1' })
        self.assertEqual(content.geturl(), "http://127.0.0.1:8187/api/1.0/current")
        # Bind to another interface
        content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/interface/eth1/qos2", "")
        headers = content.info()
        output = content.read()
        output = json.loads(output)
        self.assertEqual(content.getcode(), 200)
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(output, { 'ip': '127.0.0.1', 'interface': 'eth1', 'qos': 'qos2' })
        self.assertEqual(content.geturl(), "http://127.0.0.1:8187/api/1.0/current")
        # Bind to an incorrect interface
        with self.assertRaises(urllib2.HTTPError) as he:
            content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/interface/eth3/qos2", "")
        self.assertNotEqual(he.exception.code, 200)
        # Bind to just an interface
        with self.assertRaises(urllib2.HTTPError) as he:
            content = urllib2.urlopen("http://127.0.0.1:8187/api/1.0/interface/eth3/", "")
        self.assertEqual(he.exception.code, 404)

    def tearDown(self):
        self.service.server.close()
        cherrypy.server.stop()
        cherrypy.engine.exit()
        self.sthread.join()
        self.wthread.join(1)    # Will never terminate because it
                                # waits for main thread to
                                # terminate. We won't terminate.
