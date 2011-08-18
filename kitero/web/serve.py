import sys
import os.path

def run(config={}):
    """Start Kitero web service.

    :param config: configuration of the application
    """ 
    app = application(config)
    app.run(host=app.config['LISTEN'],
            port=app.config['PORT'])

def application(config={}):
    """Return Kitero application.

    This function could be the entry point for WSGI.
    """
    from kitero.web import app
    configure(app, config)
    return app

def configure(app, config={}):
    # Load configuration
    import kitero.config
    config = kitero.config.merge(config)
    # Configure helper
    app.config['HELPERIP'] = config['helper']['listen']
    app.config['HELPERPORT'] = config['helper']['port']
    # Configure the remaining
    config = config['web']
    for key in config:
        app.config[key.upper()] = config[key]

def _run(): # pragma: no cover
    if len(sys.argv[1:]):
        import yaml
        run(yaml.safe_load(file(sys.argv[1])))
    else:
        run()

if __name__ == "__main__": # pragma: no cover
    # Fix sys.path
    # This allows to be called with `python -m kitero.web.serve`
    curdir = os.path.dirname(__file__)
    if curdir in sys.path:
        index = sys.path.index(curdir)
        sys.path.remove(curdir)
        sys.path.insert(index,
                        os.path.dirname(os.path.dirname(curdir)))
    # Run app
    _run()
