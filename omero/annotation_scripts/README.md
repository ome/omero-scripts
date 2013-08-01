OMERO User Scripts
==================

OMERO.py scripts which use the OMERO.scripts API

Requirements
============

* OMERO 4.4.x

Installation
============

1. Fork omero-user-scripts in your own github account

2. Change into your the scripts location of your OMERO installation

        cd OMERO_DIST/lib/scripts

3. Clone the repository

        git clone git@github.com:YOURNAMEHERE/omero-user-scripts.git YOURNAMEHERE

4. Move the example script to the proper sub-directory with a valid name

        cd YOURNAMEHERE
        git mv Example.py util_scripts/daily_cleanup.py

5. List the current scripts in the system

        path/to/bin/omero script list

Legal
=====

See LICENSE

