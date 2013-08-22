OMERO User Scripts
==================

OMERO.py scripts which use the OMERO.scripts API

Requirements
============

* OMERO 4.4.x

Installation
============

1. Fork omero-user-scripts in your own github account

2. Change into the scripts location of your OMERO installation

        cd OMERO_DIST/lib/scripts

3. Clone the repository

        git clone git@github.com:YOURNAMEHERE/omero-user-scripts.git YOURNAMEHERE

3. Pick a suitable sub-directory:

    | Directory          | Scripts which ...                                                                    |
    | ---------          | -----------------                                                                    |
    | *analysis_scripts* | crunch images to produce numerical results and similar tasks                         |
    | *export_scripts*   | take one or more images as an input, and produce a representation for exchange       |
    | *figure_scripts*   | take one or more images as an input, and produce some form of summary representation |
    | *import_scripts*   | are run on images after they've been imported into OMERO for some extra processing   |
    | *setup_scripts*    | are executed once, often by administrators, to configure OMERO itself                |
    | *util_scripts*     | are periodically run to clean up or otherwise improve existing data or OMERO itself  |

4. Move the [example script](Example.py) to that directory with a valid name

        cd YOURNAMEHERE
        git mv Example.py util_scripts/daily_cleanup.py

5. List the current scripts in the system

        path/to/bin/omero script list

Legal
=====

See [LICENSE](LICENSE)


# About #
This section provides machine-readable information about your scripts.
It will be used to help generate a landing page and links for your work.
Please modify *all* values on *each* branch to describe your scripts.

###### Repository name ######
Base OMERO User Scripts repository

###### Minimum version ######
4.4

###### Maximum version ######
4.4

###### Owner(s) ######
The OME Team

###### Institution ######
Open Microscopy Environment

###### URL ######
https://www.openmicroscopy.org/site/community/script-sharing

###### Email ######
ome-devel@lists.openmicroscopy.org.uk

###### Description ######
Example script repository to be cloned, modified, and extended.
This text may be used on OME resources to explain your scripts.
