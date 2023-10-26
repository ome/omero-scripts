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

CHILD_OBJECTS = {
                    "Project": "Dataset",
                    "Dataset": "Image",
                    "Screen": "Plate",
                    "Plate": "Well",
                    #"Run": ["Well", "Image"],
                    "Well": "WellSample",
                    "WellSample": "Image"
                }

def get_children_recursive(source_object, target_type):
    print(source_object, target_type)
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

def get_existing_map_annotions(obj, namespace_l):
    keyval_l, ann_l = [], []
    for namespace in namespace_l:
        for ann in obj.listAnnotations(ns=namespace):
            if isinstance(ann, omero.gateway.MapAnnotationWrapper):
                keyval_l.extend([(k,v) for (k,v) in ann.getValue()])
                ann_l.append(ann)
    return keyval_l, ann_l

def remove_map_annotations(conn, obj, ann_l):
    mapann_ids = [ann.id for ann in ann_l]

    if len(mapann_ids) == 0:
        return 0
    print("Map Annotation IDs to delete:", mapann_ids)
    try:
        conn.deleteObjects("Annotation", mapann_ids)
        return 1
    except Exception:
        print("Failed to delete links")
        return 0

def annotate_object(conn, obj, kv_list, namespace):

    print("Adding kv:")

    map_ann = omero.gateway.MapAnnotationWrapper(conn)
    map_ann.setNs(namespace)
    map_ann.setValue(kv_list)
    map_ann.save()

    print("Map Annotation created", map_ann.id)
    obj.linkAnnotation(map_ann)

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

        if source_type == target_type:
            target_obj_l = [source_object]
        else:
            if source_type == "TagAnnotation":
                target_obj_l = conn.getObjectsByAnnotations(target_type, [source_object.getId()])
                target_obj_l = list(conn.getObjects(target_type, [o.getId() for o in target_obj_l])) # Need that to load annotations later
            else:
                target_obj_l = get_children_recursive(source_object, target_type)
            # Listing all target children to the source object (eg all images (target) in all datasets of the project (source))

        for target_obj in target_obj_l:
            ntarget_processed += 1
            print("Processing object:", target_obj)
            keyval_l, ann_l = get_existing_map_annotions(target_obj, old_namespace)
            if len(keyval_l) > 0:
                annotate_object(conn, target_obj, keyval_l, new_namespace)
                remove_map_annotations(conn, target_obj, ann_l)
                ntarget_updated += 1
                if result_obj is None:
                    result_obj = target_obj

    message = f"Updated kv pairs to {ntarget_updated}/{ntarget_processed} {target_type}"

    return message, result_obj

def run_script():

    source_types = [rstring("Project"), rstring("Dataset"), rstring("Image"),
                    rstring("Screen"), rstring("Plate"),
                    rstring("Well"), rstring("Tag"),
                    rstring("Image"), # Cannot add fancy layout if we want auto fill and selct of object ID
                    ]

    target_types = [rstring("Project"), # Duplicate Image for UI, but not a problem for script
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
    - Data Type: Type of the "parent objects" in which "target objects" are searched.
    - IDs: IDs of the "parent objects".
    - Target Data Type: Type of the "target objects" that will be changed.
    - Old Namespace: Namespace(s) of the annotations to group and change.
    - New Namespace: New namespace for the annotations.
    \t
        """, # Tabs are needed to add line breaks in the HTML

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Parent data type of the objects to annotate.",
            values=source_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of parent data IDs containing the objects to annotate.").ofType(rlong(0)),

        scripts.String(
            "Target Data_Type", optional=False, grouping="1.2",
            description="The data type for which key-value pair annotations will be converted.",
            values=target_types, default="-- Image"),

        scripts.List(
            "Old Namespace (leave blank for default)", optional=True, grouping="1.4",
            description="The namespace(s) of the annotations to group and change.").ofType(rstring("")),

        scripts.String(
            "New Namespace (leave blank for default)", optional=True, grouping="1.5",
            description="The new namespace for the annotations."),

        authors=["Tom Boissonnet"],
        institutions=["CAi HHU"],
        contact="https://forum.image.sc/tag/omero"
    )


    try:
        # process the list of args above.
        script_params = { # Param dict with defaults for optional parameters
            "File_Annotation": None,
            "Old Namespace (leave blank for default)": [omero.constants.metadata.NSCLIENTMAPANNOTATION],
            "New Namespace (leave blank for default)": omero.constants.metadata.NSCLIENTMAPANNOTATION
            }
        for key in client.getInputKeys():
            if client.getInput(key):
                script_params[key] = client.getInput(key, unwrap=True)

        # Getting rid of the trailing '---' added for the UI
        tmp_trg = script_params["Target Data_Type"]
        script_params["Target Data_Type"] = tmp_trg.split(" ")[1] if " " in tmp_trg else tmp_trg

        if script_params["Data_Type"] == "Tag":
            script_params["Data_Type"] = "TagAnnotation"

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        print("script params")
        for k, v in script_params.items():
            print(k, v)
        message, robj = replace_namespace(conn, script_params)
        client.setOutput("Message", rstring(message))
        if robj is not None:
            client.setOutput("Result", robject(robj._obj))

    except AssertionError as err: #Display assertion errors in OMERO.web activities
        client.setOutput("ERROR", rstring(err))
        raise AssertionError(str(err))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
