OMERO User Scripts
==================

Installation
------------

1. Change into the scripts location of your OMERO installation

        cd OMERO_DIST/lib/scripts

2. Clone the repository

        git clone https://github.com/THISREPOSITORY/omero-user-scripts.git UNIQUE_NAME

3. Update your list of installed scripts by examining the list of scripts
   in OMERO.insight or OMERO.web or by running

        path/to/bin/omero script list

Developer Installation
----------------------

1. Fork [omero-user-scripts](https://github.com/ome/omero-user-scripts/fork) in your own GitHub account

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

   b. Otherwise, create a suitable sub-directory. Examples of directories in use can be
      found in the [official scripts](https://github.com/ome/scripts) repository.

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
