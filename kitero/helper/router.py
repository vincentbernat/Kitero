from netaddr import IPAddress

import logging
logger = logging.getLogger("kitero.helper.router")

class Router(object):
    """A router manages interfaces, QoS settings and clients.

    A router can be created by providing a set of interfaces (each
    interface contains a list of available QoS settings).

    Once created, it is not possible to add interfaces to a router.

    The router can be pickled. It can be observed too. The observer
    should be pickable too.
    """

    @classmethod
    def load(cls, yaml):
        """Load router configuration from a YAML representation.

        :param yaml: dictionary representing the router
        :type yaml: dictionary
        :returns: a fresh new :class:`Router` instance
        """
        if "clients" not in yaml:
            raise ValueError("'clients' key is missing")
        available_qos = {}
        for q in yaml.get('qos', {}):
            settings = yaml['qos'][q].copy()
            del settings['description']
            del settings['name']
            available_qos[q] = QoS(yaml['qos'][q]['name'],
                                   yaml['qos'][q]['description'],
                                   settings)
        interfaces = {}
        for i in yaml.get('interfaces', {}):
            q = {}
            for qos in yaml['interfaces'][i].get('qos', {}):
                if qos not in available_qos:
                    raise KeyError("no %r QoS available" % qos)
                q[qos] = available_qos[qos]
            interfaces[i]=Interface(yaml['interfaces'][i]['name'],
                                    yaml['interfaces'][i]['description'],
                                    q)
        return cls(yaml["clients"], interfaces)

    def __init__(self, incoming, interfaces={}):
        """Create a new router.

        The new router will manage a set of clients connected to
        interface `incoming` and a set of outgoing interfaces.

        :param incoming: name of the interface where clients are connected
        :type incoming: string
        :param interfaces: dictionary of interfaces (keyed by interface name)
        :type interfaces: dictionary of :class:`Interface`
        """
        self._incoming = incoming
        self._interfaces = interfaces
        self._clients = {}
        self._observers = []
        # Check that we don't have conflicting interfaces
        if incoming in interfaces:
            raise ValueError("Duplicate interfaces are not allowed")

    def register(self, observer):
        """Register a new observer.
        
        The observer will be notified of bind and unbind events. It
        needs to implement one method `notify`. This method will get
        the action as a string (`bind` or `unbind`), the source (this
        router) and some additional parameters that should be
        retrieved as keyword arguments.

        .. class:: Observer
           .. method:: notify(event : string, source, **kwargs)

        There is no way to unregister an observer. An observer should
        be pickable.

        :param observer: observer object to be notified
        """
        self._observers.append(observer)

    def notify(self, event, **kwargs):
        """Notify all observers.

        :param event: event to be notified about
        :type event: string
        """
        for obs in self._observers:
            obs.notify(event, self, **kwargs)

    @property
    def incoming(self):
        """Name of the interface where clients are connected"""
        return self._incoming
    @property
    def clients(self):
        """Clients managed by this router as a dictionary.

        Each client is associated with a tuple of interface and
        connection.
        """
        return self._clients.copy()
    @property
    def interfaces(self):
        """Outgoing interfaces managed by this router as a dictionary"""
        return self._interfaces.copy()

    def __eq__(self, other):
        if not isinstance(other, Router):
            return False
        return self.incoming == other.incoming and \
            self.interfaces == other.interfaces
    def __ne__(self, other):
        return not(self == other)
    def __repr__(self):
        return '<Router(incoming=%r): %d clients, %d interfaces>' % (self.incoming,
                                                                     len(self.clients),
                                                                     len(self.interfaces))

    def bind(self, client, interface, qos):
        """Bind a client to an interface and QoS settings.

        :param client: IP address of client
        :type client: string
        :param interface: interface to use for binding
        :type interface: string
        :param qos: QoS settings to use
        :type qos: string
        """
        client = str(IPAddress(client))
        if client in self._clients:
            raise ValueError("Client %r is already bound" % client)
        # Search the interface
        for q in self.interfaces[interface].qos:
            if q == qos:
                logger.info("bind %r to %r" % (client, (interface, q)))
                self._clients[client] = (interface, q)
                self.notify("bind", client=client, interface=interface, qos=q)
                return
        raise KeyError("No %r for %r" % (qos, interface))

    def unbind(self, client):
        """Unbind a client from the router.

        :param client: IP address of client
        :type client: string
        """
        if client not in self._clients:
            return              # Already done
        logger.info("unbind %r from %r" % (client, self))
        self.notify("unbind", client=client)
        del self._clients[client]

    def __getstate__(self):
        """When pickling, we only need interfaces, clients and incoming interface"""
        return { "interfaces": self._interfaces,
                 "incoming": self._incoming,
                 "clients": self._clients,
                 "observers": self._observers }
    def __setstate__(self, state):
        """Unpickle and rebind clients"""
        self._interfaces = state["interfaces"]
        self._incoming = state["incoming"]
        self._observers = state["observers"]
        self._clients = {}
        # Rebind clients
        for client in state["clients"]:
            i, q = state["clients"][client]
            self.bind(client, i, q)

class Interface(object):
    """An interface represents an outgoing interface with its QoS settings.

    Once created, an interface is a read-only object. It is not
    possible to append a new QoS settings.
    """

    def __init__(self, name, description, qos={}):
        """Create a new interface.

        :param name: name of the outgoing interface
        :type name: string
        :param description: description
        :type description: string
        :param qos: QoS settings associated
        :type qos: dictionary of :class:`QoS`
        """
        self._name = name
        self._description = description
        self._qos = qos

    @property
    def name(self):
        return self._name
    @property
    def description(self):
        return self._description
    @property
    def qos(self):
        return self._qos.copy()

    def __eq__(self, other):
        if not isinstance(other, Interface):
            return False
        return self.name == other.name and \
            self.description == other.description and \
            self.qos == other.qos
    def __ne__(self, other):
        return not(self == other)
    def __repr__(self):
        return '<Interface(%r): %s>' % (self.name, self.description)

class QoS(object):
    """QoS settings

    Once created, this object is a read-only.
    """

    def __init__(self, name, description, settings={}):
        """Create a new QoS settings.

        A setting is represented as a dictionary.

        :param name: name of the QoS settings
        :type name: string
        :param description: description
        :type description: string
        :param settings: QoS settings
        :type settings: dictionary of strings
        """
        self._name = name
        self._description = description
        self._settings = settings

    @property
    def name(self):
        return self._name
    @property
    def description(self):
        return self._description
    @property
    def settings(self):
        return self._settings.copy()

    def __eq__(self, other):
        if not isinstance(other, QoS):
            return False
        return self.name == other.name and \
            self.description == other.description and \
            self.settings == other.settings
    def __ne__(self, other):
        return not(self == other)
    def __repr__(self):
        return '<QoS(%r): %s>' % (self.name, self.description)
