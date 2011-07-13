import sys
import yaml
import rpyc
import threading

import logging
import logging.handlers
logger = logging.getLogger("kitero.helper.service")

from kitero.helper.router import Router

class RPCService(rpyc.Service):
    """Helper service as an RPC service.

    This is the actual class that will be instantiated for each
    connection and serve RPC queries.
    """

    # Class variables
    router_lock = threading.Lock() # Lock to access the router
    router = None                  # Reference to the router

    def exposed_get_interfaces(self):
        """Return the dictionary of known interfaces.

        :return: dictionary of interfaces
        """
        interfaces = {}
        for i, interface in self.router.interfaces.items():
            interfaces[i] = {
                'description': interface.description,
                }
            qos = {}
            for q in interface.qos:
                qos[q.name] = {
                    'description': q.description,
                    }
                qos[q.name].update(q.settings)
            interfaces[i]['qos'] = qos
        return interfaces

    def exposed_get_client(self, client):
        """Return client current binding.

        :param client: IP address of the client
        :type client: string
        :return: a tuple (interface, qos) if the client is bound.
           `None` otherwise.
        :rtype:" a tuple of strings
        """
        with self.router_lock:
            if client not in self.router.clients:
                return None
            interface, qos = self.router.clients[client]
            return (interface.name, qos.name)

    def exposed_bind_client(self, client, interface, qos):
        """Bind a client to an interface and QoS settings.

        :param client: IP address of the client
        :type client: string
        :param interface: Interface the client should be bound
        :type interface: string
        :param qos: QoS settings to be applied
        :type qos: string
        """
        with self.router_lock:
            if client in self.router.clients:
                self.router.unbind(client)
            self.router.bind(client, interface, qos)

class Service(object):
    """Helper service.

    This RPC service allows an external program to interact with the
    helper functions to grab interface and QoS information and to bind
    clients to the router. It is expected that this service is run as
    root.

    An instance of this service can be summoned with the
    :classmethod:`run` class method.
    """

    def __init__(self, config, router):
        """Create helper service.

        :param config: configuration of the application
        :param router: router that should be serviced
        """
        # Let RPCService knows the managed router
        # TODO: This should be done through a factory but
        # TODO: RPyC introspects the class and is not happy.
        RPCService.router = router

        # Create RPyC service
        from rpyc.utils.server import ThreadedServer
        config = config.get('helper', {})
        port = config.get('port', 18861)
        listen = config.get('listen', '127.0.0.1')
        self.server = ThreadedServer(RPCService,
                           port = port, hostname = listen,
                           auto_register = False)
        logger.info('create RPyC server on %s:%d', listen, port)

    def start(self):
        """Run the helper"""
        if self.server is not None:
            self.server.start()

    @classmethod
    def run(cls, args=sys.argv[1:], binder=None):
        """Start the helper service.

        This method should be used to instantiate
        :class:`Service`. The configuration file must be provided as
        an argument.

        :param args: list of command line arguments
        :type args: list of strings
        """
        from optparse import OptionParser
        usage = "usage: %prog [options] config.yaml"
        parser = OptionParser(usage=usage)
        parser.add_option("-l", "--log",
                          type="string", dest="log",
                          help="log to file",
                          metavar="FILE")
        parser.add_option("-s", "--syslog",
                          action="store_true", dest="syslog",
                          help="log to syslog")
        parser.add_option("-d", "--debug",
                          action="count", dest="debug",
                          help="enable debugging")
        (options, args) = parser.parse_args(args)
        if len(args) != 1:
            parser.error("incorrect number of arguments")

        # Logger configuration
        l = logging.root
        if options.debug == 1:
            l.setLevel(logging.INFO)
        if options.debug > 1:
            l.setLevel(logging.DEBUG)
        if options.log:
            fh = logging.FileHandler(options.log)
            fh.setFormatter(
                logging.Formatter('%(asctime)s %(name)s[%(process)d] '
                                  '%(levelname)s: %(message)s'))
            l.addHandler(fh)
        if options.syslog:
            sh = logging.handlers.SysLogHandler(address='/dev/log',
                                                facility="daemon")
            sh.setFormatter(
                logging.Formatter('kitero[%(process)d]: '
                                  '%(levelname)s %(message)s'))
            l.addHandler(sh)
        if not options.syslog and not options.log:
            # Log to stderr
            eh = logging.StreamHandler()
            eh.setFormatter(
                logging.Formatter('%(asctime)s %(name)s[%(process)d] '
                                  '%(levelname)s: %(message)s'))
            l.addHandler(eh)

        # Reading configuration file
        logger.info("read configuration file %r" % args[0])
        try:
            config = yaml.safe_load(file(args[0]))
            # Create the router
            router = Router.load(config['router'])
            if binder is not None:
                router.notify(binder)
            # Start service
            s = cls(config, router)
            s.start()
        except Exception as e:
            logger.exception("unhandled error received")
            sys.exit(1)
        sys.exit(0)

if __name__ == "__main__": # pragma: no cover
    # TODO: Should be run with a sensible binder.
    Service.run()
