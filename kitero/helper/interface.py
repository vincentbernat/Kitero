import zope.interface

class IBinder(zope.interface.Interface):
    """Interface for a binder to be used by :class:`kitero.helper.router.Router`"""

    def notify(event, router, **kwargs):
        """Callback used when an event (i.e a binding) happens.

        :param event: event received (bind or unbind)
        :type event: string
        :param router: router that triggered the event
        :type router: instance of :class:`Router`
        """

class IStatsProvider(zope.interface.Interface):
    """Interface for objects providing stats about clients.

    Such an object should be able to return the current statistics for
    the clients it manages.
    """

    def stats():
        """Return the current values for managed statistics.

        All statistics are optional and an empty dictionary could be
        returned. This function should return a dictionary whose keys
        are the interfaces for which stats are available. For each
        interface, we get the number of active clients for this
        interface (as `clients`), the upload and download speed (`up`
        and `down`) in bytes/s and a dictionary of clients (`details`). This
        dictionary is keyed by client IP and features two keys: `up`
        and `down`.

        Here is an example of allowed output::

            dict(eth1=dict(clients=5,
                up=45,
                down=457,
                details={
                  "172.16.10.14": dict(up=0, down=0),
                  "172.16.10.15": dict(up=14, down=155)
                }))
        """
