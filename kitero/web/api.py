import cherrypy

from kitero.web.rpc import RPCClient

class Api10(object):
    """Access to Kitero REST API 1.0.

     * `/current` will return the current settings for the client
     * `/interface` will return a dictionary of available interfaces
       with their QoS settings
    """

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def current(self):
        """Return the current settings for the client."""
        client = cherrypy.request.remote.ip
        current = RPCClient.get("get_client")(client)
        if current is None:
            return { 'ip': client }
        return {
            'ip': client,
            'interface': current[0],
            'qos': current[1]
            }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def interface(self, interface=None, qos=None):
        """Return the list of available interfaces.

        If `interface` and `qos` are provided, bind the client.
        """
        if interface is None and qos is None:
            interfaces = RPCClient.get("get_interfaces")()
            return interfaces
        if cherrypy.request.method != "POST":
            raise cherrypy.HTTPError(405, "modifications should be done with POST")
        if interface is not None and qos is not None:
            client = cherrypy.request.remote.ip
            RPCClient.get("bind_client")(client, interface, qos)
            print cherrypy.request.path_info, cherrypy.request.script_name
            raise cherrypy.HTTPRedirect("../../current")
        raise cherrypy.HTTPError(404, "need both interface and QoS")

class Api(object):
    """Select the appropriate API object for the given version.

    For each supported version, expose the appropriate version number.
    """

    supported = [ "1.0" ]       # Supported versions

    def __init__(self):
        for s in self.supported:
            api = Api10()
            api.exposed = True
            setattr(self, s.replace(".", "_"), api)
