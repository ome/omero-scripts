MIF developed scripts for OMERO
===========================

This is a collection of python scripts written for 
the [OMERO](https://www.openmicroscopy.org/omero/) installation in the 
[Microbial Imaging Facility](https://www.uts.edu.au/about/faculty-science/microbial-imaging-facility/about-us) (MIF),
which is part of the [ithree institute](https://www.uts.edu.au/research-and-teaching/our-research/ithree-institute)
at the [University of Technology Sydney](ihttps://www.uts.edu.au).

These scripts are primarily for the handling of metadata.  Details and instructions can be found from the links:

* [Add key-values to a dataset](https://code.research.uts.edu.au/MIF/OMERO-instructions/wikis/organising_data/Adding-Global-Key-Values)
* [Extract key-values from filenames](https://code.research.uts.edu.au/MIF/OMERO-instructions/wikis/organising_data/filename/Extracting-Key-Values-from-filenames)
* [Export/Import key-values from .csv](https://code.research.uts.edu.au/MIF/OMERO-instructions/wikis/organising_data/csv/Managing-Key-values-with-csv-files)

The scripts were developed using the following resources:

* [Script sharing site](https://www-legacy.openmicroscopy.org/site/community/scripts)
* [Scripting documentation](https://docs.openmicroscopy.org/omero/5.3.3/developers/scripts/style-guide.html)

# Installing OMERO CLI for 5.4.1

## 1. Create a virtual env for python 2.7:

```
conda create -n OMERO_CLI python=2.7 anaconda
```

## 2. Download the package from: 
Get the "OMERO python" package download 

* [https://www.openmicroscopy.org/omero/downloads/](https://www.openmicroscopy.org/omero/downloads/)

or directly from this [link](http://downloads.openmicroscopy.org/omero/5.4.1/artifacts/OMERO.py-5.4.1-ice36-b75.zip).	
## 3. Install the ICE library

```
pip install zeroc-ice==3.6.4
```

## 4. Add conda paths

Add the path to the library. Instructions from [conda webpage](https://conda.io/docs/user-guide/tasks/manage-environments.html#saving-environment-variables)

```
cd /Users/evenhuis/anaconda3/envs/OMERO_5.4_CLI
mkdir -p ./etc/conda/activate.d
mkdir -p ./etc/conda/deactivate.d
touch ./etc/conda/activate.d/env_vars.sh
touch ./etc/conda/deactivate.d/env_vars.sh
```

Add the following to the activate.d/env_vars.sh:


```	
#!/bin/sh

export OMERO_PREFIX=~/Dropbox/MIF/OMERO/downloads_5.4.1/OMERO.py-5.4.1-ice36-b75

export ORIGPATH=$PATH
export ORIGPYTHONPATH=$PYTHONPATH
export PATH=$PATH:$OMERO_PREFIX/lib/python:$OMERO_PREFIX/bin
export PYTHONPATH=$PYTHONPATH:$OMERO_PREFIX/lib/python:$OMERO_PREFIX/bin
```

This appends the OMERO library to the search path.  And the following in deactivate.d/env_vars.sh restores the path variabeles

```
export PATH=$ORIGPATH
export PYTHONPATH=$ORIGPYTHONPATH

unset ORIGPATH
unset ORIGPYTHONPATH
```


# Run downloads

1. Example
```bash
OMERO_USERNAME='USERNAME' OMERO_USER_PASSWORD='PASSWORD' OMERO_APP_URL='omero-app.server.edu' python download_files.py -h
```
Result:
```bash
usage: download_files.py [-h] [-p PROJECT [PROJECT ...]]
                         [-d DATASET [DATASET ...]] [-g [GROUP]] [-o] [-t]

Download datasets and projects from OMERO

optional arguments:
  -h, --help            show this help message and exit
  -p PROJECT [PROJECT ...], --project PROJECT [PROJECT ...]
                        IDs of projects to download
  -d DATASET [DATASET ...], --dataset DATASET [DATASET ...]
                        IDs of datasets to download
  -g [GROUP], --group [GROUP]
                        name of group
  -o, --orig            download originals
  -t, --tif             download OME-TIFs

```

2. Example
```bash
OMERO_USERNAME='USERNAME' OMERO_USER_PASSWORD='PASSWORD' OMERO_APP_URL='omero-app.server.edu' python download_files.py -d 2071 -p 759 -o
```
```bash

omero-app.research.uts.edu.au
Current user:
   ID: 2
   Username: 135553
   Full Name: Moises Sacal Bonequi
['2071']
moises-dataset/
              /gravatar.jpeg
['759']
moises-dataset/
              /gravatar.jpeg

```

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
5.4

###### Owner(s) ######
Christian Evenhuis

###### Institution ######
Microbial Imaging Facility
University of Technology Sydeny

###### URL ######
https://www.uts.edu.au/about/faculty-science/microbial-imaging-facility/about-us

###### Email ######
christian.evenhuis@gmail.com

###### Description ######
Example script repository to be cloned, modified, and extended.
This text may be used on OME resources to explain your scripts.

