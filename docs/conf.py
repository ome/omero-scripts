# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from sphinx.util import logging
logger = logging.getLogger(__name__)


# To fix 'docs/contents.rst not found' errors we need this, see
# https://github.com/readthedocs/readthedocs.org/issues/2569

master_doc = 'index'


# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
def get_scripts(directory):
    """
    Find all the scripts available
    """
    scripts = []

    # Walk the tree.
    for root, directories, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".py") and "_init_" not in filename:
                scripts.append(filename.replace('\n', '').replace(".py", ""))

    return scripts


def find_scripts_entry():
    """
    Find the entries corresponding to the scripts.
    """

    with open("scripts.rst") as file:
        lines = file.readlines()

    entries = []
    for line in lines:
        if "automodule" in line:
            values = line.split(".. automodule::")
            entries.append(values[1].replace('\n', '').strip())
    return entries


def compare(list1, list2):
    """
    Return the elements not common to both lists
    """
    return [i for i in list1 + list2 if i not in list1 or i not in list2]


# List of directories to scan and add the path.
directories = ['../omero/analysis_scripts', '../omero/export_scripts',
               '../omero/figure_scripts', '../omero/import_scripts',
               '../omero/util_scripts']
scripts = []
for d in directories:
    sys.path.insert(0, d)
    scripts.extend(get_scripts(d))

entries = find_scripts_entry()

# Indicate the scripts not listed for documentation
if len(entries) < len(scripts):
    common = compare(scripts, entries)
    logger.warning("automodule entries missing for:\n" + '\n'.join(common))


# -- Project information -----------------------------------------------------

project = u'omero scripts'
copyright = u'2021, Open Microscopy Environment'
author = u'Open Microscopy Environment'

# The full version, including alpha/beta/rc tags
# The short X.Y version.
version = '5.6.0'
release = version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [u'_build', 'Thumbs.db', '.DS_Store']

# Build docs without external dependencies
autodoc_mock_imports = ['numpy', 'omero-py', 'omero', "PIL"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'default'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'OMEROScripts.tex', u'OMERO Scripts Documentation',
     author, 'manual'),
]


# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'omeroscripts', u'OMERO Scripts Documentation',
     [author], 1)
]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'OMEROScripts', u'OMERO Script Documentation',
     author, 'OMEROScripts', 'One line description of project.',
     'Miscellaneous'),
]


# -- Options for Epub output -------------------------------------------------

# Bibliographic Dublin Core info.
epub_title = project

# The unique identifier of the text. This can be a ISBN number
# or the project homepage.
#
# epub_identifier = ''

# A unique identification for the text.
#
# epub_uid = ''

# A list of files that should not be packed into the epub file.
epub_exclude_files = ['search.html']
