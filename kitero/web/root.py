import socket

from kitero.web import app
from kitero.web.decorators import templated
import kitero.web.api

hostname=socket.gethostname()
try:
    hostname=socket.gethostbyaddr(hostname)[0]
except: # pragma: no cover
    pass

@app.route("/")
@templated
def kitero():
    """Index page for the application.

    This returns the static HTML+JS application.
    """
    return dict(hostname=hostname)
