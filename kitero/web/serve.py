import sys
import os.path

def run(config={}):
    """Start Kitero web service.

    :param config: configuration of the application
    """ 
    # Load configuration
    import kitero.config
    config = kitero.config.merge(config)

    # Update RPC client config
    from kitero.web.rpc import RPCClient
    RPCClient.config = config['helper']

    from kitero.web import app
    config = config['web']
    app.run(host=config['listen'],
            port=config['port'],
            debug=config['debug'])

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
    if len(sys.argv[1:]):
        import yaml
        run(yaml.safe_load(file(sys.argv[1])))
    else:
        run()
