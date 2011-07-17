import threading
import time
import socket
import json
import traceback
import logging
logger = logging.getLogger("kitero.web.rpc")

import kitero.config

class RPCException(Exception):
    def __init__(self, exception, message, traceback):
        self.exception = exception
        self.message = message
        self.traceback = traceback

    def __str__(self):
        return "RPC error: %s(%r)" % (self.exception,
                                      self.message)

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
    def call(cls, method, *args):
        """Request an attribute from remote service.

        :param method: method to invoke
        :type method: string
        :return: requested value
        """
        cls.connect()
        with cls.lock:
            data = [method,]
            data.extend(args)
            cls.write.write("%s\n" % json.dumps(data))
            answer = json.loads(cls.read.readline())
            if answer['status'] != 0:
                raise RPCException(answer['exception']['class'],
                                   answer['exception']['message'],
                                   answer['exception']['traceback'])
            return answer['value']

    @classmethod
    def clean(cls):
        """Try to cleanup.

        Only used for unittests.
        """
        try:
            if cls.client is not None:
                cls.read.close()
                cls.write.close()
                cls.client.close()
        except: # pragma: no cover
            pass

    @classmethod
    def connect(cls):
        """Connect to RPC client."""
        with cls.lock:
            i = 0
            client = None
            while client is None:
                try:
                    if cls.client is None:
                        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        client.connect((cls.config['listen'], cls.config['port']))
                        read, write = client.makefile('rb'), client.makefile('wb', 0)
                    else:
                        client, cls.client = cls.client, None
                        read, write = cls.read, cls.write
                    # Try to ping
                    write.write("%s\n" % json.dumps(("ping",)))
                    answer = json.loads(read.readline())
                except Exception as e: # Not the best, but we don't have better
                    i = i + 1
                    if i < 4:
                        client = None
                        time.sleep(0.1)
                        continue
                    logger.exception("unable to contact RPC server")
                    raise IOError(
                        "unable to contact RPC server (%s:%d)" % (cls.config['listen'],
                                                                  cls.config['port']))
            cls.client = client
            cls.read, cls.write = read, write
