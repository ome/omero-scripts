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
from omero.rtypes import rstring, rlong
import omero.scripts as scripts
from omero.model import PlateI, ScreenI

import sys

from omero.util.populate_roi import DownloadingOriginalFileProvider
from omero.util.populate_metadata import ParsingContext


def get_original_file(conn, object_type, object_id, file_ann_id=None):
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
    file_ann = None

    for ann in omero_object.listAnnotations():
        if isinstance(ann, omero.gateway.FileAnnotationWrapper):
            file_name = ann.getFile().getName()
            # Pick file by Ann ID (or name if ID is None)
            if (file_ann_id is None and file_name.endswith(".csv")) or (
                    ann.getId() == file_ann_id):
                file_ann = ann
    if file_ann is None:
        sys.stderr.write("Error: File does not exist.\n")
        sys.exit(1)

    return file_ann.getFile()._obj


def populate_metadata(client, conn, script_params):
    object_ids = script_params["IDs"]
    object_id = object_ids[0]
    file_ann_id = None
    if "File_Annotation" in script_params:
        file_ann_id = int(script_params["File_Annotation"])
    data_type = script_params["Data_Type"]
    original_file = get_original_file(
        conn, data_type, object_id, file_ann_id)
    provider = DownloadingOriginalFileProvider(conn)
    file_handle = provider.get_original_file_data(original_file)
    if data_type == "Plate":
        omero_object = PlateI(int(object_id), False)
    else:
        omero_object = ScreenI(int(object_id), False)
    ctx = ParsingContext(client, omero_object, "")
    ctx.parse_from_handle(file_handle)
    ctx.write_to_omero()
    return "Table data populated for %s: %s" % (data_type, object_id)


def run_script():

    data_types = [rstring('Plate'), rstring('Screen')]
    client = scripts.client(
        'Populate_Metadata.py',
        """
    This script processes a csv file, attached to a Screen or Plate,
    converting it to an OMERO.table, with one row per Well.
    The table data can then be displayed in the OMERO clients.
    For full details, see
    http://help.openmicroscopy.org/scripts.html#metadata
        """,
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=data_types, default="Plate"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="Plate or Screen ID.").ofType(rlong(0)),

        scripts.String(
            "File_Annotation", grouping="3",
            description="File ID containing metadata to populate."),

        authors=["Emil Rozbicki", "OME Team"],
        institutions=["Glencoe Software Inc."],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        # process the list of args above.
        script_params = {}
        for key in client.getInputKeys():
            if client.getInput(key):
                script_params[key] = client.getInput(key, unwrap=True)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        message = populate_metadata(client, conn, script_params)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
