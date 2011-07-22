import json
import socket
import threading
import SocketServer
import logging
logger = logging.getLogger("kitero.helper.rpc")
import traceback

def expose(fn):
    """Expose a function to be available as a RPC"""
    fn._kitero_rpc = True
    return fn

class RPCRequestHandler(SocketServer.StreamRequestHandler):
    """Handle one RPC connection.

    Should be subclassed to be useful. Only function exposed are
    exported as RPC. Nothing is done to help to resolve threading
    issues.
    """

    def process(self, data):
        """Process received data.

        :param data: received data in JSON format
        :type data: JSON string
        :return: answer
        :rtype: JSON string

        If there is an exception, the returned JSON string is::

            { status: -1,
              exception: {
                class: 'ValueError',
                message: 'Incorrect blah blah blah',
                traceback: 'Traceback (most recent call last)...'
              }
            }

        If there is no exception, the returned JSON string is::

            { status: 0, value: ...}
        """
        try:
            data = json.loads(data)
            if type(data) is not list:
                raise ValueError("Invalid RPC: not a list")
            if not len(data):
                raise ValueError("Invalid RPC: empty list")
            function = data[0]
            args = tuple(data[1:])
            # We need to find the function
            method = getattr(self, function)
            if not hasattr(method, "_kitero_rpc") or \
                    not method._kitero_rpc:
                raise ValueError("Method %r is not exported" % method)
            logger.debug("executing %s%s" % (method, args))
            result = method(*args)
            result = json.dumps({'status': 0,
                                 'value': result})
            return result
        except Exception as e:
            # We got an exception
            logger.exception("while executing %r, got exception" % data)
            return json.dumps({'status': -1,
                               'exception': {
                        'class': e.__class__.__name__,
                        'message': str(e),
                        'traceback': traceback.format_exc()
                        }})

    def handle(self):
        """Handle one connection.

        The protocol is pretty simple. We wait for a tuple whose first
        member is the name of the function to invoke and the remaining
        members are arguments. This tuple is provided as a JSON
        string. We execute the function with the given arguments if it
        is exposed and return the value as a JSON string.

        Moreover, the returned value is wrapped into a dictionary
        containing the key `status` (whose value is `0` if there were
        no exceptions and `-1` is an exception was raised), `value`
        (who contains the returned value) if there was no exception
        and `exception` which encodes the exception.
        """
        while True:
            data = self.rfile.readline()
            if not data:
                break
            result = self.process(data)
            self.wfile.write("%s\n" % result)

    @expose
    def ping(self):
        """Simple example of RPC function"""
        return None

class RPCServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):

    allow_reuse_address = True

    @classmethod
    def run(cls, host, port, handler=RPCRequestHandler):
        """Start a new server.

        :param host: IP to listen to
        :type host: string
        :param port: port to listen to
        :type port: integer
        :param handler: request handler
        :return: the server instance started
        """
        server = cls((host, port), handler)
        server._thread = threading.Thread(target=server.serve_forever)
        server._thread.setDaemon(True)
        server._thread.start()
        logger.info("RPC server for %r started on %s:%s" % (handler, host, port))
        return server

    def stop(self):
        """Stop the running server."""
        self.shutdown()
        self.wait()

    def wait(self, timeout=None):
        """Wait for server to finish.

        :return: is the server still alive?
        """
        self._thread.join(timeout)
        return self._thread.isAlive()
