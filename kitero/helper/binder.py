import re
import zope.interface
import logging
logger = logging.getLogger("kitero.helper.binder")
import cPickle as pickle

from kitero.helper.router import Router
from kitero.helper.commands import Commands
from kitero.helper.interface import IBinder, IStatsProvider

class Mark(object):
    """Class to provides Netfilter marks for each interface/slot."""

    def __init__(self, interfaces, slots):
        """Create an instance able to provide marks.

        :param interfaces: number of interfaces that we should address
        :type interfaces: integer
        :param slots: number of slots per interface we should address
        :type slots: integer
        """

        # Compute necessary bits for the interfaces and slots
        def bits(m):
            b = 0
            m = m - 1
            while m > 0:
                b = b + 1
                m = m >> 1
            return b
        self.bits = dict(slots=bits(slots),
                         interfaces=bits(interfaces + 1))

        if sum(self.bits.values()) > 32:
            raise ValueError("to many interfaces or slots per interface (%s)" % self.bits.values())
        logger.info("use firewall mark mask %s" % self(0,0)[1])

    def __call__(self, interface=None, slot=None):
        """Return the (mark, mask) to use to match the given interface/slot.

        If `slot` or `interface` is `None`, the mask is adapted. A
        slot is a user bound to an interface (a low index for the user
        in the context of the interface).

        :param interface: interface name
        :param slot: slot number for the user (relative to the interface)
        :return: a tuple (mark, mask) (like `('0x1400', '0xff00')`)
        :rtype: a tuple of strings
        """
        # To avoid any conflict, we use high order bits first.
        mark = 0
        mask = 0
        if interface is not None:
            interface = interface + 1
            mask = mask + (((1<<self.bits['interfaces']) - 1) <<
                           (32 - self.bits['interfaces']))
            mark = mark + (interface << (32 - self.bits['interfaces']))
        if slot is not None:
            mask = mask + (((1<<self.bits['slots']) - 1) <<
                           (32 - self.bits['interfaces'] - self.bits['slots']))
            mark = mark + (slot << (32 - self.bits['interfaces'] - self.bits['slots']))
        return ("0x%08x" % mark, "0x%08x" % mask)

class SlotsProvider(object):
    """Class to provide slot number associated to interfaces for clients"""

    def __init__(self, max_slots):
        self.interfaces = {}
        self.max_slots = max_slots

    def request(self, interface, client):
        """Request a new slot for a given client on the given interface.

        :param interface: interface the client will be bound too
        :type interface: string
        :param client: client IP requesting a slot for the interface
        :type client: string
        :return: minimal slot number
        :rtype: integer
        """
        if interface not in self.interfaces:
            self.interfaces[interface] = {}
        if client in self.interfaces[interface]:
            raise ValueError("client %r has already a slot for %r" % (client, interface))
        slots = self.interfaces[interface].values()
        slots.sort()
        i = 0
        while i < len(slots):
            if slots[i] != i:
                break
            i = i + 1
        slot = i
        if slot >= self.max_slots:
            raise RuntimeError("no free slot for interface %r (max: %d)" % (interface,
                                                                            self.max_slots))
        self.interfaces[interface][client] = slot
        return slot

    def get(self, client):
        """Get the slot number allocated for a client."""
        for interface in self.interfaces:
            if client in self.interfaces[interface]:
                slot = self.interfaces[interface][client]
                return slot
        raise ValueError("the client %r was not found" % client)

    def release(self, client):
        """Release the slot number allocated for client.

        :param client: IP address of the client that should be released
        :type client: string
        :return: the slot that was allocated
        :rtype: integer
        """
        for interface in self.interfaces:
            if client in self.interfaces[interface]:
                slot = self.interfaces[interface][client]
                del self.interfaces[interface][client]
                return slot
        raise ValueError("the client %r was not found" % client)

class TicketsProvider(object):
    """Class to provide a ticket for each user.

    A ticket is an unique number which is not assigned to another user
    """

    def __init__(self):
        self.clients = {}

    def request(self, client):
        """Request a new ticket for the client.

        :param client: IP address of the client
        :type client: string
        :return: ticket
        :rtype: integer
        """
        if client in self.clients:
            raise ValueError("client %r has already a ticket" % client)
        values = self.clients.values()
        values.sort()
        i = 0
        while i < len(values):
            if values[i] != i + 1:
                break
            i = i + 1
        i = i + 1
        self.clients[client] = i
        return i

    def get(self, client):
        """Get the ticket associated to a client"""
        return self.clients[client]

    def release(self, client):
        """Release the ticket associated to a client.

        :param client: IP address of the client
        :type client: string
        :return: ticket that was associated
        :rtype: integer
        """
        ticket = self.clients.get(client, None)
        if ticket is None:
            raise ValueError("client %r does not have a ticket" % client)
        del self.clients[client]
        return ticket

