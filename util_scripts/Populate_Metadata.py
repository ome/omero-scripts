# coding=utf-8
'''
-----------------------------------------------------------------------------
  Copyright (C) 2014 Glencoe Software, Inc. All rights reserved.


  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.
  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License along
  with this program; if not, write to the Free Software Foundation, Inc.,
  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

------------------------------------------------------------------------------

Populate metadata from CSV.
'''

import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rstring
import omero.scripts as scripts
from omero.model import PlateI

import sys

from omero.util.populate_roi import DownloadingOriginalFileProvider
from omero.util.populate_metadata import ParsingContext


def get_original_file(conn, plateId, fileId):
    plate = conn.getObject("Plate", int(plateId))
    if plate is None:
        sys.stderr.write("Error: Object does not exist.\n")
        sys.exit(1)
    file = None
    for ann in plate.listAnnotations():
        if isinstance(ann, omero.gateway.FileAnnotationWrapper):
            print "File ID:", ann.getFile().getId(), ann.getFile().getName(),\
                "Size:", ann.getFile().getSize()
            if (ann.getFile().getId() == int(fileId)):
                file = ann.getFile()._obj
    if file is None:
        sys.stderr.write("Error: File does not exist.\n")
        sys.exit(1)
    return file


def populateMetadata(client, conn, scriptParams):
    plateId = long(scriptParams["IDs"])
    fileId = long(scriptParams["File_ID"])
    original_file = get_original_file(conn, plateId, fileId)
    provider = DownloadingOriginalFileProvider(conn)
    fileHandle = provider.get_original_file_data(original_file)
    plate = PlateI(long(plateId), False)
    ctx = ParsingContext(client, plate, "")
    ctx.parse_from_handle(fileHandle)
    ctx.write_to_omero()


if __name__ == "__main__":
    dataTypes = [rstring('Plate')]
    client = scripts.client(
        'Poulate_Metadata.py',
        """
        """,
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images (only Plate supported)",
            values=dataTypes, default="Plate"),

        scripts.String(
            "IDs", optional=False, grouping="2",
            description="List of Image IDs to process."),

        scripts.String(
            "File_ID", optional=False, grouping="3", default='',
            description="File ID containing metadata to populate."),

        version="0.1",
        authors=["Emil Rozbicki"],
        institutions=["Glencoe Software Inc."],
        contact="emil@glencoesoftware.com",
    )

    try:
        # process the list of args above.
        scriptParams = {}
        for key in client.getInputKeys():
            if client.getInput(key):
                scriptParams[key] = client.getInput(key, unwrap=True)
        print scriptParams

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        message = populateMetadata(client, conn, scriptParams)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()
