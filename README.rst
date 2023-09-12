.. image:: https://github.com/ome/omero-scripts/workflows/OMERO/badge.svg
    :target: https://github.com/ome/omero-scripts/actions

.. image:: https://readthedocs.org/projects/omero-scripts/badge/?version=stable
    :target: https://readthedocs.org/projects/omero-scripts/badge/?version=stable

.. image:: https://badge.fury.io/py/omero-scripts.svg
    :target: https://badge.fury.io/py/omero-scripts

OMERO Core Scripts
==================

This directory contains OMERO scripts which use the
OMERO.scripts API. All scripts (e.g. ``*.py``) present in the
directory will be automatically distributed with all binary
builds. Which file-endings will be detected and how they
will be launched are both configured centrally in the server.
``.py``, ``.jy``, and ``.m`` (MATLAB) files should all be detected
by default starting with OMERO 5.


Categories
==========

Scripts are separated into several categories, one per directory.

+------------------------+-------------------------------------------------------------------------------+
| Directory              | Description                                                                   |
+========================+===============================================================================+                                                    
| **analysis_scripts**   | crunch images to produce numerical results and similar tasks                  |
+------------------------+-------------------------------------------------------------------------------+
| **export_scripts**     | take one or more images as an input, and produce a representation for exchange|
+------------------------+-------------------------------------------------------------------------------+
| **figure_scripts**     | take one or more images as an input, and produce a summary representation     |
+------------------------+-------------------------------------------------------------------------------+
| **import_scripts**     | are run on images after import for extra processing                           |
+------------------------+-------------------------------------------------------------------------------+
| **util_scripts**       | perform other miscellaneous tasks like cleaning up or optimizing OMERO itself |
+------------------------+-------------------------------------------------------------------------------+


Scripts which would like to rely on other scripts can
use::

    import omero.<sub_dir>.<script_name>

For this to work, the official script in question must
be properly importable, i.e.::

    def run():
        client = omero.scripts.client(...)

    if __name__ == "__main__":
        run()


OMERO User Scripts
==================

If you would like to provide your own scripts for others to install
into their OMERO installations, please see https://openmicroscopy.org/info/scripts


Testing
=======

Integration tests under ``test/`` require an OMERO server with scripts installed.
The tests are run by Travis for open PRs using omero-test-infra to deploy OMERO
via Docker containers.

To run tests locally::

	# All tests
	$ python setup.py test

	# Single test in a single file
	$ python setup.py test -t test/integration/test_util_scripts.py -k test_dataset_to_plate

Usage
=====

See https://omero-scripts.readthedocs.io/en/stable/

Release process
===============

This repository uses `bump2version <https://pypi.org/project/bump2version/>`_ to manage version numbers.
To tag a release run::

    $ bumpversion release

This will remove the ``.dev0`` suffix from the current version, commit, and tag the release.

To switch back to a development version run::

    $ bumpversion --no-tag [major|minor|patch]

specifying ``major``, ``minor`` or ``patch`` depending on whether the development branch will be a `major, minor or patch release <https://semver.org/>`_. This will also add the ``.dev0`` suffix.

Remember to ``git push`` all commits and tags.s essential.

The CI pipeline will automatically deploy the tag onto PyPI.


Copyright
=========

2010-2021, The Open Microscopy Environment
