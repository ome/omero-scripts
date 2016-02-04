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
from omero.model import PlateI, ScreenI

import sys

from omero.util.populate_roi import DownloadingOriginalFileProvider
from omero.util.populate_metadata import ParsingContext


def get_original_file(conn, object_type, object_id, file_id):
    if object_type == "Plate":
        omero_object = conn.getObject("Plate", int(object_id))
        if omero_object is None:
            sys.stderr.write("Error: Plate does not exist.\n")
            sys.exit(1)
    else:
        omero_object = conn.getObject("Screen", int(object_id))
        if omero_object is None:
            sys.stderr.write("Error: Screen does not exist.\n")
            sys.exit(1)
    file = None
    for ann in omero_object.listAnnotations():
        if isinstance(ann, omero.gateway.FileAnnotationWrapper):
            print "File ID:", ann.getFile().getId(), ann.getFile().getName(),\
                "Size:", ann.getFile().getSize()
            if (ann.getFile().getId() == int(file_id)):
                file = ann.getFile()._obj
    if file is None:
        sys.stderr.write("Error: File does not exist.\n")
        sys.exit(1)
    return file


def populate_metadata(client, conn, script_params):
    object_id = long(script_params["IDs"])
    file_id = long(script_params["File_ID"])
    original_file = get_original_file(
        conn, script_params["Data_Type"], object_id, file_id)
    provider = DownloadingOriginalFileProvider(conn)
    file_handle = provider.get_original_file_data(original_file)
    if script_params["Data_Type"] == "Plate":
        omero_object = PlateI(long(object_id), False)
    else:
        omero_object = ScreenI(long(object_id), False)
    ctx = ParsingContext(client, omero_object, "")
    ctx.parse_from_handle(file_handle)
    ctx.write_to_omero()


if __name__ == "__main__":
    dataTypes = [rstring('Plate'), rstring('Screen')]
    client = scripts.client(
        'Populate_Metadata.py',
        """
        Attach a file in csv (comma separated values) format to a Screen or Plate.
        Use a 'Well' column to specify wells via 'A1' etc.
        Other columns contain values for each well. For example:

        Well, Reagent, Volume
        A1,   DMSO, 10 ul
        A2,   Drug, 5 ul

        Then select the Screen or Plate and run this script.
        """,
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=dataTypes, default="Plate"),

        scripts.String(
            "IDs", optional=False, grouping="2",
            description="List of Image IDs to process."),

        scripts.String(
            "File_ID", optional=False, grouping="3", default='',
            description="File ID containing metadata to populate."),

        version="0.2",
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
        message = populate_metadata(client, conn, scriptParams)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()
