OMERO Core Scripts
==================

This directory contains OmeroPy scripts which use the
OmeroScripts API. All scripts ("*.py") present in the
directory will be automatically distributed with all binary
builds.

Categories
----------

Scripts are separated into several categories, one per directory.

| In the directory       | are scripts which ...                                                                |
| ----------------       | ---------------------                                                                |
| **analysis_scripts**   | crunch images to produce numerical results and similar tasks                         |
| **export_scripts**     | take one or more images as an input, and produce a representation for exchange       |
| **figure_scripts**     | take one or more images as an input, and produce some form of summary representation |
| **hcs_scripts**        | work with screens/plates/wells rather than just images                               |
| **import_scripts**     | are run on images after they've been imported into OMERO for some extra processing   |
| **processing_scripts** | create new images from existing images or other data                                 |
| **setup_scripts**      | are executed once, often by administrators, to configure OMERO itself                |
| **util_scripts**       | are periodically run to clean up or otherwise improve existing data or OMERO itself  |


Scripts which would like to rely on other scripts can
use:

    import omero.<sub_dir>.<script_name>

For this to work, the official script in question must
be properly importable, i.e.:

    def run():
        client = omero.scripts.client(...)

    if __name__ == "__main__":
        run()


OMERO User Scripts
------------------

If you would like to provide your own scripts for others to install
into their OMERO installations, please see http://openmicroscopy.org/info/scripts
