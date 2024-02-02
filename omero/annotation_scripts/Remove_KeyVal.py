#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 MIF/Key_Value_remove.py"

 Remove all key-value pairs associated with a namespace from
 objects on OMERO.

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
from omero.rtypes import rlong, rstring, robject
from omero.constants.metadata import NSCLIENTMAPANNOTATION
import omero.scripts as scripts


CHILD_OBJECTS = {
    "Project": "Dataset",
    "Dataset": "Image",
    "Screen": "Plate",
    "Plate": "Well",
    "Well": "WellSample",
    "WellSample": "Image"
}

ALLOWED_PARAM = {
    "Project": ["Project", "Dataset", "Image"],
    "Dataset": ["Dataset", "Image"],
    "Image": ["Image"],
    "Screen": ["Screen", "Plate", "Well", "Run", "Image"],
    "Plate": ["Plate", "Well", "Run", "Image"],
    "Well": ["Well", "Image"],
    "Run": ["Run", "Image"],
    "Tag": ["Project", "Dataset", "Image",
            "Screen", "Plate", "Well", "Run"]
}

AGREEMENT = ("I understand what I am doing and that this will result " +
             "in a batch deletion of key-value pairs from the server")


def get_children_recursive(source_object, target_type):
    if CHILD_OBJECTS[source_object.OMERO_CLASS] == target_type:
        # Stop condition, we return the source_obj children
        if source_object.OMERO_CLASS != "WellSample":
            return source_object.listChildren()
        else:
            return [source_object.getImage()]
    else:  # Not yet the target
        result = []
        for child_obj in source_object.listChildren():
            # Going down in the Hierarchy list
            result.extend(get_children_recursive(child_obj, target_type))
        return result


def target_iterator(conn, source_object, target_type, is_tag):
    if target_type == source_object.OMERO_CLASS:
        target_obj_l = [source_object]
    elif source_object.OMERO_CLASS == "PlateAcquisition":
        # Check if there is more than one Run, otherwise
        # it's equivalent to start from a plate (and faster this way)
        plate_o = source_object.getParent()
        wellsamp_l = get_children_recursive(plate_o, "WellSample")
        if len(list(plate_o.listPlateAcquisitions())) > 1:
            # Only case where we need to filter on PlateAcquisition
            run_id = source_object.getId()
            wellsamp_l = filter(lambda x: x._obj.plateAcquisition._id._val
                                == run_id, wellsamp_l)
        target_obj_l = [wellsamp.getImage() for wellsamp in wellsamp_l]
    elif target_type == "PlateAcquisition":
        # No direct children access from a plate
        if source_object.OMERO_CLASS == "Screen":
            plate_l = get_children_recursive(source_object, "Plate")
        elif source_object.OMERO_CLASS == "Plate":
            plate_l = [source_object]
        target_obj_l = [r for p in plate_l for r in p.listPlateAcquisitions()]
    elif is_tag:
        target_obj_l = conn.getObjectsByAnnotations(target_type,
                                                    [source_object.getId()])
        # Need that to load objects
        obj_ids = [o.getId() for o in target_obj_l]
        target_obj_l = list(conn.getObjects(target_type, obj_ids))
    else:
        target_obj_l = get_children_recursive(source_object,
                                              target_type)

    print(f"Iterating objects from {source_object}:")
    for target_obj in target_obj_l:
        print(f"\t- {target_obj}")
        yield target_obj


def main_loop(conn, script_params):
    """
    For every object:
     - Find annotations in the namespace and remove
    """
    source_type = script_params["Data_Type"]
    target_type = script_params["Target Data_Type"]
    source_ids = script_params["IDs"]
    namespace_l = script_params["Namespace (blank for default)"]

    nsuccess = 0
    ntotal = 0
    result_obj = None

    for source_object in conn.getObjects(source_type, source_ids):
        is_tag = source_type == "TagAnnotation"
        for target_obj in target_iterator(conn, source_object,
                                          target_type, is_tag):
            success = remove_map_annotations(conn, target_obj, namespace_l)
            if success:
                nsuccess += 1
                if result_obj is None:
                    result_obj = target_obj

            ntotal += 1
        print("\n------------------------------------\n")
    message = f"Key value data deleted from {nsuccess} of {ntotal} objects"

    return message, result_obj


