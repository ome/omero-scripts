ometa: contributed scripts for metadata handling in omero-web
============================================================================

Summary
--------
This is the central repository for community contributed scripts to [omero-web]() to support metadata handling and bulk annotation with *key-value* pairs.
These scripts, in combination with the [omero.forms](https://pypi.org/project/omero-forms),
support the bulk annotation workflow described in [this blog post](https://mpievolbio-scicomp.pages.gwdg.de/blog/post/2020-09-03_omerobulkannotation/).


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
Annotation/`. 

`OMERODIR`
refers to the root directory of you omero server. If you followed the
installation procedures, you should have the `$OMERODIR` environment variable set.
Logged in omero admins can also use the "Upload scripts" button in the *Gears*
menu.

After installation, the scripts will be accessible in omero web by clicking the *Gears*
icon in the  menu bar.

History
--------
This repository started as a fork of [evehuis/omero-user-scripts](). Ownership was transferred to @CFGrote after merging a pull request that fixed a number of bugs and
ported the original code from python2.7 to python3.x


Contributions
----------------
Contributions are welcome: Bugfixes, enhancements, additional scripts, tests etc should be submitted as pull requests. We also encourage you to post suggestions or bug reports in our github issues.
