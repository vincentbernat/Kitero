import cherrypy
import uuid
import logging
logger = logging.getLogger("kitero.web.api")

from kitero.web.rpc import RPCClient

ID = 100

def wrap_status(fn):
    """Wrap exception into a dictionary for nice JSON formatting."""
    def wrapped(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            return { 'status': 0,
                     'value': result }
        except cherrypy.HTTPError as e:
            cherrypy.serving.response.status = e.status
            return { 'status': e.code,
                     'message': str(e) }
        except cherrypy.HTTPRedirect:
            raise
        except Exception as e:
            global ID
            ID = ID + 1
            logger.warning("%d: %s(%r)" % (ID, e.__class__.__name__, e))
            cherrypy.serving.response.status = "500 Internal Error"
            return { 'status': 500,
                     'message':
                         "An internal error occurred and has been logged with ID %d." % ID}
    return wrapped
    

class Api10(object):
    """Access to Kitero REST API 1.0.

     * `/current` will return the current settings for the client
     * `/interface` will return a dictionary of available interfaces
       with their QoS settings
    """

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @wrap_status
    def current(self):
        """Return the current settings for the client."""
        client = cherrypy.request.remote.ip
        current = RPCClient.call("client", client)
        if current is None: # Not bound
            return { 'ip': client }
        return {
            'ip': client,
            'interface': current[0],
            'qos': current[1]
            }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @wrap_status
    def interface(self, interface=None, qos=None):
        """Return the list of available interfaces.

        If `interface` and `qos` are provided, bind the client.
        """
        if interface is None and qos is None:
            interfaces = RPCClient.call("interfaces")
            return interfaces
        if cherrypy.request.method != "POST":
            raise cherrypy.HTTPError(405, "modifications should be done with POST")
        if interface is not None and qos is not None:
            client = cherrypy.request.remote.ip
            RPCClient.call("bind_client", client, interface, qos)
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
