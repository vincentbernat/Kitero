import sys
import yaml
import threading

import logging
import logging.handlers
logger = logging.getLogger("kitero.helper.service")

from kitero.helper.router import Router
from kitero.helper.rpc import RPCServer, RPCRequestHandler, expose
from kitero.helper.binder import PersistentBinder
import kitero.config

class RouterRPCService(RPCRequestHandler):
    """Helper service as an RPC service.

    This is the actual class that will be instantiated for each
    connection and serve RPC queries.
    """

    router_lock = threading.Lock() # Lock to access the router
    router = None

    @expose
    def interfaces(self):
        """Return the dictionary of known interfaces.

        :return: dictionary of interfaces
        """
        interfaces = {}
        for i, interface in self.router.interfaces.items():
            interfaces[i] = {
                'name': interface.name,
                'description': interface.description,
                }
            qos = {}
            for q, qq in interface.qos.items():
                qos[q] = {
                    'name': qq.name,
                    'description': qq.description,
                    }
                qos[q].update(qq.settings)
            interfaces[i]['qos'] = qos
        return interfaces

    @expose
    def stats(self):
        """Return the stats for each interface.

        :return: dictionary of stats
        """
        with self.router_lock:
            return self.router.stats

    @expose
    def client(self, client):
        """Return client current binding.

        :param client: IP address of the client
        :type client: string
        :return: a tuple (interface, qos) if the client is bound. `None` otherwise.
        :rtype: a tuple of strings
        """
        with self.router_lock:
            if client not in self.router.clients:
                return None
            interface, qos = self.router.clients[client]
            return (interface, qos)

    @expose
    def bind_client(self, client, interface, qos, password=None):
        """Bind a client to an interface and QoS settings.

        :param client: IP address of the client
        :type client: string
        :param interface: Interface the client should be bound
        :type interface: string
        :param qos: QoS settings to be applied
        :type qos: string
        :param password: supplied password
        :type password: string, int or `None`
        """
        with self.router_lock:
            if client in self.router.clients:
                self.router.unbind(client)
            self.router.bind(client, interface, qos, password)

    @expose
    def unbind_client(self, client):
        """Unbind a client.

        :param client: IP address of the client
        :type client: string
        """
        with self.router_lock:
            if client in self.router.clients:
                self.router.unbind(client)

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
        # Create RPC service
        config = kitero.config.merge(config)
        config = config['helper']
        # Bind persistency module
        save = config.get("save", None)
        if save is not None:
            save = PersistentBinder(save)
            try:
                save.restore(router)
            except IOError as e:
                logger.warning("unable to restore previous configuration: %s", e)
            router.register(save)
        RouterRPCService.router = router
        self.server = RPCServer.run(config['listen'],
                                    config['port'],
                                    handler=RouterRPCService)
        logger.info('create RPC server on %s:%d',
                    config['listen'], config['port'])

    def stop(self):
        """Stop the helper service."""
        self.server.stop()
        self.server = None

    def wait(self):
        """Wait for the service to stop."""
        while self.server is not None and self.server.wait(1): # pragma: no cover
            pass

    @classmethod
    def run(cls, args=sys.argv[1:], binder=None):
        """Start the helper service.

        This method should be used to instantiate
        :class:`Service`. The configuration file must be provided as
        an argument.

        :param args: list of command line arguments
        :type args: list of strings
        :param binder: binder to register to the router
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
            config = kitero.config.merge(config)
            # Create the router
            router = Router.load(config['router'])
            # Add the regular binder to it
            if binder is not None:
                router.register(binder)
            # Start service
            s = cls(config, router)
            s.wait()
        except Exception as e:
            logger.exception("unhandled error received")
            sys.exit(1)
        sys.exit(0)

def _run(): # pragma: no cover
    from kitero.helper.binder import LinuxBinder
    Service.run(binder=LinuxBinder())

if __name__ == "__main__": # pragma: no cover
    _run()