def remove_map_annotations(conn, obj, namespace_l):
    mapann_ids = []
    forbidden_deletion = []
    for namespace in namespace_l:
        p = {} if namespace == "*" else {"ns": namespace}
        for ann in obj.listAnnotations(**p):
            if isinstance(ann, omero.gateway.MapAnnotationWrapper):
                if ann.canEdit():  # If not, skipping it
                    mapann_ids.append(ann.id)
                else:
                    forbidden_deletion.append(ann.id)

    if len(mapann_ids) == 0:
        return 0
    print(f"\tMap Annotation IDs to delete: {mapann_ids}")
    if len(forbidden_deletion) > 0:
        print("\tMap Annotation IDs skipped (not permitted):",
              f"{forbidden_deletion}\n")
    try:
        conn.deleteObjects("Annotation", mapann_ids)
        return 1
    except Exception:
        print("Failed to delete links")
        return 0


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    # Cannot add fancy layout if we want auto fill and selct of object ID
    source_types = [
                    rstring("Project"), rstring("Dataset"), rstring("Image"),
                    rstring("Screen"), rstring("Plate"), rstring("Well"),
                    rstring("Run"), rstring("Image"), rstring("Tag"),
    ]

    # Duplicate Image for UI, but not a problem for script
    target_types = [
                    rstring("<on current>"), rstring("Project"),
                    rstring("- Dataset"), rstring("-- Image"),
                    rstring("Screen"), rstring("- Plate"),
                    rstring("-- Well"), rstring("-- Run"),
                    rstring("--- Image")
    ]

    # Here we define the script name and description.
    # Good practice to put url here to give users more guidance on how to run
    # your script.
    client = scripts.client(
        'Remove_KV.py',
        """
    This script deletes for the selected objects the key-value pairs
    associated to the given namespace.
    \t
    Check the guide for more information on parameters and errors:
    TODO link to omero-guides
    https://github.com/German-BioImaging/guide-KVpairs-scripts/blob/master/docs/gettingstarted.rst#deleting-key-value-pairs
    \t
    Default namespace: openmicroscopy.org/omero/client/mapAnnotation
        """,  # Tabs are needed to add line breaks in the HTML

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Parent-data type of the objects to annotate.",
            values=source_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of parent-data IDs containing the objects " +
                        "to delete annotation from.").ofType(rlong(0)),

        scripts.String(
            "Target Data_Type", optional=True, grouping="1.2",
            description="Choose the object type to delete annotation from.",
            values=target_types, default="<on current>"),

        scripts.List(
            "Namespace (blank for default)", optional=True,
            grouping="1.3",
            description="Annotation with these namespace will " +
                        "be deleted. Default is the client" +
                        " namespace, meaning editable in " +
                        "OMERO.web").ofType(rstring("")),

        scripts.Bool(
            AGREEMENT, optional=False, grouping="2",
            description="Make sure that you understood the scope of " +
                        "what will be deleted."),

        authors=["Christian Evenhuis", "MIF", "Tom Boissonnet"],
        institutions=["University of Technology Sydney", "CAi HHU"],
        contact="https://forum.image.sc/tag/omero",
    )

    try:
        params = parameters_parsing(client)
        print("Input parameters:")
        keys = ["Data_Type", "IDs", "Target Data_Type",
                "Namespace (blank for default)"]
        for k in keys:
            print(f"\t- {k}: {params[k]}")
        print("\n####################################\n")

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        message, robj = main_loop(conn, params)
        client.setOutput("Message", rstring(message))
        if robj is not None:
            client.setOutput("Result", robject(robj._obj))
    except AssertionError as err:
        # Display assertion errors in OMERO.web activities
        client.setOutput("ERROR", rstring(err))
        raise AssertionError(str(err))
    finally:
        client.closeSession()


def parameters_parsing(client):
    params = {}
    # Param dict with defaults for optional parameters
    params["Namespace (blank for default)"] = [NSCLIENTMAPANNOTATION]

    for key in client.getInputKeys():
        if client.getInput(key):
            # unwrap rtypes to String, Integer etc
            params[key] = client.getInput(key, unwrap=True)

    assert params[AGREEMENT], "Please tick the box to confirm that you " +\
                              "understood the risks."

    if params["Target Data_Type"] == "<on current>":
        params["Target Data_Type"] = params["Data_Type"]
    elif " " in params["Target Data_Type"]:
        # Getting rid of the trailing '---' added for the UI
        params["Target Data_Type"] = params["Target Data_Type"].split(" ")[1]

    assert params["Target Data_Type"] in ALLOWED_PARAM[params["Data_Type"]], \
           (f"{params['Target Data_Type']} is not a valid target for " +
            f"{params['Data_Type']}.")

    if params["Data_Type"] == "Tag":
        params["Data_Type"] = "TagAnnotation"

    if params["Data_Type"] == "Run":
        params["Data_Type"] = "Acquisition"
    if params["Target Data_Type"] == "Run":
        params["Target Data_Type"] = "PlateAcquisition"

    # Remove duplicate entries from namespace list
    tmp = params["Namespace (blank for default)"]
    if "*" in tmp:
        tmp = ["*"]
    params["Namespace (blank for default)"] = list(set(tmp))

    return params


if __name__ == "__main__":
    run_script()
