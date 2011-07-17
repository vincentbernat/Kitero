import json
import time
from functools import wraps
from flask import request
from flask import Response

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