class LinuxBinder(object):
    """Handle client binding on a Linux hosts.

    This uses `ip`, `tc` and `iptables` to do the binding. Routing
    tables should already exists. One routing table per outgoing
    interface. The routing table should be named after the name of the
    interface and contains appropriate routes to let the traffic flow
    from the user to the interface. This binder will setup rules to
    use those tables. Those rules will rely on firewall marks that
    will be setup with iptables.

    It is important to note that even if a user request the same
    interface and QoS that another user, it will get a distinct
    firewall mark (and a distinct QoS). Two users asking for a 5MB
    bandwidth should not share this bandwidth.

    We need to encode interfaces and QoS in firewall marks. A mark is
    a 32-bit int. The number of bits for the QoS is configurable
    (`max_users`). The number of bits for the interfaces is computed
    from the number of interfaces. Each time a new user is bound to an
    interface, we affect her a slot which is an integer that is only
    affected to her in the context of the interface. The firewall mark
    is built by combining the interface index with the slot number.

    Classification ID are built using tickets which are just
    integers associated to only one client. This ticket is multiplied
    by 10 and we add 0, 1 or 2 to build the class of each QoS.

    Keep in mind that the binder should work even in case of SNAT on
    output interfaces. This makes things a bit difficult and explain
    why we rely heavily on marks: in ``POSTROUTING``, the source
    address is not present anymore in the ``mangle`` table while in
    the other direction, ``PREROUTING``, it is not present yet. We
    assume that there is no NAT on the interface where clients are
    connected.

    This binder handles IPv6.
    """

    zope.interface.implements(IBinder, IStatsProvider)

    iptables = [ "iptables", "ip6tables" ]
    ipcmd = [ "ip", "ip -6" ]

    def __init__(self, max_users=256):
        """Not really the constructor of the class.

        The :method:`setup` is the real constructor but needs to be
        called with a router.
        """
        self.router = None      # Router handled
        self.config = {
            "prerouting": "kitero-PREROUTING",   # prerouting chain name
            "postrouting": "kitero-POSTROUTING", # postrouting chain name
            "accounting": "kitero-ACCOUNTING",   # accounting chain name
            "max_users": max_users,              # maximum number of users **per interface**
            }

    def isipv6(self, client):
        """Is the client an IPv6 address?"""
        return ":" in client

    def setup(self):
        """Setup the binder for the first time.

        Cleaning is also handled here since the binder has no way to
        clean on exit.
        """
        self.interfaces = self.router.interfaces.keys() # Ordered interface list
        self.interfaces.sort()
        self.mark = Mark(len(self.interfaces),                # Netfilter mark producer
                         self.config['max_users'])
        self.slots = SlotsProvider(self.config['max_users'])  # Slot producer
        self.tickets = TicketsProvider()                      # Ticket producer

        # Netfilter
        for chain in [ "prerouting", "accounting", "postrouting" ]:
            subs = dict(chain = self.config[chain],
                        chain_upper = chain.upper())
            if chain == "accounting":
                subs['chain_upper'] = "POSTROUTING"
            logger.info("setup %(chain)s chain" % subs)
            # Cleanup old iptables rules
            for iptables in self.iptables:
                Commands.run_noerr("%(iptables)s -t mangle -D %(chain_upper)s -j  %(chain)s",
                                   "%(iptables)s -t mangle -F %(chain)s",
                                   "%(iptables)s -t mangle -X %(chain)s",
                                   iptables=iptables,
                                   **subs)
                # Setup the new chains
                Commands.run("%(iptables)s -t mangle -N %(chain)s",
                             "%(iptables)s -t mangle -I %(chain_upper)s -j  %(chain)s",
                             iptables=iptables,
                             **subs)

        # Setup QoS
        for interface in self.interfaces + self.router.incoming:
            logger.info("setup QoS for interface %s" % interface)
            Commands.run_noerr("tc qdisc del dev %(interface)s root", interface=interface)
            Commands.run(
                # Flush QoS
                "tc qdisc add dev %(interface)s root handle 1: drr",
                # Default class
                "tc class add dev %(interface)s parent 1: classid 1:2 drr",
                "tc qdisc add dev %(interface)s parent 1:2 handle 12: sfq",
                # Use default class for unmatched traffic
                "tc filter add dev %(interface)s protocol arp parent 1:0"
                "  prio 1 u32 match u32 0 0 flowid 1:2", # ARP
                interface=interface, **self.config)
            for iptables in self.iptables:
                Commands.run(
                    "%(iptables)s -t mangle -A %(postrouting)s"
                    "  -o %(interface)s -j CLASSIFY --set-class 1:2", # IP
                    iptables=iptables,
                    interface=interface, **self.config)

        # Setup routing rules
        for interface in self.interfaces:
            logger.info("setup ip rules for interface %s" % interface)
            for ip in self.ipcmd:
                Commands.run_noerr("%(ip)s rule del fwmark %(mark)s table %(interface)s",
                                   mark="%s/%s" % self.mark(self.interfaces.index(interface)),
                                   ip = ip,
                                   interface=interface)
                Commands.run("%(ip)s rule add fwmark %(mark)s table %(interface)s",
                             ip = ip,
                             mark="%s/%s" % self.mark(self.interfaces.index(interface)),
                             interface=interface)

    def bind(self, client, interface, qos, bind=True):
        """Bind or unbind a user.

        This is the method that will issue all `tc` and `iptables`
        commands to ensure the binding of the user to the chosen
        interface and QoS.

        :param client: IP of the user
        :type client: string
        :param interface: name of the outgoing interface
        :type interface: string
        :param qos: QoS name
        :type qos: string
        :param slot: QoS slot
        :type slot: integer
        :param bind: bind or unbind?
        :type bind: boolean
        """
        ticket = self.tickets.get(client)
        slot = self.slots.get(client)
        mark = self.mark(self.interfaces.index(interface), slot)
        # tc qdisc and classes for the user
        def build(interface, qos, what):
            r = self.router.interfaces[interface].qos[qos].settings.get(what, None)
            result = { 'up': r, 'down': r }
            if type(r) is dict:
                result['up'] = r.get('up', None)
                result['down'] = r.get('down', None)
            return result
        bw = build(interface, qos, "bandwidth")
        netem = build(interface, qos, "netem")
        for iface in [interface,] + self.router.incoming:
            direction = (iface in self.router.incoming) and 'down' or 'up'
            opts=dict(iface=iface,
                      mark=mark[0],
                      ticket=ticket,
                      bw=bw[direction],
                      netem=netem[direction],
                      add=(bind and "add" or "del"))
            # Create a deficit round robin scheduler
            Commands.run("tc class %(add)s dev %(iface)s parent 1: classid 1:%(ticket)s0 drr",
                         **opts)
            if bw[direction] is not None and bind:
                # TBF for bandwidth limit...
                Commands.run(
                    "tc qdisc %(add)s dev %(iface)s parent 1:%(ticket)s0 handle %(ticket)s0:"
                    "  tbf rate %(bw)s", **opts)
                if netem[direction] is not None and bind:
                    # ...and netem
                    Commands.run(
                        "tc qdisc %(add)s dev %(iface)s parent %(ticket)s0:1 "
                        "  handle %(ticket)s1:"
                        "  netem %(netem)s", **opts)
            elif netem[direction] is not None and bind:
                # Just netem
                Commands.run(
                    "tc qdisc %(add)s dev %(iface)s parent 1:%(ticket)s0 handle %(ticket)s0:"
                    "  netem %(netem)s", **opts)
            elif bind:
                # No QoS: just use SFQ
                Commands.run(
                    "tc qdisc %(add)s dev %(iface)s parent 1:%(ticket)s0"
                    "  handle %(ticket)s0: sfq",
                    **opts)
        # iptables to classify and accounting
        opts = dict(
            A=(bind and "A" or "D"),
            outgoing=interface,
            client=client,
            mark=mark[0], mask=mark[1],
            ticket=ticket,
            iptables=self.isipv6(client) and "ip6tables" or "iptables",
            **self.config)
        for incoming in self.router.incoming:
            Commands.run(
                # Mark the incoming packet from the client
                "%(iptables)s -t mangle -%(A)s %(prerouting)s -i %(incoming)s"
                "  -s %(client)s -j MARK --set-mark %(mark)s/%(mask)s",
                incoming=incoming,
                **opts)
        Commands.run(
            # Keep the mark only if we reached the output interface
            "%(iptables)s -t mangle -%(A)s %(postrouting)s "
            "  -o %(outgoing)s -s %(client)s -m mark --mark %(mark)s/%(mask)s"
            "  -j CONNMARK --save-mark --nfmask %(mask)s --ctmask %(mask)s",
            # Classify. Outgoing
            "%(iptables)s -t mangle -%(A)s %(postrouting)s"
            "  -o %(outgoing)s -m connmark --mark %(mark)s/%(mask)s"
            "  -j CLASSIFY --set-class 1:%(ticket)s0",
            **opts)
        for incoming in self.router.incoming:
            Commands.run(
                # Classify. Incoming
                "%(iptables)s -t mangle -%(A)s %(postrouting)s"
                "  -o %(incoming)s -m connmark --mark %(mark)s/%(mask)s"
                "  -j CLASSIFY --set-class 1:%(ticket)s0",
                incoming=incoming,
                **opts)
        Commands.run(
            # Accounting. Outgoing
            "%(iptables)s -t mangle -%(A)s %(accounting)s"
            "  -o %(outgoing)s -m connmark --mark %(mark)s/%(mask)s"
            "  -m comment --comment up-%(outgoing)s-%(client)s",
            **opts)
        for incoming in self.router.incoming:
            Commands.run(
                # Accouting. Incoming
                "%(iptables)s -t mangle -%(A)s %(accounting)s"
                "  -o %(incoming)s -m connmark --mark %(mark)s/%(mask)s"
                "  -m comment --comment down-%(outgoing)s-%(client)s",
                incoming=incoming,
                **opts)

    def notify(self, event, router, **kwargs):
        """Handle an event.

        The event is either binding a user or unbinding it. It this is
        the first time we bind a user, :func:`setup` is called. The
        real work for binding/unbinding is done by :func:`bind`.

        :param event: event received
        :type event: string
        :param router: router that triggered the event
        :type router: instance of :class:`Router`
        """
        if self.router is None:
            self.router = router
            self.setup()
        elif self.router != router:
            raise ValueError(
                "already bound to another router (%s != %s)" % (self.router, router))
        if event == "bind":
            client = kwargs['client']
            interface = kwargs['interface']
            qos = kwargs['qos']
            logger.info("bind %s" % client)
            # Do the binding
            slot = self.slots.request(interface, client)
            ticket = self.tickets.request(client)
            self.bind(client, interface, qos)
        elif event == "unbind":
            client = kwargs['client']
            interface, qos = self.router.clients[client]
            logger.info("unbind %s from interface %s" % (client, interface))
            # Undo the binding
            self.bind(client, interface, qos, bind=False)
            slot = self.slots.release(client)
            ticket = self.tickets.release(client)

    STATSRE=re.compile(
        r'^.* --comment "(?P<direction>up|down)-(?P<interface>[^"]+)-'
        r'(?P<client>[0-9a-f:.]+)" -c \d+ (?P<bytes>\d+)$')

    def stats(self):
        """Return statistics for each interface and client."""
        if self.router is None:
            return {}           # Setup is not done yet
        stats = {}
        output = "\n".join([Commands.run("%(iptables)s -t mangle -v -S %(accounting)s",
                                         iptables=iptables,
                                         **self.config) for iptables in self.iptables])
        for line in output.split("\n"):
            mo = self.STATSRE.match(line.strip())
            if mo:
                interface = mo.group('interface')
                direction = mo.group('direction')
                client = mo.group('client')
                if interface not in stats:
                    stats[interface] = {}
                    stats[interface]['details'] = {}
                if client not in stats[interface]['details']:
                    stats[interface]['details'][client]= {}
                stats[interface]['details'][client][direction] = int(mo.group("bytes"))
        for interface in stats:
            up = down = clients = 0
            for client in stats[interface]['details']:
                clients = clients + 1
                up = up + stats[interface]['details'][client].get("up", 0)
                down = down + stats[interface]['details'][client].get("down", 0)
            stats[interface]["clients"] = clients
            stats[interface]["up"] = up
            stats[interface]["down"] = down
        return stats

