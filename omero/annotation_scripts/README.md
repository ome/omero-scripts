ometa: contributed scripts for metadata handling in omero-web
============================================================================

Summary
--------
This is the central repository for community contributed scripts to [omero-web]() to support metadata handling and bulk annotation with *key-value* pairs.
These scripts, in combination with the [omero.forms](https://pypi.org/project/omero-forms),
support the bulk annotation workflow described in [this blog post](https://mpievolbio-scicomp.pages.gwdg.de/blog/post/2020-09-03_omerobulkannotation/).

For the new scripts version of 2024, you can follow this guide:
https://guide-kvpairs-scripts.readthedocs.io/en/latest/walkthrough.html


Content
-------
This repository provides four scripts:
* `Import_from_csv.py`: Read a csv file and converts each row into a map annotation
for the identified object (image, dataset, project, run, well, plate, screen).
* `Export_to_csv.py`: Exports the map annotations of objects into a csv file.
* `Remove_KeyVal.py`: Removes the key-value pairs of an object associated with
a given namespace.
* `Convert_KeyVal_namespace.py`: Converts the namespace of map annotations.

Installation
---------------
The scripts must be placed in the `OMERODIR/lib/scripts/omero` directory of your
omero installation, preferrentially in a seperatate subdirectory, e.g. `Bulk
Annotation/`.

Follow [these instruction](https://omero.readthedocs.io/en/stable/developers/scripts/index.html#downloading-and-installing-scripts) to install/update the scripts,

You should also configure the Export_to_csv script so that it returns the csv file as a direct download link:
https://guide-kvpairs-scripts.readthedocs.io/en/latest/setup.html#configuring-the-export-script

History
--------
This repository started as a fork of [evehuis/omero-user-scripts](). Ownership was transferred to @CFGrote after merging a pull request that fixed a number of bugs and
ported the original code from python2.7 to python3.x

In 2023, the scripts were reworked by Tom Boissonnet and Jens Wendt to extend the annotation to all OMERO objects, and to include a new script to convert namespaces of map annotations.


Contributions
----------------
Contributions are welcome: Bugfixes, enhancements, additional scripts, tests etc should be submitted as pull requests. We also encourage you to post suggestions or bug reports in our github issues.
