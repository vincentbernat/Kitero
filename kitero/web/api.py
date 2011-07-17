import flask

from kitero.web import app
from kitero.web.decorators import jsonify
from kitero.web.rpc import RPCClient

@app.route("/api/1.0/current", methods=['GET'])
@jsonify
def current():
    """Return the current settings for the client."""
    client = flask.request.remote_addr
    current = RPCClient.call("client", client)
    if current is None: # Not bound
        return { 'ip': client }
    return {
        'ip': client,
        'interface': current[0],
        'qos': current[1]
        }

@app.route("/api/1.0/interface", methods=['GET'])
@jsonify
def get_interfaces():
    """Return the list of available interfaces."""
    interfaces = RPCClient.call("interfaces")
    return interfaces

@app.route("/api/1.0/interface/<interface>/<qos>", methods=['GET', 'POST', 'PUT'])
@jsonify
def set_interface(interface, qos):
    """Allow to set the current interface for the client.

    :param interface: Output interface requested
    :param qos: QoS settings requested
    """
    client = flask.request.remote_addr
    RPCClient.call("bind_client", client, interface, qos)
    return "Client bound to interface %s, QoS %s" % (interface, qos)
