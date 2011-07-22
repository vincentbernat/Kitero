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

@app.route("/api/1.0/current", methods=['GET'])
@jsonify
def current():
    """Return the current settings for the client."""
    client = flask.request.remote_addr
    return status(client)

@app.route("/api/1.0/interfaces", methods=['GET'])
@jsonify
def interfaces():
    """Return the list of available interfaces."""
    interfaces = RPCClient.call("interfaces")
    return interfaces

@app.route("/api/1.0/bind/<interface>/<qos>", methods=['GET', 'POST', 'PUT'])
@jsonify
def bind(interface, qos):
    """Allow to set the current interface for the client.

    :param interface: Output interface requested
    :param qos: QoS settings requested
    """
    client = flask.request.remote_addr
    RPCClient.call("bind_client", client, interface, qos)
    return status(client)

@app.route("/api/1.0/unbind", methods=['GET', 'POST', 'PUT'])
@jsonify
def unbind():
    """Unbind the client.
    """
    client = flask.request.remote_addr
    RPCClient.call("unbind_client", client)
    return status(client)
