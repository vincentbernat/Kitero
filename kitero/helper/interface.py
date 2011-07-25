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
