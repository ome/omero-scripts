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

HIERARCHY_OBJECTS = {
                        "Project": ["Dataset", "Image"],
                        "Dataset": ["Image"],
                        "Screen": ["Plate", "Well", "Image"],
                        "Plate": ["Well", "Image"],
                        #"Run": ["Well", "Image"],
                        "Well": ["Image"]
                    }

def remove_map_annotations(conn, obj, namespace):
    anns = list(obj.listAnnotations(ns=namespace))
    mapann_ids = [ann.id for ann in anns
                  if isinstance(ann, omero.gateway.MapAnnotationWrapper)]
    if len(mapann_ids) == 0:
        return 1

    print("Map Annotation IDs to delete:", mapann_ids)
    try:
        conn.deleteObjects("Annotation", mapann_ids)
        return 1
    except Exception:
        print("Failed to delete links")
        return 0


def get_children_recursive(source_object, target_type):
    if HIERARCHY_OBJECTS[source_object.OMERO_CLASS][0] == target_type: # Stop condition, we return the source_obj children
        return source_object.listChildren()
    else:
        result = []
        for child_obj in source_object.listChildren():
            # Going down in the Hierarchy list for all childs that aren't yet the target
            result.extend(get_children_recursive(child_obj, target_type))
        return result

def remove_keyvalue(conn, script_params):
    """
    File the list of objects
    @param conn:             Blitz Gateway connection wrapper
    @param script_params:     A map of the input parameters
    """
    source_type = script_params["Source_object_type"]
    target_type = script_params["Target_object_type"]
    source_ids = script_params["Source_IDs"]
    namespace = script_params["Namespace (leave blank for default)"]

    nsuccess = 0
    ntotal = 0
    if source_type == target_type: # We remove annotation to the given objects ID
        for source_object in conn.getObjects(source_type, source_ids):
            print("Processing object:", source_object)
            ret = remove_map_annotations(conn, source_object, namespace)
            nsuccess += ret
            ntotal += 1
    else:
        for source_object in conn.getObjects(source_type, source_ids):
            # Listing all target children to the source object (eg all images (target) in all datasets of the project (source))
            target_obj_l = get_children_recursive(source_object, target_type)
            for target_obj in target_obj_l:
                print("Processing object:", target_obj)
                ret = remove_map_annotations(conn, target_obj, namespace)
                nsuccess += ret
                ntotal += 1

    message = f"Key value data deleted from {ntotal-nsuccess} of {ntotal} objects"

    return message


if __name__ == "__main__":
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    data_types = [rstring("Project"), rstring("Dataset"),
                  rstring("Screen"), rstring("Plate"),
                  rstring("Well"), rstring("Image")]

    agreement = "I understand what I am doing and that this will result in a batch deletion of key-value pairs from the server"

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
            "Source_object_type", optional=False, grouping="1",
            description="Choose the object type containing the objects to delete annotation from",
            values=data_types, default="Image"),

        scripts.List(
            "Source_IDs", optional=False, grouping="1.1",
            description="List of source IDs").ofType(rlong(0)),

        scripts.String(
            "Target_object_type", optional=True, grouping="1.2",
            description="Choose the object type to delete annotation from (if empty, same as source)",
            values=[rstring("")]+data_types, default=""),

        scripts.String(
            "Namespace (leave blank for default)", optional=True, grouping="2",
            description="Choose a namespace for the annotations"),

        scripts.Bool(
            agreement, optional=False, grouping="3",
            description="Make sure that you understood what this script does"),

        authors=["Christian Evenhuis", "MIF", "Tom Boissonnet"],
        institutions=["University of Technology Sydney", "CAi HHU"],
        contact="https://forum.image.sc/tag/omero",
        version="2.0.0"
    )

    try:
        script_params = {
            "Namespace (leave blank for default)": omero.constants.metadata.NSCLIENTMAPANNOTATION
        }
        for key in client.getInputKeys():
            if client.getInput(key):
                # unwrap rtypes to String, Integer etc
                script_params[key] = client.getInput(key, unwrap=True)
        if script_params["Target_object_type"] == "":
            script_params["Target_object_type"] = script_params["Source_object_type"]

        assert script_params[agreement], "Please confirm that you understood the risks."

        print(script_params)   # handy to have inputs in the std-out log

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        # do the editing...
        message = remove_keyvalue(conn, script_params)
        client.setOutput("Message", rstring(message))
    except AssertionError as err: #Display assertion errors in OMERO.web activities
        client.setOutput("ERROR", rstring(err))
        raise AssertionError(str(err))
    finally:
        client.closeSession()
