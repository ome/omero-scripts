import os
import sys

from setuptools import setup
from setuptools.command.test import test as test_command


class PyTest(test_command):
    user_options = [
        ('test-path=', 't', "base dir for test collection"),
        ('test-ice-config=', 'i',
         "use specified 'ice config' file instead of default"),
        ('test-pythonpath=', 'p', "prepend 'pythonpath' to PYTHONPATH"),
        ('test-marker=', 'm', "only run tests including 'marker'"),
        ('test-no-capture', 's', "don't suppress test output"),
        ('test-failfast', 'x', "Exit on first error"),
        ('test-verbose', 'v', "more verbose output"),
        ('test-string=', 'k', "filter tests by string"),
        ('test-quiet', 'q', "less verbose output"),
        ('junitxml=', None, "create junit-xml style report file at 'path'"),
        ('pdb', None, "fallback to pdb on error"),
        ]

    def initialize_options(self):
        test_command.initialize_options(self)
        self.test_pythonpath = None
        self.test_string = None
        self.test_marker = None
        self.test_path = 'test'
        self.test_failfast = False
        self.test_quiet = False
        self.test_verbose = False
        self.test_no_capture = False
        self.junitxml = None
        self.pdb = False
        self.test_ice_config = None

    def finalize_options(self):
        test_command.finalize_options(self)
        self.test_args = [self.test_path]
        if self.test_string is not None:
            self.test_args.extend(['-k', self.test_string])
        if self.test_marker is not None:
            self.test_args.extend(['-m', self.test_marker])
        if self.test_failfast:
            self.test_args.extend(['-x'])
        if self.test_verbose:
            self.test_args.extend(['-v'])
        if self.test_quiet:
            self.test_args.extend(['-q'])
        if self.junitxml is not None:
            self.test_args.extend(['--junitxml', self.junitxml])
        if self.pdb:
            self.test_args.extend(['--pdb'])
        self.test_suite = True
        if 'ICE_CONFIG' not in os.environ:
            os.environ['ICE_CONFIG'] = self.test_ice_config

    def run_tests(self):
        if self.test_pythonpath is not None:
            sys.path.insert(0, self.test_pythonpath)
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


version = '5.6.dev1'
url = "https://github.com/ome/omero-scripts/"

setup(
    version=version,
    name='omero-scripts',
    packages=[
        'omero.analysis_scripts',
        'omero.export_scripts',
        'omero.figure_scripts',
        'omero.import_scripts',
        'omero.util_scripts'],
    description="OMERO scripts",
    long_description="OMERO scripts",
    author='The Open Microscopy Team',
    author_email='ome-devel@lists.openmicroscopy.org.uk',
    license='GPL-2.0+',
    url='%s' % url,
    zip_safe=False,
    download_url='%s' % url,
    cmdclass={'test': PyTest},
    tests_require=['pytest'],
)
