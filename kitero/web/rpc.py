import rpyc
import threading
import cherrypy
import time
import socket

import kitero.config

class RPCClient(object):
    """Singleton object for communication with the helper.

    This object should not be instantiated. The methods should be used
    only inside a request: the application configuration is grabbed
    from the request.
    """
    client = None               # No connection made yet
    lock = threading.Lock()
    config = kitero.config.merge()['helper']

    @classmethod
    def get(cls, attr):
        """Request an attribute from remote service.

        :param attr: attribute to be requested
        :type attr: string
        :return: requested attribute
        """
        cls.connect()
        with cls.lock:
            attr = getattr(cls.client.root, attr)
            return attr

    @classmethod
    def connect(cls):
        """Connect to RPC client."""
        with cls.lock:
            i = 0
            client = None
            while client is None:
                try:
                    if cls.client is None:
                        client = rpyc.connect(cls.config['listen'], cls.config['port'])
                    else:
                        client, cls.client = cls.client, None
                    client.ping()
                except (EOFError, socket.error):
                    i = i + 1
                    if i < 4:
                        client = None
                        time.sleep(0.1)
                        continue
                    raise IOError("unable to contact RPC server (%s:%d)" % (cls.config['listen'],
                                                                            cls.config['port']))
            cls.client = client
