import zope.interface

class IObserver(zope.interface.Interface):
    """Interface for an observer"""

    def notify(event, source, **kwargs):
        """Callback used when an event happens.

        :param event: event received
        :type event: string
        :param source: source object that triggered the event
        """
