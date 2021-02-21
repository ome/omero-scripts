.. image:: https://github.com/ome/omero-scripts/workflows/OMERO/badge.svg
    :target: https://github.com/ome/omero-scripts/actions

.. image:: https://github.com/ome/omero-scripts/workflows/sphinx/badge.svg
    :target: https://github.com/ome/omero-scripts/actions

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

Copyright
=========

2010-2021, The Open Microscopy Environment
