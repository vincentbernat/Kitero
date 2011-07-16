import json
import time
from functools import wraps
from flask import request, Response, render_template

def jsonify(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        result = f(*args, **kwargs)
        result = { 'status': 0,
                   'time': time.strftime("%Y-%m-%dT%H:%M:%S%z"),
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
