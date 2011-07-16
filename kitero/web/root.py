import socket

from kitero.web import app
from kitero.web.decorators import templated
import kitero.web.api

@app.route("/")
@templated
def kitero():
    """Index page for the application.

    This returns the static HTML+JS application.
    """
    return dict(hostname=socket.gethostbyaddr(socket.gethostname())[0])
