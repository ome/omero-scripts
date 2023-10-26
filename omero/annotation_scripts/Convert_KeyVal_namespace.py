# coding=utf-8
"""
 Convert_namespace_KeyVal.py

 Convert the namespace of objects key-value pairs.
-----------------------------------------------------------------------------
  Copyright (C) 2018
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
Created by Tom Boissonnet

"""

import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong, robject
import omero.scripts as scripts
from omero.constants.metadata import NSCLIENTMAPANNOTATION

from collections import OrderedDict

CHILD_OBJECTS = {
                    "Project": "Dataset",
                    "Dataset": "Image",
                    "Screen": "Plate",
                    "Plate": "Well",
                    # "Run": ["Well", "Image"],
                    "Well": "WellSample",
                    "WellSample": "Image"
                }


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


def get_existing_map_annotions(obj, namespace_l):
    keyval_l, ann_l = [], []
    forbidden_deletion = []
    for namespace in namespace_l:
        for ann in obj.listAnnotations(ns=namespace):
            if isinstance(ann, omero.gateway.MapAnnotationWrapper):
                if ann.canEdit():  # If not, skipping it
                    keyval_l.extend([(k, v) for (k, v) in ann.getValue()])
                    ann_l.append(ann)
                else:
                    forbidden_deletion.append(ann.id)
    print("\tMap Annotation IDs skipped (not permitted):",
          f"{forbidden_deletion}")
    return keyval_l, ann_l


def remove_map_annotations(conn, obj, ann_l):
    mapann_ids = [ann.id for ann in ann_l]

    if len(mapann_ids) == 0:
        return 0
    print(f"\tMap Annotation IDs to delete: {mapann_ids}\n")
    try:
        conn.deleteObjects("Annotation", mapann_ids)
        return 1
    except Exception:
        print("Failed to delete links")
        return 0


def annotate_object(conn, obj, kv_list, namespace):

    map_ann = omero.gateway.MapAnnotationWrapper(conn)
    map_ann.setNs(namespace)
    map_ann.setValue(kv_list)
    map_ann.save()

    print("\tMap Annotation created", map_ann.id)
    obj.linkAnnotation(map_ann)


def target_iterator(conn, source_object, target_type):
    source_type = source_object.OMERO_CLASS
    if source_type == target_type:
        target_obj_l = [source_object]
    elif source_type == "TagAnnotation":
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


def replace_namespace(conn, script_params):
    source_type = script_params["Data_Type"]
    target_type = script_params["Target Data_Type"]
    source_ids = script_params["IDs"]
    old_namespace = script_params["Old Namespace (leave blank for default)"]
    new_namespace = script_params["New Namespace (leave blank for default)"]

    ntarget_processed = 0
    ntarget_updated = 0
    result_obj = None

    # One file output per given ID
    for source_object in conn.getObjects(source_type, source_ids):

        for target_obj in target_iterator(conn, source_object, target_type):
            ntarget_processed += 1
            keyval_l, ann_l = get_existing_map_annotions(target_obj,
                                                         old_namespace)
            if len(keyval_l) > 0:
                annotate_object(conn, target_obj, keyval_l, new_namespace)
                remove_map_annotations(conn, target_obj, ann_l)
                ntarget_updated += 1
                if result_obj is None:
                    result_obj = target_obj
            else:
                print("\tNo MapAnnotation found with that namespace\n")
        print("\n------------------------------------\n")
    message = f"Updated kv pairs to \
        {ntarget_updated}/{ntarget_processed} {target_type}"

    return message, result_obj


def run_script():

    # Cannot add fancy layout if we want auto fill and selct of object ID
    source_types = [rstring("Project"), rstring("Dataset"), rstring("Image"),
                    rstring("Screen"), rstring("Plate"),
                    rstring("Well"), rstring("Tag"),
                    rstring("Image"),
                    ]

    # Duplicate Image for UI, but not a problem for script
    target_types = [rstring("Project"),
                    rstring("- Dataset"), rstring("-- Image"),
                    rstring("Screen"), rstring("- Plate"),
                    rstring("-- Well"), rstring("--- Image")]

    client = scripts.client(
        'Convert_KeyVal_namespace',
        """
    This script converts the namespace of key-value pair annotations.

    TODO: add hyperlink to readthedocs
    \t
    Parameters:
    \t
    - Data Type: parent-objects type in which target-objects are searched.
    - IDs: IDs of the parent-objects.
    - Target Data Type: Type of the target-objects that will be changed.
    - Old Namespace: Namespace(s) of the annotations to group and change.
    - New Namespace: New namespace for the annotations.
    \t
        """,  # Tabs are needed to add line breaks in the HTML

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Parent-data type of the objects to annotate.",
            values=source_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of parent-data IDs containing the objects \
                to annotate.").ofType(rlong(0)),

        scripts.String(
            "Target Data_Type", optional=False, grouping="1.2",
            description="The data type for which key-value pair annotations \
                will be converted.",
            values=target_types, default="-- Image"),

        scripts.List(
            "Old Namespace (leave blank for default)", optional=True,
            grouping="1.4",
            description="The namespace(s) of the annotations to \
                group and change.").ofType(rstring("")),

        scripts.String(
            "New Namespace (leave blank for default)", optional=True,
            grouping="1.5",
            description="The new namespace for the annotations."),

        authors=["Tom Boissonnet"],
        institutions=["CAi HHU"],
        contact="https://forum.image.sc/tag/omero"
    )

    params = parameters_parsing(client)
    print("Input parameters:")
    keys = ["Data_Type", "IDs", "Target Data_Type",
            "Old Namespace (leave blank for default)",
            "New Namespace (leave blank for default)"]
    for k in keys:
        print(f"\t- {k}: {params[k]}")
    print("\n####################################\n")
    try:
        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        message, robj = replace_namespace(conn, params)
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
    params = OrderedDict()
    # Param dict with defaults for optional parameters
    params["File_Annotation"] = None
    params["Old Namespace (leave blank for default)"] = [NSCLIENTMAPANNOTATION]
    params["New Namespace (leave blank for default)"] = NSCLIENTMAPANNOTATION

    for key in client.getInputKeys():
        if client.getInput(key):
            params[key] = client.getInput(key, unwrap=True)

    # Getting rid of the trailing '---' added for the UI
    if " " in params["Target Data_Type"]:
        params["Target Data_Type"] = params["Target Data_Type"].split(" ")[1]

    if params["Data_Type"] == "Tag":
        params["Data_Type"] = "TagAnnotation"

    return params


if __name__ == "__main__":
    run_script()
