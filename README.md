Kitérő
------

Kitérő is a tool allowing a user to choose the output interface and
the associated QoS that should be used to route her packets. It
contains a **daemon** issuing commands to configure the router, a
**web service** and a **web interface** using this service providing
an API to let a user chooses her interface and QoS.

The user will point her browser to the IP address of the router and
will be presented a simple interface allowing to choose the interface
that should be used to route her packets and the associated QoS.

The documentation can be built with `python setup.py build_sphinx`.

Facebook published a similar tool: [Augmented Traffic Control][]. You
may want to look at it. However, only one output interface can be used
(it only handles QoS).

[Augmented Traffic Control]: https://github.com/facebook/augmented-traffic-control
