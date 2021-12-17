Omero Bulk Annotation Tools
==================================

Content
-------
This repository provides five scripts:
* `01-KeyVal_from_Description.py`: Parses a Dataset/Project/Screen description and converts
  key:value pairs into map annotations in the same container.
* `01-KeyVal_to_csv.py`: Converts a dataset map annotation into a table with one
  record for every image in the dataset. Columns are named according to map
annotation keys. The first column contains the image filename (or id???)
* `03-KeyVal_from_csv.py`: Parses a given csv table attachment and converts each
  record into a map annotation for the image identified via the entry in the
first column (filename or image id).
* `04-Remove_KeyVal.py`: Removes all map annotations from a dataset and all
  contained images.
* `05-KeyVal_from_Filename.py`: Creates image map annotation by tokenizing the
  filename.

Installation
---------------
The scripts must be placed in the `OMERODIR/lib/scripts/omero` directory of your
omero installation, preferrentially in a seperatate subdirectory, e.g. `Bulk
Annotation/`. `OMERODIR`
refers to the root directory of you omero server. If you followed the
installation procedures, you should have the `$OMERODIR` environment variable set.
Logged in omero admins can also use the "Upload scripts" button in the *Gears*
menu.

After installation, the scripts will be accessible in omero web by clicking the *Gears*
icon in the  menu bar.

**NOTE**: The original readme of this repository moved [here](readme.orig.md).


Tutorial
----------
A short tutorial on its usage in combination with the [omero.forms](https://pypi.org/project/omero-forms) plugin was posted [here](https://mpievolbio-scicomp.pages.gwdg.de/blog/post/2020-09-03_omerobulkannotation/) .

