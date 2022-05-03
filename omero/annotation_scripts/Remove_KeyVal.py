#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 MIF/Key_Value_remove.py"

 Remove all key-value  pairs from:
   * selected image(s)
   * selected dataset(s) and the images contained in them
   * selected screens(s) and the wells & images contained in them

-----------------------------------------------------------------------------
  Copyright (C) 2018 - 2022
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
Created by Christian Evenhuis

"""

from omero.gateway import BlitzGateway
import omero
from omero.rtypes import rlong, rstring, wrap
import omero.scripts as scripts


def remove_map_annotations(conn, obj):
    anns = list(obj.listAnnotations())
    mapann_ids = [ann.id for ann in anns
                  if isinstance(ann, omero.gateway.MapAnnotationWrapper)]
    if len(mapann_ids) == 0:
        return 0

    print("Map Annotation IDs to delete:", mapann_ids)
    try:
        conn.deleteObjects("Annotation", mapann_ids)
        return 0
    except Exception:
        print("Failed to delete links")
        return 1
    return


def get_objects(conn, script_params):
    """
    File the list of objects
    @param conn:             Blitz Gateway connection wrapper
    @param script_params:     A map of the input parameters
    """
    # we know script_params will have "Data_Type" and "IDs" since these
    # parameters are not optional
    data_type = script_params["Data_Type"]
    ids = script_params["IDs"]

    # data_type is 'Dataset', 'Plate' or 'Image' so we can use it directly in
    objs = list(conn.getObjects(data_type, ids))

    if len(objs) == 0:
        print("No {} found for specified IDs".format(data_type))
        return

    objs_ret = []

    if data_type == 'Dataset':
        for ds in objs:
            print("Processing Images from Dataset: {}".format(ds.getName()))
            objs_ret.append(ds)
            imgs = list(ds.listChildren())
            objs_ret.extend(imgs)
    elif data_type == "Plate":
        for plate in objs:
            print("Processing Wells and Images from Plate:", plate.getName())
            objs_ret.append(plate)
            for well in plate.listChildren():
                objs_ret.append(well)
                for ws in well.listChildren():
                    img = ws.getImage()
                    objs_ret.append(img)
    else:
        print("Processing Images identified by ID")
        objs_ret = objs

    return objs_ret


if __name__ == "__main__":
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    data_types = wrap(['Dataset', 'Plate', 'Image'])

    # Here we define the script name and description.
    # Good practice to put url here to give users more guidance on how to run
    # your script.
    client = scripts.client(
        'Remove_Key_Value.py',
        ("Remove key-value pairs from"
         " Image IDs or by the Dataset IDs.\nSee"
         " http://www.openmicroscopy.org/site/support/omero5.2/developers/"
         "scripts/user-guide.html for the tutorial that uses this script."),

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        authors=["Christian Evenhuis", "MIF"],
        institutions=["University of Technology Sydney"],
        contact="https://forum.image.sc/tag/omero"
    )

    try:
        script_params = {}
        for key in client.getInputKeys():
            if client.getInput(key):
                # unwrap rtypes to String, Integer etc
                script_params[key] = client.getInput(key, unwrap=True)

        print(script_params)   # handy to have inputs in the std-out log

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        # do the editing...
        objs = get_objects(conn, script_params)

        nfailed = 0
        for obj in objs:
            print("Processing object:", obj)
            ret = remove_map_annotations(conn, obj)
            nfailed = nfailed + ret

        # now handle the result, displaying message and returning image if
        # appropriate
        nobjs = len(objs)
        message = "Key value data deleted from  {} of {} objects".format(
                nobjs-nfailed, nobjs)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()
