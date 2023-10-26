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

CHILD_OBJECTS = {
                    "Project": "Dataset",
                    "Dataset": "Image",
                    "Screen": "Plate",
                    "Plate": "Well",
                    #"Run": ["Well", "Image"],
                    "Well": "WellSample",
                    "WellSample": "Image"
                }

def remove_map_annotations(conn, obj, namespace_l):
    mapann_ids = []
    for namespace in namespace_l:
        anns = list(obj.listAnnotations(ns=namespace))
        mapann_ids.extend([ann.id for ann in anns
                           if isinstance(ann, omero.gateway.MapAnnotationWrapper)])

    if len(mapann_ids) == 0:
        return 0
    print("Map Annotation IDs to delete:", mapann_ids)
    try:
        conn.deleteObjects("Annotation", mapann_ids)
        return 1
    except Exception:
        print("Failed to delete links")
        return 0


def get_children_recursive(source_object, target_type):
    if CHILD_OBJECTS[source_object.OMERO_CLASS] == target_type: # Stop condition, we return the source_obj children
        if source_object.OMERO_CLASS != "WellSample":
            return source_object.listChildren()
        else:
            return [source_object.getImage()]
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
    source_type = script_params["Data_Type"]
    target_type = script_params["Target Data_Type"]
    source_ids = script_params["IDs"]
    namespace_l = script_params["Namespace (leave blank for default)"]

    nsuccess = 0
    ntotal = 0
    for source_object in conn.getObjects(source_type, source_ids):
        if source_type == target_type:
            target_obj_l = [source_object]
        else:
            # Listing all target children to the source object (eg all images (target) in all datasets of the project (source))
            if source_type == "TagAnnotation":
                target_obj_l = conn.getObjectsByAnnotations(target_type, [source_object.getId()])
                target_obj_l = list(conn.getObjects(target_type, [o.getId() for o in target_obj_l])) # Need that to load annotations later
            else:
                target_obj_l = get_children_recursive(source_object, target_type)
        for target_obj in target_obj_l:
            print("Processing object:", target_obj)
            ret = remove_map_annotations(conn, target_obj, namespace_l)
            nsuccess += ret
            ntotal += 1

    message = f"Key value data deleted from {nsuccess} of {ntotal} objects"

    return message


if __name__ == "__main__":
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    source_types = [rstring("Project"), rstring("Dataset"), rstring("Image"),
                    rstring("Screen"), rstring("Plate"),
                    rstring("Well"), rstring("Tag"),
                    rstring("Image"), # Cannot add fancy layout if we want auto fill and selct of object ID
                    ]

    target_types = [rstring("Project"), # Duplicate Image for UI, but not a problem for script
                    rstring("- Dataset"), rstring("-- Image"),
                    rstring("Screen"), rstring("- Plate"),
                    rstring("-- Well"), rstring("--- Image")]

    agreement = "I understand what I am doing and that this will result in a batch deletion of key-value pairs from the server"

    # Here we define the script name and description.
    # Good practice to put url here to give users more guidance on how to run
    # your script.
    client = scripts.client(
        'Remove_Key_Value.py',
        """
    This script deletes key-value pairs of all child objects founds.
    Only key-value pairs of the namespace are deleted.
    (default namespace correspond to editable KV pairs in web)
    TODO: add hyperlink to readthedocs
    \t
    Parameters:
    \t
    - Data Type: Type of the "parent objects" in which "target objects" are searched.
    - IDs: IDs of the "parent objects".
    - Target Data Type: Type of the "target objects" of which KV-pairs are deleted.
    - Namespace: Only annotations having one of these namespace(s) will be deleted.
    \t
        """,

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Parent data type of the objects to annotate.",
            values=source_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of parent data IDs containing the objects to delete annotation from.").ofType(rlong(0)),

        scripts.String(
            "Target Data_Type", optional=True, grouping="1.2",
            description="Choose the object type to delete annotation from.",
            values=target_types, default="-- Image"),

        scripts.List(
            "Namespace (leave blank for default)", optional=True, grouping="1.3",
            default="NAMESPACE TO DELETE",
            description="Annotation with these namespace will be deleted.").ofType(rstring("")),

        scripts.Bool(
            agreement, optional=False, grouping="2",
            description="Make sure that you understood the scope of what will be deleted."),

        authors=["Christian Evenhuis", "MIF", "Tom Boissonnet"],
        institutions=["University of Technology Sydney", "CAi HHU"],
        contact="https://forum.image.sc/tag/omero",
    )

    try:
        script_params = {
            "Namespace (leave blank for default)": [omero.constants.metadata.NSCLIENTMAPANNOTATION]
        }
        for key in client.getInputKeys():
            if client.getInput(key):
                # unwrap rtypes to String, Integer etc
                script_params[key] = client.getInput(key, unwrap=True)

        assert script_params[agreement], "Please confirm that you understood the risks."

        # Getting rid of the trailing '---' added for the UI
        tmp_trg = script_params["Target Data_Type"]
        script_params["Target Data_Type"] = tmp_trg.split(" ")[1] if " " in tmp_trg else tmp_trg

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
