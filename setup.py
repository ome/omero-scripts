import os

from setuptools import setup


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


version = '5.7.4.dev0'
url = "https://github.com/ome/omero-scripts/"

setup(
    version=version,
    name='omero-scripts',
    packages=[
        'omero.analysis_scripts',
        'omero.annotation_scripts',
        'omero.export_scripts',
        'omero.figure_scripts',
        'omero.import_scripts',
        'omero.util_scripts'],
    description="OMERO scripts",
    long_description=read('README.rst'),
    classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Plugins',
          'Intended Audience :: Developers',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GNU General Public License v2 '
          'or later (GPLv2+)',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3',
          'Topic :: Software Development :: Libraries :: Python Modules'
      ],  # Get strings from
          # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    author='The Open Microscopy Team',
    author_email='ome-devel@lists.openmicroscopy.org.uk',
    license='GPL-2.0+',
    url='%s' % url,
    zip_safe=False,
    download_url='%s' % url,
    python_requires='>=3',
    tests_require=['pytest'],
)
