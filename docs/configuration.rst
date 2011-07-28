Configuring Kitérő
==================

Basic configuration
-------------------

The next step is to configure Kitérő. The configuration is done in a
`YAML <http://en.wikipedia.org/wiki/YAML>`_ configuration file that
should be provided to both the helper and the web service. A sample
configuration file can be found in ``docs/sample.yaml``.

The configuration file accepts three sections:

1. ``web`` to configure the web service
2. ``helper`` to configure the helper service
3. ``router`` to define available interfaces and QoS

``web``
```````

None of the directives in this section are required.

========== =========== ====================
Directive  Default     Comment
========== =========== ====================
``listen`` ``0.0.0.0`` IP address the web service
                       should listen to.
``port``   ``8187``    Port the web service
                       should listen to. This must
                       be a port greater than 1024.
                       Use ``iptables`` to redirect
                       access to port 80 to this
                       port.
``debug``  ``false``   Enable debugging. This should not
                       be done on production.
``expire`` ``900``     After how many seconds an inactive
                       client should be purged
========== =========== ====================

``helper``
``````````

None of the directives in this section are required.

========== ============= ====================
Directive  Default       Comment
========== ============= ====================
``listen`` ``127.0.0.1`` IP address the helper service
                         should listen to.
``port``   ``18861``     Port the helper service
                         should listen to.
``save``   None          Save and restore bindings
                         from this file. This allows
                         bindings to remain persistent
                         across restart of the helper.
========== ============= ====================

``router``
``````````

This section describes the available interfaces and the associated
QoS. You should at least define one interface and for each interface,
you need to specify at least one QoS.

============== ====================
Directive      Comment
============== ====================
``clients``    Which interface the clients are
               connected to. This is mandatory
               to specify an interface here. For
               example, ``eth0``
``interfaces`` List of available interfaces.
``qos``        List of QoS definitions.
============== ====================

A list of interfaces is in fact a mapping between the physical
interface name and a description of the interface. Physical names
should be used only once. Moreover, they must not conflict with the
value of ``clients``. The following attributes should be used to
define an interface. They are mandatory.

=============== ====================
Attribute       Comment
=============== ====================
``name``        User friendly name for the interface.
	        This is not the physical name of the interface.
                For example ``LAN``.
``description`` Description of the interface (targeted at the user)
``qos``         A list of QoS names. This is not a list of QoS
                definitions. Since QoS can be reused on several
    		interfaces, we only specify names here.
=============== ====================

Each QoS specified in the definition of an interface should be defined
in the ``qos`` section. The list of QoS definitions is a mapping
between a QoS name and the definition of the QoS. The following
attributes should be used to define a QoS.

================ ========================================================
Attribute        Comment
================ ========================================================
``name``         User friendly name for the QoS. This is
                 just a display name. It is mandatory to
                 specify one.
``description``  Mandatory description of the QoS.
``bandwidth``    Optional bandwidth for the QoS. The syntax should
                 be accepted by ``tc``. For example, ``20mbps`` is a
                 valid value. If you want to specify a different
                 bandwidth for upload and download, you can specify a
                 mapping with ``up`` and ``down`` as keys and the
                 appropriate bandwidth.
``netem``        Optional netem settings to apply for the QoS. The
                 syntax should
                 be accepted by ``tc`` for the ``netem``
		 module. ``delay 200ms 15ms`` will add an
                 average delay of 200 ms with a possible variation of
                 15 ms. As for bandwidth, it is possible to specify
                 different parameters for download and upload by
                 providing a
                 mapping with ``up`` and ``down`` as keys.
================ ========================================================

See the `documentation of netem`_ for more information on the accepted
values for the ``netem`` keyword.

.. _documentation of netem: http://www.linuxfoundation.org/collaborate/workgroups/networking/netem

Here is a short example for the ``router`` block::

    router:
      clients: eth0
      interfaces:
	eth1:
	  name: LAN
	  description: "LAN access"
	  qos:
	    - 100mbps
	    - 10mbps
	eth2:
	  name: WAN
	  description: "WAN access"
	  qos:
	    - 10mbps
      qos:
	100mbps:
	  name: 100Mbps
	  description: "Restrict the bandwidth to 100 Mbps in both directions."
	  bandwidth:
	     up: 100mbps
	     down: 90mbps
	10mbps:
	  name: 10Mbps
	  description: "Restrict the bandwidth to 10 Mbps in both directions."
	  bandwidth: 10mbps

Start services
--------------

Once Kitérő has been installed and the configuration file has been
installed, we need to start the helper and the web service. They both
need the configuration file as an argument::

  $ kitero-web /path/to/conf.yaml
  $ sudo kitero-helper /path/to/conf.yaml

``kitero-helper`` accepts some additional arguments to configure
logging. See ``kitero-helper --help`` for additional details.

Use something like ``start-stop-daemon`` if you want to daemonize
those services. You can test if everything works as expected with the
following command::

  $ curl http://127.0.0.1:8187/api/1.0/current
  {
    "status": 0, 
    "value": {
      "ip": "127.0.0.1"
    }, 
    "time": "2011-07-24T00:08:05+0200"
  }

QoS configuration
-----------------

Kitérő relies on `netem`_ to emulate a wide variety of networks by
adding latency, loss, duplication, corruption and reordering. It is
possible to do some measurements. For example, assume we are connected
to some ADSL network::

    $ apt-get source iproute
    $ cd iproute-20110629/netem
    $ make
    cc  -I../include -o maketable maketable.c -lm
    cc  -I../include -o normal normal.c -lm
    cc  -I../include -o pareto pareto.c -lm
    cc  -I../include -o paretonormal paretonormal.c -lm
    ./normal > normal.dist
    ./pareto > pareto.dist
    ./paretonormal > paretonormal.dist
    ./maketable experimental.dat > experimental.dist
    $ cc -I../include -o stats stats.c -lm

We need to gather some statistics to configure the ``delay`` parameter
appropriately::

    $ sudo ping -U  -c 10000  -i 0.1 88.176.20.254 | \
    >      sed -n 's/^.*icmp_req=\([0-9]*\) .*time=\([0-9.]*\) ms/\1 \2/p' \
    >     > adsl.dat
    $ sort -n adsl.dat | awk '{print $NF}' | ./stats
    mu =       21.922970
    sigma =     6.944398
    rho =      -0.037530

Therefore, we can use ``delay 22ms 7ms 3.4%``. We can account for data
loss too::

    $ awk 'BEGIN {loss=0}
    >             {if (NR != $1 - loss) { loss = loss + 1 ; print 1 }
    >                                   else print 0 }' adsl.dat | \
    >          | ./stats
    mu =        0.000400
    sigma =     0.020001
    rho =       0.499800

Therefore, we can add ``loss 0.04% 50%``. We did not get duplication
or packet corruption, but this can be added with the keywords
``duplicate`` and ``corrupt``.

The measurements are user-to-user roundtrips. Therefore, we either
need to half each value and get ``delay 11ms 3.5ms 3.4% loss 0.02%
50%`` or we just apply netem to one direction. The first way does not
allow correlation to work correctly while the second way only impact
one direction while packet losses may occur in both directions.

.. _netem: http://www.linuxfoundation.org/collaborate/workgroups/networking/netem
