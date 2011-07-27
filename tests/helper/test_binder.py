try:
    import unittest2 as unittest
except ImportError: # pragma: no cover
    import unittest

import yaml
import os
import stat
import tempfile
import shutil
from functools import wraps

from kitero.helper.binder import LinuxBinder
from kitero.helper.router import Router

# SaveBinder is tested in test_service.py

class TestBinder(unittest.TestCase):
    def setUp(self):
        self.binder = LinuxBinder()
        doc = """
clients: eth0
interfaces:
  eth1:
    name: LAN
    description: "My first interface"
    qos:
      - qos1
      - qos2
  eth2:
    name: WAN
    description: "My second interface"
    qos:
      - qos1
      - qos3
      - qos4
qos:
  qos1:
    name: "100M"
    description: "My first QoS"
    bandwidth:
        down: 100mbps
        up: 50mbps
    netem: delay 100ms 10ms distribution experimental
  qos2:
    name: "10M"
    description: "My second QoS"
    bandwidth: 10mbps
    netem: delay 200ms 10ms
  qos3:
    name: "1M"
    description: "My third QoS"
    netem:
      down: delay 500ms 30ms
      up: delay 10ms 2ms loss 0.01%
  qos4:
    name: "unlimited"
    description: "My fourth QoS"
"""
        self.router = Router.load(yaml.load(doc))
        self.router.register(self.binder)
        # Provide fake binaries for `ip`, `iptables`, `tc`
        self.temp = tempfile.mkdtemp()
        biny = os.path.join(self.temp, "bin")
        os.mkdir(biny)
        self.oldpath = os.environ['PATH']
        os.environ['PATH'] = "%s:%s" % (biny, os.environ['PATH'])
        f = file(os.path.join(biny, "fake"), "w")
        f.write("""#!/bin/sh

echo $(basename $0) "$@" >> "%s"
case "$(basename $0) $@" in
   "iptables -t mangle -v -S kitero-ACCOUNTING")
  cat <<EOF
-N kitero-ACCOUNTING
-A kitero-ACCOUNTING -o eth2 -m connmark --mark 0x40000000/0xffe00000 -m comment --comment "up-eth2-172.29.7.14" -c 39219 2079628
-A kitero-ACCOUNTING -o eth0 -m connmark --mark 0x40000000/0xffe00000 -m comment --comment "down-eth2-172.29.7.14" -c 72867 108647983
-A kitero-ACCOUNTING -o eth2 -m connmark --mark 0x41000000/0xffe00000 -m comment --comment "up-eth2-172.29.7.15" -c 247 20796
-A kitero-ACCOUNTING -o eth0 -m connmark --mark 0x41000000/0xffe00000 -m comment --comment "down-eth2-172.29.7.15" -c 867 2015775
-A kitero-ACCOUNTING -o eth1 -m connmark --mark 0x20000000/0xffe00000 -m comment --comment "up-eth1-172.29.7.19" -c 8888 99999
-A kitero-ACCOUNTING -o eth0 -m connmark --mark 0x20000000/0xffe00000 -m comment --comment "down-eth1-172.29.7.19" -c 8888 11111
EOF
  ;;
esac
exit 0
""" % os.path.join(self.temp, "output.txt"))
        f.close()
        os.chmod(os.path.join(biny, "fake"),
                 stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH |
                 stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        for ex in ['iptables', 'tc', 'ip']:
            os.symlink("fake", os.path.join(biny, ex))

    # Redirect future output to some file named after the function
    def out(f):
        @wraps(f)
        def decorated_function(self, *args, **kwargs):
            self.cur = os.path.join(self.temp, "output.txt")
            os.symlink(f.__name__, self.cur)
            return f(self, *args, **kwargs)
        return decorated_function

    SETUP = """iptables -t mangle -D PREROUTING -j kitero-PREROUTING
iptables -t mangle -F kitero-PREROUTING
iptables -t mangle -X kitero-PREROUTING
iptables -t mangle -N kitero-PREROUTING
iptables -t mangle -I PREROUTING -j kitero-PREROUTING
iptables -t mangle -D POSTROUTING -j kitero-ACCOUNTING
iptables -t mangle -F kitero-ACCOUNTING
iptables -t mangle -X kitero-ACCOUNTING
iptables -t mangle -N kitero-ACCOUNTING
iptables -t mangle -I POSTROUTING -j kitero-ACCOUNTING
iptables -t mangle -D POSTROUTING -j kitero-POSTROUTING
iptables -t mangle -F kitero-POSTROUTING
iptables -t mangle -X kitero-POSTROUTING
iptables -t mangle -N kitero-POSTROUTING
iptables -t mangle -I POSTROUTING -j kitero-POSTROUTING
tc qdisc del dev eth1 root
tc qdisc add dev eth1 root handle 1: drr
tc class add dev eth1 parent 1: classid 1:2 drr
tc qdisc add dev eth1 parent 1:2 handle 12: sfq
tc filter add dev eth1 protocol arp parent 1:0 prio 1 u32 match u32 0 0 flowid 1:2
iptables -t mangle -A kitero-POSTROUTING -o eth1 -j CLASSIFY --set-class 1:2
tc qdisc del dev eth2 root
tc qdisc add dev eth2 root handle 1: drr
tc class add dev eth2 parent 1: classid 1:2 drr
tc qdisc add dev eth2 parent 1:2 handle 12: sfq
tc filter add dev eth2 protocol arp parent 1:0 prio 1 u32 match u32 0 0 flowid 1:2
iptables -t mangle -A kitero-POSTROUTING -o eth2 -j CLASSIFY --set-class 1:2
tc qdisc del dev eth0 root
tc qdisc add dev eth0 root handle 1: drr
tc class add dev eth0 parent 1: classid 1:2 drr
tc qdisc add dev eth0 parent 1:2 handle 12: sfq
tc filter add dev eth0 protocol arp parent 1:0 prio 1 u32 match u32 0 0 flowid 1:2
iptables -t mangle -A kitero-POSTROUTING -o eth0 -j CLASSIFY --set-class 1:2
ip rule del fwmark 0x40000000/0xc0000000 table eth1
ip rule add fwmark 0x40000000/0xc0000000 table eth1
ip rule del fwmark 0x80000000/0xc0000000 table eth2
ip rule add fwmark 0x80000000/0xc0000000 table eth2
"""

    @out
    def test_setup(self):
        """Ask binder to setup the environment"""
        self.binder.router = self.router
        self.binder.setup()
        self.assertEqual(file(self.cur).read().split("\n"), self.SETUP.split("\n"))

    @out
    def test_setup_and_binding(self):
        """Ask binder to bind a client for the first time"""
        self.router.bind("192.168.15.2", "eth1", "qos1")
        self.assertEqual(file(self.cur).read().split("\n"), (self.SETUP + 
"""tc class add dev eth1 parent 1: classid 1:10 drr
tc qdisc add dev eth1 parent 1:10 handle 10: tbf rate 50mbps buffer 10Mbit latency 1s
tc qdisc add dev eth1 parent 10:1 handle 11: netem delay 100ms 10ms distribution experimental
tc class add dev eth0 parent 1: classid 1:10 drr
tc qdisc add dev eth0 parent 1:10 handle 10: tbf rate 100mbps buffer 10Mbit latency 1s
tc qdisc add dev eth0 parent 10:1 handle 11: netem delay 100ms 10ms distribution experimental
iptables -t mangle -A kitero-PREROUTING -i eth0 -s 192.168.15.2 -j MARK --set-mark 0x40000000/0xffc00000
iptables -t mangle -A kitero-POSTROUTING -o eth1 -s 192.168.15.2 -m mark --mark 0x40000000/0xffc00000 -j CONNMARK --save-mark --nfmask 0xffc00000 --ctmask 0xffc00000
iptables -t mangle -A kitero-POSTROUTING -o eth1 -m connmark --mark 0x40000000/0xffc00000 -j CLASSIFY --set-class 1:10
iptables -t mangle -A kitero-POSTROUTING -o eth0 -m connmark --mark 0x40000000/0xffc00000 -j CLASSIFY --set-class 1:10
iptables -t mangle -A kitero-ACCOUNTING -o eth1 -m connmark --mark 0x40000000/0xffc00000 -m comment --comment up-eth1-192.168.15.2
iptables -t mangle -A kitero-ACCOUNTING -o eth0 -m connmark --mark 0x40000000/0xffc00000 -m comment --comment down-eth1-192.168.15.2
""").split("\n"))

    @out
    def test_several_binds(self):
        """Ask binder to bind several clients"""
        self.router.bind("192.168.15.2", "eth1", "qos1")
        self.router.bind("192.168.15.3", "eth1", "qos2")
        self.router.bind("192.168.15.4", "eth2", "qos3")
        os.unlink(self.cur)
        self.router.bind("192.168.15.5", "eth2", "qos3")
        self.assertEqual(file(self.cur).read().split("\n"),
"""tc class add dev eth2 parent 1: classid 1:40 drr
tc qdisc add dev eth2 parent 1:40 handle 40: netem delay 10ms 2ms loss 0.01%
tc class add dev eth0 parent 1: classid 1:40 drr
tc qdisc add dev eth0 parent 1:40 handle 40: netem delay 500ms 30ms
iptables -t mangle -A kitero-PREROUTING -i eth0 -s 192.168.15.5 -j MARK --set-mark 0x80400000/0xffc00000
iptables -t mangle -A kitero-POSTROUTING -o eth2 -s 192.168.15.5 -m mark --mark 0x80400000/0xffc00000 -j CONNMARK --save-mark --nfmask 0xffc00000 --ctmask 0xffc00000
iptables -t mangle -A kitero-POSTROUTING -o eth2 -m connmark --mark 0x80400000/0xffc00000 -j CLASSIFY --set-class 1:40
iptables -t mangle -A kitero-POSTROUTING -o eth0 -m connmark --mark 0x80400000/0xffc00000 -j CLASSIFY --set-class 1:40
iptables -t mangle -A kitero-ACCOUNTING -o eth2 -m connmark --mark 0x80400000/0xffc00000 -m comment --comment up-eth2-192.168.15.5
iptables -t mangle -A kitero-ACCOUNTING -o eth0 -m connmark --mark 0x80400000/0xffc00000 -m comment --comment down-eth2-192.168.15.5
""".split("\n"))

    @out
    def test_unbind(self):
        """Bind two clients, unbind one"""
        self.router.bind("192.168.15.2", "eth2", "qos3")
        self.router.bind("192.168.15.3", "eth1", "qos1")
        os.unlink(self.cur)
        self.router.unbind("192.168.15.2")
        self.assertEqual(file(self.cur).read().split("\n"),
"""tc class del dev eth2 parent 1: classid 1:10 drr
tc class del dev eth0 parent 1: classid 1:10 drr
iptables -t mangle -D kitero-PREROUTING -i eth0 -s 192.168.15.2 -j MARK --set-mark 0x80000000/0xffc00000
iptables -t mangle -D kitero-POSTROUTING -o eth2 -s 192.168.15.2 -m mark --mark 0x80000000/0xffc00000 -j CONNMARK --save-mark --nfmask 0xffc00000 --ctmask 0xffc00000
iptables -t mangle -D kitero-POSTROUTING -o eth2 -m connmark --mark 0x80000000/0xffc00000 -j CLASSIFY --set-class 1:10
iptables -t mangle -D kitero-POSTROUTING -o eth0 -m connmark --mark 0x80000000/0xffc00000 -j CLASSIFY --set-class 1:10
iptables -t mangle -D kitero-ACCOUNTING -o eth2 -m connmark --mark 0x80000000/0xffc00000 -m comment --comment up-eth2-192.168.15.2
iptables -t mangle -D kitero-ACCOUNTING -o eth0 -m connmark --mark 0x80000000/0xffc00000 -m comment --comment down-eth2-192.168.15.2
""".split("\n"))

    @out
    def test_unbind_bind(self):
        """Bind three clients, unbind one, bind another one"""
        self.router.bind("192.168.15.2", "eth1", "qos1")
        self.router.bind("192.168.15.3", "eth1", "qos1")
        self.router.bind("192.168.15.4", "eth1", "qos1")
        self.router.bind("192.168.15.5", "eth1", "qos1")
        os.unlink(self.cur)
        self.router.bind("192.168.15.6", "eth1", "qos1")
        print file(self.cur).read()
        self.assertIn("--mark 0x41000000", file(self.cur).read())
        self.assertIn("--set-class 1:50", file(self.cur).read())
        self.router.unbind("192.168.15.2")
        os.unlink(self.cur)
        # Next one should get ticket and mark from 15.2
        self.router.bind("192.168.15.7", "eth1", "qos1")
        self.assertIn("--mark 0x40000000", file(self.cur).read())
        self.assertIn("--set-class 1:10", file(self.cur).read())
        self.router.unbind("192.168.15.4")
        os.unlink(self.cur)
        # Next one should get ticket and mark from 15.4
        self.router.bind("192.168.15.8", "eth1", "qos1")
        self.assertIn("--mark 0x40800000", file(self.cur).read())
        self.assertIn("--set-class 1:30", file(self.cur).read())
        self.router.unbind("192.168.15.6")
        os.unlink(self.cur)
        # Next one should get ticket and mark from 15.6
        self.router.bind("192.168.15.9", "eth1", "qos1")
        self.assertIn("--mark 0x41000000", file(self.cur).read())
        self.assertIn("--set-class 1:50", file(self.cur).read())
        self.router.bind("192.168.15.10", "eth2", "qos1")
        self.router.unbind("192.168.15.9")
        os.unlink(self.cur)
        # Next one should get ticket from 15.9 but new mark (not the same interface)
        self.router.bind("192.168.15.11", "eth2", "qos1")
        self.assertIn("--mark 0x80400000", file(self.cur).read())
        self.assertIn("--set-class 1:50", file(self.cur).read())

    def test_bind_once(self):
        """The binder should be bound to only one router"""
        self.binder.notify("unknown", self.router)
        self.binder.notify("unknwon", self.router)
        with self.assertRaises(ValueError):
            self.binder.notify("unknwon", Router("eth0"))

    @out
    def test_no_qos(self):
        """Bind without QoS"""
        self.router.bind("192.168.15.11", "eth2", "qos1")
        os.unlink(self.cur)
        self.router.bind("192.168.15.5", "eth2", "qos4")
        self.assertEqual(file(self.cur).read().split("\n"),
"""tc class add dev eth2 parent 1: classid 1:20 drr
tc qdisc add dev eth2 parent 1:20 handle 20: sfq
tc class add dev eth0 parent 1: classid 1:20 drr
tc qdisc add dev eth0 parent 1:20 handle 20: sfq
iptables -t mangle -A kitero-PREROUTING -i eth0 -s 192.168.15.5 -j MARK --set-mark 0x80400000/0xffc00000
iptables -t mangle -A kitero-POSTROUTING -o eth2 -s 192.168.15.5 -m mark --mark 0x80400000/0xffc00000 -j CONNMARK --save-mark --nfmask 0xffc00000 --ctmask 0xffc00000
iptables -t mangle -A kitero-POSTROUTING -o eth2 -m connmark --mark 0x80400000/0xffc00000 -j CLASSIFY --set-class 1:20
iptables -t mangle -A kitero-POSTROUTING -o eth0 -m connmark --mark 0x80400000/0xffc00000 -j CLASSIFY --set-class 1:20
iptables -t mangle -A kitero-ACCOUNTING -o eth2 -m connmark --mark 0x80400000/0xffc00000 -m comment --comment up-eth2-192.168.15.5
iptables -t mangle -A kitero-ACCOUNTING -o eth0 -m connmark --mark 0x80400000/0xffc00000 -m comment --comment down-eth2-192.168.15.5
""".split("\n"))

    def test_stats(self):
        """Grab some statistics"""
        self.router.bind("192.168.15.11", "eth2", "qos1") # For initialization
        self.assertEqual(self.binder.stats(),
                         dict(eth1=dict(clients=1,
                                        up=99999,
                                        down=11111,
                                        details={"172.29.7.19":
                                                     dict(up=99999, down=11111)}),
                              eth2=dict(clients=2,
                                        up=(2079628+20796),
                                        down=(108647983+2015775),
                                        details={"172.29.7.14":
                                                     dict(up=2079628, down=108647983),
                                                 "172.29.7.15":
                                                     dict(up=20796, down=2015775)})))

    def test_no_stats(self):
        """Grab stats when not initialized"""
        self.assertEqual(self.binder.stats(), {})

    def tearDown(self):
        os.environ['PATH'] = self.oldpath
        shutil.rmtree(self.temp)

from kitero.helper.binder import Mark

class TestMark(unittest.TestCase):
    def test_mark_size(self):
        """Check the computed sizes for marks"""
        m = Mark(7, 8)
        self.assertEqual(m.bits['slots'], 3)
        self.assertEqual(m.bits['interfaces'], 3)
        m = Mark(8, 8)
        self.assertEqual(m.bits['interfaces'], 4)
        m = Mark((1<<28) - 1, 1<<4)
        self.assertEqual(m.bits['slots'], 4)
        self.assertEqual(m.bits['interfaces'], 28)
        with self.assertRaises(ValueError):
            m = Mark(1<<28, 1<<4)

    def test_mark_value(self):
        """Check appropriate values for marks"""
        m = Mark(15,8)
        self.assertEqual(m(1,None), ("0x20000000", "0xf0000000"))
        self.assertEqual(m(None,1), ("0x02000000", "0x0e000000"))
        self.assertEqual(m(7,3), ("0x86000000", "0xfe000000"))

from kitero.helper.binder import SlotsProvider

class TestSlots(unittest.TestCase):
    def test_requests(self):
        """Request a slot"""
        s = SlotsProvider(10)
        self.assertEqual(s.request("eth1", "192.168.1.1"), 0)
        self.assertEqual(s.request("eth1", "192.168.1.2"), 1)
        self.assertEqual(s.request("eth1", "192.168.1.3"), 2)
        self.assertEqual(s.request("eth3", "192.168.1.4"), 0)
        self.assertEqual(s.request("eth3", "192.168.1.5"), 1)
        self.assertEqual(s.get("192.168.1.5"), 1)

    def test_releases(self):
        """Release slots"""
        s = SlotsProvider(10)
        s.request("eth1", "192.168.1.1")
        s.request("eth1", "192.168.1.2")
        s.request("eth1", "192.168.1.3")
        s.request("eth2", "192.168.1.4")
        s.request("eth2", "192.168.1.5")
        self.assertEqual(s.release("192.168.1.1"), 0)
        self.assertEqual(s.release("192.168.1.3"), 2)
        self.assertEqual(s.release("192.168.1.5"), 1)

    def test_requests_releases(self):
        """Request and release slots"""
        s = SlotsProvider(10)
        s.request("eth1", "192.168.1.1")
        s.request("eth1", "192.168.1.2")
        s.request("eth1", "192.168.1.3")
        s.request("eth2", "192.168.1.4")
        s.request("eth2", "192.168.1.5")
        s.release("192.168.1.1")
        s.release("192.168.1.3")
        s.release("192.168.1.5")
        self.assertEqual(s.request("eth2", "192.168.1.1"), 1)
        self.assertEqual(s.request("eth1", "192.168.1.5"), 0)
        self.assertEqual(s.request("eth1", "192.168.1.3"), 2)

    def test_no_free_slots(self):
        """Request too much slots"""
        s = SlotsProvider(10)
        for i in range(10):
            s.request("eth1", "192.168.1.%d" % i)
        s.request("eth2", "192.168.2.1")
        with self.assertRaises(RuntimeError):
            s.request("eth1", "192.168.1.10")
        s.release("192.168.1.5")
        self.assertEqual(s.request("eth1", "192.168.1.10"), 5)

    def test_bogus_requests_releases(self):
        """Requests twice or release twice"""
        s = SlotsProvider(10)
        s.request("eth1", "192.168.1.10")
        with self.assertRaises(ValueError):
            s.request("eth1", "192.168.1.10")
        self.assertEqual(s.request("eth1", "192.168.1.11"), 1)
        s.release("192.168.1.10")
        with self.assertRaises(ValueError):
            s.release("192.168.1.10")
        with self.assertRaises(ValueError):
            s.get("192.168.1.10")

from kitero.helper.binder import TicketsProvider

class TestTickets(unittest.TestCase):
    def test_tickets(self):
        """Request and release tickets"""
        t = TicketsProvider()
        self.assertEqual(t.request("192.168.1.1"), 1)
        self.assertEqual(t.request("192.168.1.2"), 2)
        self.assertEqual(t.request("192.168.1.3"), 3)
        self.assertEqual(t.request("192.168.1.4"), 4)
        self.assertEqual(t.request("192.168.1.5"), 5)
        self.assertEqual(t.request("192.168.1.6"), 6)
        self.assertEqual(t.request("192.168.1.7"), 7)
        self.assertEqual(t.request("192.168.1.8"), 8)
        self.assertEqual(t.release("192.168.1.1"), 1)
        self.assertEqual(t.release("192.168.1.6"), 6)
        self.assertEqual(t.release("192.168.1.8"), 8)
        self.assertEqual(t.request("192.168.1.10"), 1)
        self.assertEqual(t.request("192.168.1.11"), 6)
        self.assertEqual(t.request("192.168.1.12"), 8)
        self.assertEqual(t.request("192.168.1.13"), 9)
        self.assertEqual(t.get("192.168.1.11"), 6)

    def test_errors(self):
        """Requests and release bogus tickets"""
        t = TicketsProvider()
        self.assertEqual(t.request("192.168.1.1"), 1)
        with self.assertRaises(ValueError):
            t.request("192.168.1.1")
        self.assertEqual(t.request("192.168.1.2"), 2)
        self.assertEqual(t.request("192.168.1.3"), 3)
        self.assertEqual(t.release("192.168.1.2"), 2)
        with self.assertRaises(ValueError):
            t.release("192.168.1.2")
