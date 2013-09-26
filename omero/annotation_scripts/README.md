OMERO User Scripts
==================

Installation
------------

1. Fork [omero-user-scripts](https://github.com/ome/omero-user-scripts/fork) in your own github account

2. Change into the scripts location of your OMERO installation

        cd OMERO_DIST/lib/scripts

3. Clone the repository

        git clone git@github.com:YOURGITUSER/omero-user-scripts.git YOUR_SCRIPTS

Adding a script
---------------

1. Choose a naming scheme for your scripts. The name of the clone
   (e.g. "YOUR_SCRIPTS"), the script name, and all sub-directories will be shown
   to your users in the UI, so think about script organization upfront.

   a. If you don't plan to have many scripts, then you need not have any sub-directories
      and can place scripts directly under YOUR_SCRIPTS.

   b. Otherwise, create a suitable sub-directory. We encourage one of:

    | Directory              | Scripts which ...                                                                    |
    | ---------              | -----------------                                                                    |
    | **analysis_scripts**   | crunch images to produce numerical results and similar tasks                         |
    | **export_scripts**     | take one or more images as an input, and produce a representation for exchange       |
    | **figure_scripts**     | take one or more images as an input, and produce some form of summary representation |
    | **hcs_scripts**        | work with screens/plates/wells rather than just images
    | **import_scripts**     | are run on images after they've been imported into OMERO for some extra processing   |
    | **processing_scripts** | create new images from existing images or other data                                 |
    | **setup_scripts**      | are executed once, often by administrators, to configure OMERO itself                |
    | **util_scripts**       | are periodically run to clean up or otherwise improve existing data or OMERO itself  |

2. Place your script in the chosen directory:
  * If you have an existing script, simply save it.
  * Otherwise, copy [Example.txt](Example.txt) and edit it in place. (Don't use git mv)

3. Add the file to git, commit, and push.

Testing your script
-------------------

1. List the current scripts in the system

        path/to/bin/omero script list

2. List the parameters

        path/to/bin/omero script params SCRIPT_ID

3. Launch the script

        path/to/bin/omero script launch SCRIPT_ID

4. See the [developer documentation](https://www.openmicroscopy.org/site/support/omero4/developers/scripts/)
   for more information on testing and modifying your scripts.

Legal
-----

See [LICENSE](LICENSE)


# About #
This section provides machine-readable information about your scripts.
It will be used to help generate a landing page and links for your work.
Please modify **all** values on **each** branch to describe your scripts.

###### Repository name ######
Base OMERO User Scripts repository

###### Minimum version ######
4.4

###### Maximum version ######
5.0

###### Owner(s) ######
The OME Team

###### Institution ######
Open Microscopy Environment

###### URL ######
http://openmicroscopy.org/info/scripts

###### Email ######
ome-devel@lists.openmicroscopy.org.uk

###### Description ######
Example script repository to be cloned, modified, and extended.
This text may be used on OME resources to explain your scripts.
