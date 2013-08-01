#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) <year> Open Microscopy Environment.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Describe your script here
"""

import omero
import omero.util.script_utils as scriptUtil

from omero.gateway import BlitzGateway
from omero.rtypes import *

import omero.scripts as scripts
from cStringIO import StringIO
from numpy import *

try:
    from PIL import Image
except ImportError:
    import Image

if __name__ == "__main__":

    dataTypes = [rstring('Image')]

    client = scripts.client('Example.py', """This script ...""","

    scripts.String("Data_Type", optional=False, grouping="1",
        description="Choose source of images (only Image supported)", values=dataTypes, default="Image"),

    scripts.List("IDs", optional=False, grouping="2",
        description="List of Image IDs to process.").ofType(rlong(0)),

    version = "0.1",
    authors = ["Author 1", "Author 2"],
    institutions = ["The OME Consortium"],
    contact = "ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        # Do work here including calling functions
        # defined above.

        client.setOutput("Message", rstring("Success"))

    finally:
        client.closeSession()
