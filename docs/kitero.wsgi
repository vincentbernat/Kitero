# -*- python -*-
#
# Example of WSGI file with virtualenv enabled.

activate_this = '/srv/kitero/virtualenv/prod/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

import yaml
from kitero.web import app
from kitero.web.serve import configure

configure(app, yaml.safe_load(file("/srv/kitero/conf/prod.yaml")))
application = app
