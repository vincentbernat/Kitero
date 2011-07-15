import sys
import os.path
import cherrypy
import logging

import kitero.config
from kitero.web.api import Api
from kitero.web.rpc import RPCClient

class KiteroWebService(object):
    """Root object for Kitero web service.

    The root object will return a static HTML file containing the
    application. It will also make available `/api` and `/static`
    resources.
    """

    api = Api()

    @cherrypy.expose
    def index(self):
        return "Hello world. Available soon.\n"

    @classmethod
    def run(cls, config={}):
        """Start Kitero web service.

        A YAML configuration file can be provided as first argument.
        """
        config = kitero.config.merge(config)
        RPCClient.config = config['helper']
        default_config = {
            'kitero': config,
            'global': {
                'server.socket_host': '127.0.0.1',
                'server.socket_port': 8187
                },
            # Static files
            '/static':  {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                    'static'),
                }
            }

        # Merge configuration file
        config = config['web']
        default_config['global']['server.socket_port'] = config['port']
        default_config['global']['server.socket_host'] = config['listen']
        cherrypy._cpconfig.merge(default_config, config['advanced'])

        # Start server
        cherrypy.quickstart(cls(), config=default_config)

if __name__ == "__main__": # pragma: no cover
    import yaml
    if len(sys.argv[1:]):
        KiteroWebService.run(yaml.safe_load(file(sys.argv[1])))
    else:
        KiteroWebService.run()