class PersistentBinder(object):
    """Keep track of client bindings and allow persistence to a file.

    This binder will just record each client binding into a file and
    allow to restore them when the application restarts.
    """

    zope.interface.implements(IBinder)

    def __init__(self, save):
        """Initialize this instance of saving binder.

        :param save: file where to store persistent information
        :type save: string
        """
        self.save = save
        self.bindings = {}

    def restore(self, router):
        """Restore bindings from saved file

        :param router: router where to restore bindings
        :type router: :class:`Router`
        """
        logger.info("restore bindings from %s" % self.save)
        self.bindings = pickle.load(file(self.save, "r"))
        for client in self.bindings:
            eth, qos = self.bindings[client]
            try:
                router.bind(client, eth, qos)
            except:
                logger.exception("unable to rebind %r" % client)

    def notify(self, event, router, **kwargs):
        """Handle an event.

        The event is either binding a user or unbinding it. We update
        our client table and save it to disk.

        :param event: event received
        :type event: string
        :param router: router that triggered the event
        :type router: instance of :class:`Router`
        """
        if event == "bind":
            self.bindings[kwargs['client']] = (kwargs['interface'], kwargs['qos'])
        elif event == "unbind":
            del self.bindings[kwargs['client']]
        logger.info("save bindings to %s" % self.save)
        pickle.dump(self.bindings, file(self.save, "w"))

class LinuxBinderIPv4(LinuxBinder):
    """IPv4 only version of `LinuxBinder`."""

    iptables = [ "iptables" ]
    ipcmd = [ "ip" ]

    def isipv6(self, client):
        if LinuxBinder.isipv6(self, client):
            raise NotImplementedError("cannot use IPv6 address with this binder")
        return False
