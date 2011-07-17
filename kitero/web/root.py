from kitero.web import app
import kitero.web.api

@app.route("/")
def index():
    """Index page for the application.

    This returns the static HTML+JS application.
    """
    return "Hello world\n"
