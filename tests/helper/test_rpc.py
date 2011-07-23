try:
    import unittest2 as unittest
except ImportError: # pragma: no cover
    import unittest

import socket
import json
import time

from kitero.helper.rpc import RPCRequestHandler, RPCServer, expose

class DummyRPCHandler(RPCRequestHandler):
    def not_exposed(self): # pragma: no cover
        return "Hello"

    @expose
    def without_args(self):
        return "Hi!"

    @expose
    def with_arguments(self, arg1, arg2):
        return ["Hello", arg1, "and", arg2]

    @expose
    def with_complex_result(self):
        return { "s1": {
                "s2": "Hello",
                "s3": "Hi\n\nBye",
                "s4": {
                    "s5": "Nothing",
                    "s6": [784, "Hop"]
                    },
                "Bli": "Blo"
                }}

    @expose
    def with_exception(self):
        raise RuntimeError("Sorry...")

class TestRPCServer(unittest.TestCase):
    def setUp(self):
        self.server = RPCServer.run('127.0.0.1', 18861, DummyRPCHandler)

    def test_basic_tests(self):
        """Run simple basic tests"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 18861))
        read, write = sock.makefile('rb'), sock.makefile('wb', 0)
        # Ping
        write.write("%s\n" % json.dumps(("ping",)))
        answer = json.loads(read.readline())
        self.assertEqual(answer, {u"status": 0, u"value": None})
        # Simple function
        write.write("%s\n" % json.dumps(("without_args",)))
        answer = json.loads(read.readline())
        self.assertEqual(answer, {u"status": 0, u"value": u"Hi!"})
        # With arguments
        write.write("%s\n" % json.dumps(("with_arguments", 45, u"hello")))
        answer = json.loads(read.readline())
        self.assertEqual(answer, {u"status": 0, u"value": [u"Hello", 45, u"and", u"hello"]})
        # With complex result
        write.write("%s\n" % json.dumps(("with_complex_result",)))
        answer = json.loads(read.readline())
        self.assertEqual(answer, {u"status": 0, u"value": { u"s1": {
                u"s2": u"Hello",
                u"s3": u"Hi\n\nBye",
                u"s4": {
                    u"s5": u"Nothing",
                    u"s6": [784, u"Hop"]
                    },
                u"Bli": u"Blo"
                }}})
        # With exception
        write.write("%s\n" % json.dumps(("with_exception",)))
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], -1)
        self.assertEqual(answer["exception"]["class"], u"RuntimeError")
        self.assertEqual(answer["exception"]["message"], u"Sorry...")
        self.assertEqual(answer["exception"]["traceback"].split("\n")[0],
                         u"Traceback (most recent call last):")
        sock.close()

    def test_invalid_tests(self):
        """Run some errors"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 18861))
        read, write = sock.makefile('rb'), sock.makefile('wb', 0)
        # Not exposed
        write.write("%s\n" % json.dumps(("not_exposed",)))
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], -1)
        self.assertEqual(answer["exception"]["class"], u"ValueError")
        # Does not exist
        write.write("%s\n" % json.dumps(("not_exist",)))
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], -1)
        self.assertEqual(answer["exception"]["class"], u"AttributeError")
        # No JSON
        write.write("8787gfgfgf\n")
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], -1)
        self.assertEqual(answer["exception"]["class"], u"ValueError")
        # Empty call
        write.write("%s\n" % json.dumps(()))
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], -1)
        self.assertEqual(answer["exception"]["class"], u"ValueError")
        # Too many args
        write.write("%s\n" % json.dumps(("ping",454)))
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], -1)
        self.assertEqual(answer["exception"]["class"], u"TypeError")
        # Not a valid RPC call
        write.write("%s\n" % json.dumps({"call": "ping"}))
        answer = json.loads(read.readline())
        self.assertEqual(answer["status"], -1)
        self.assertEqual(answer["exception"]["class"], u"ValueError")
        sock.close()

    def tearDown(self):
        self.server.stop()
        del self.server

