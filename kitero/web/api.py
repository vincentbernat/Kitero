import time
import threading
import flask

from kitero.web import app
from kitero.web.decorators import jsonify
from kitero.web.rpc import RPCClient

def status(client):
    """Return the status of the given client"""
    current = RPCClient.call("client", client)
    if current is None: # Not bound
        return { 'ip': client }
    return {
        'ip': client,
        'interface': current[0],
        'qos': current[1]
        }

class Ping(object):
    def __init__(self):
        self.clients = {}
        self.lock = threading.Lock()

    def refresh(self, client):
        self.clients[client] = time.time()

    def expire(self):
        with self.lock:
            clients = self.clients.keys()
            current = time.time()
            for client in clients:
                if current - self.clients[client] > app.config['EXPIRE']:
                    # Expiration of `client`
                    del self.clients[client]
                    RPCClient.call("unbind_client", client)

ping = Ping()

@app.route("/api/1.0/current", methods=['GET'])
@jsonify
def current():
    """Return the current settings for the client.

    This API should be requested from time to time to let us know that
    the client is still alive. As soon as a client is not alive
    anymore, we may unbind it.

    The returned value exhibits the following format::

        { ip: '172.147.12.15',
          interface: 'eth1',
          qos: 'qos1' }

    If no interface is bound to the client, ``interface`` and ``qos``
    are absent of the answer.
    """
    client = flask.request.remote_addr
    ping.expire()
    ping.refresh(client)
    return status(client)

@app.route("/api/1.0/interfaces", methods=['GET'])
@jsonify
def interfaces():
    """Return the list of available interfaces.

    The returned value exhibits the following format::

      {
        "eth2": {
          "name": "WAN", 
          "description": "My second interface",
          "qos": {
            "qos1": {
              "name": "100M", 
              "description": "My first QoS",
              "bandwidth": "100mbps"
            }, 
            "qos3": {
              "name": "1M", 
              "description": "My third QoS",
              "bandwidth": "1mbps"
            }
          }
        }, 
        "eth1": {
          "name": "LAN", 
          "description": "My first interface",
          "qos": {
            "qos1": {
              "name": "100M", 
              "description": "My first QoS",
              "bandwidth": "100mbps"
            }
          }
        }
      }
    """
    interfaces = RPCClient.call("interfaces")
    return interfaces

@app.route("/api/1.0/bind/<interface>/<qos>", methods=['GET', 'POST', 'PUT'])
@jsonify
def bind(interface, qos):
    """Allow to set the current interface for the client.

    The result of this function is the same as :func:`current`.

    :param interface: Output interface requested
    :param qos: QoS settings requested
    """
    client = flask.request.remote_addr
    RPCClient.call("bind_client", client, interface, qos)
    ping.refresh(client)
    return status(client)

@app.route("/api/1.0/unbind", methods=['GET', 'POST', 'PUT'])
@jsonify
def unbind():
    """Unbind the client.

    The result of this function is the same as :func:`current`.
    """
    client = flask.request.remote_addr
    RPCClient.call("unbind_client", client)
    return status(client)
