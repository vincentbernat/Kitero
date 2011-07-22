# -*- coding: utf-8 -*-

import sys, os
sys.path.insert(0, os.path.abspath('..'))

project = u'Kitérő'
copyright = u'2011, Vincent Bernat'
version = '0.1'
release = '0.1'

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode']

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
exclude_patterns = ['_build', 'lab']
pygments_style = 'sphinx'

html_theme = 'nature'
html_logo = "kitero.png"
html_favicon = "favicon.ico"
html_static_path = ['_static']
htmlhelp_basename = 'kiterodoc'
