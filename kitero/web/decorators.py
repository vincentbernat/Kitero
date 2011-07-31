import json
import time
from functools import wraps
from flask import request, Response, render_template

def jsonify(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        result = f(*args, **kwargs)
        result = { 'status': 0,
                   'time': time.time(),
                   'value': result }
        return Response("%s\n" % json.dumps(result,
                                            indent=None if request.is_xhr else 2),
                        mimetype='application/json')
    return decorated_function

def templated(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        template_name = request.endpoint \
            .replace('.', '/') + '.html'
        ctx = f(*args, **kwargs)
        return render_template(template_name, **ctx)
    return decorated_function

def cache(timeout=5):
    def decorate(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            now = time.time()
            if f._cache is None:
                value, last = f(*args, **kwargs), now
            else:
                value, last = f._cache
                if now - last > timeout:
                    value, last = f(*args, **kwargs), now
            f._cache = (value, last)
            return value
        f._cache = None
        return decorated_function
    return decorate
