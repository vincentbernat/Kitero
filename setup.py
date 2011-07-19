import os

# Some ugly hack to force the use of buffered output when running tests
import StringIO
StringIO._complain_ifclosed = lambda x: x
from setuptools.command.test import test
def run_tests(self):
    try:
        import unittest2 as unittest
    except ImportError:
        import unittest
    unittest.main(
        None, None, [unittest.__file__]+self.test_args,
        testLoader=unittest.loader.defaultTestLoader,
        buffer = True
    )

test.run_tests = run_tests

from setuptools import setup, find_packages
setup(
    name = "kitero",
    version = "0.1",
    author = "Vincent Bernat",
    author_email = "bernat@luffy.cx",
    description = "Interface and QoS switcher for router",

    # List of provided packages
    packages = find_packages(exclude=("tests",)),
    package_data = {
        '': [ 'README' ],
        'kitero.web': [ 'templates/*.html',
                        'static/css/*.css', 'static/js/*.js',
                        'static/images/*.jpg', 'static/images/*.png' ],
        },

    # We provide two services
    entry_points = {
        'console_scripts': [
            'kitero-helper = kitero.helper.service:Service.run',
            'kitero-web = kitero.web.serve:_run',
            ]
        },

    # Dependencies
    install_requires = [ x.strip()
                         for x in file("requirements.txt").readlines()
                         if x.strip() ],

    # Tests
    test_suite = 'unittest2.collector',
    )
