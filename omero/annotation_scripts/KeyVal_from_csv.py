# coding=utf-8
"""
 MIF/Add_Key_Val_from_csv.py

 Adds key-value (kv) metadata to images in a dataset from a csv file
 The first column contains the filenames
 The first  row of the file contains the keys
 The rest is the values for each file/key

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
Created by Christian Evenhuis

"""

import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong
import omero.scripts as scripts
from omero.cmd import Delete2

import sys
import csv
import copy
from math import floor

from omero.util.populate_roi import DownloadingOriginalFileProvider

from collections import OrderedDict

HIERARCHY_OBJECTS = {
                        "Project": ["Dataset", "Image"],
                        "Dataset": ["Image"],
                        "Screen": ["Plate", "Well", "Image"],
                        "Plate": ["Well", "Image"],
                        #"Run": ["Well", "Image"],
                        "Well": ["Image"]
                    }


def get_existing_map_annotations(obj):
    """Get all Map Annotations linked to the object"""
    ord_dict = OrderedDict()
    for ann in obj.listAnnotations():
        if isinstance(ann, omero.gateway.MapAnnotationWrapper):
            kvs = ann.getValue()
            for k, v in kvs:
                if k not in ord_dict:
                    ord_dict[k] = set()
                ord_dict[k].add(v)
    return ord_dict


def remove_map_annotations(conn, object):
    """Remove ALL Map Annotations on the object"""
    anns = list(object.listAnnotations())
    mapann_ids = [ann.id for ann in anns
                  if isinstance(ann, omero.gateway.MapAnnotationWrapper)]

    try:
        delete = Delete2(targetObjects={'MapAnnotation': mapann_ids})
        handle = conn.c.sf.submit(delete)
        conn.c.waitOnCmd(handle, loops=10, ms=500, failonerror=True,
                         failontimeout=False, closehandle=False)

    except Exception as ex:
        print("Failed to delete links: {}".format(ex.message))
    return


def get_original_file(omero_object, file_ann_id=None):
    """Find file linked to object. Option to filter by ID."""
    file_ann = None
    for ann in omero_object.listAnnotations():
        if isinstance(ann, omero.gateway.FileAnnotationWrapper):
            file_name = ann.getFile().getName()
            # Pick file by Ann ID (or name if ID is None)
            if ann.getId() == file_ann_id:
                file_ann = ann # Found it
                break
            elif file_ann_id is None and file_name.endswith(".csv"):
                if (file_ann is None) or (ann.getId() > file_ann.getId()):
                    # Get the file with the biggest ID, that should be the most recent
                    file_ann = ann
    if file_ann is None:
        sys.stderr.write("Error: File does not exist.\n")
        sys.exit(1)

    return file_ann.getFile()._obj


def link_file_ann(conn, object_type, object_id, file_ann_id):
    """Link File Annotation to the Object, if not already linked."""
    file_ann = conn.getObject("Annotation", file_ann_id)
    if file_ann is None:
        sys.stderr.write("Error: File Annotation not found: %s.\n"
                         % file_ann_id)
        sys.exit(1)
    omero_object = conn.getObject(object_type, object_id)
    # Check for existing links
    links = list(conn.getAnnotationLinks(object_type, parent_ids=[object_id],
                                         ann_ids=[file_ann_id]))
    if len(links) == 0:
        omero_object.linkAnnotation(file_ann)

def read_csv(conn, source_object, file_ann_id): #Dedicated function to read the CSV file
    original_file = get_original_file(source_object, file_ann_id)
    print("Original File", original_file.id.val, original_file.name.val)
    provider = DownloadingOriginalFileProvider(conn)
    # read the csv
    temp_file = provider.get_original_file_data(original_file)
    # Needs omero-py 5.9.1 or later
    temp_name = temp_file.name
    file_length = original_file.size.val
    with open(temp_name, 'rt', encoding='utf-8-sig') as file_handle:
        try:
            delimiter = csv.Sniffer().sniff(
                file_handle.read(floor(file_length/4)), ",;\t").delimiter
            print("Using delimiter: ", delimiter,
                    f" after reading {floor(file_length/4)} characters")
        except Exception:
            file_handle.seek(0)
            try:
                delimiter = csv.Sniffer().sniff(
                    file_handle.read(floor(file_length/2)),
                    ",;\t").delimiter
                print("Using delimiter: ", delimiter,
                        f"after reading {floor(file_length/2)} characters")
            except Exception:
                file_handle.seek(0)
                try:
                    delimiter = csv.Sniffer().sniff(
                        file_handle.read(floor(file_length*0.75)),
                        ",;\t").delimiter
                    print("Using delimiter: ", delimiter,
                            f" after reading {floor(file_length*0.75)}"
                            " characters")
                except Exception:
                    print("Failed to sniff delimiter, using ','")
                    delimiter = ","

        # reset to start and read whole file...
        file_handle.seek(0)
        data = list(csv.reader(file_handle, delimiter=delimiter))

    # keys are in the header row
    header = data[0]
    print("header", header)
    return data, header

def get_children_recursive(source_object, target_type):
    if HIERARCHY_OBJECTS[source_object.OMERO_CLASS][0] == target_type: # Stop condition, we return the source_obj children
        return source_object.listChildren()
    else:
        result = []
        for child_obj in source_object.listChildren():
            # Going down in the Hierarchy list for all childs that aren't yet the target
            result.extend(get_children_recursive(child_obj, target_type))
        return result

def keyval_from_csv(conn, script_params):
    source_type = script_params["Source_object_type"]
    target_type = script_params["Target_object_type"]
    source_ids = script_params["Source_IDs"]
    file_ids = script_params["File_Annotation_ID"]

    ntarget_processed = 0
    ntarget_updated = 0
    missing_names = 0

    for source_object, file_ann_id in zip(conn.getObjects(source_type, source_ids), file_ids):
        #link_file_ann(conn, source_type, source_object.id, file_ann_id) # Make sure file is attached to the source
        print("set ann id", file_ann_id)
        data, header = read_csv(conn, source_object, file_ann_id)

        # Listing all target children to the source object (eg all images (target) in all datasets of the project (source))
        target_obj_l = get_children_recursive(source_object, target_type)

        # Finds the index of the column used to identify the targets. Try for IDs first
        idx_id = header.index("target_id") if "target_id" in header else -1
        idx_name = header.index("target_name") if "target_name" in header else -1
        use_id = idx_id != -1

        if not use_id: # Identify images by name must fail if two images have identical names
            idx_id = idx_name
            target_d = dict()
            for target_obj in target_obj_l:
                assert target_obj.getName() not in target_d.keys(), f"Target objects identified by name have duplicate: {target_obj.getName()}"
                target_d[target_obj.getName()] = target_obj
        else: # Setting the dictionnary target_id:target_obj   keys as string to match CSV reader output
            target_d = {str(target_obj.getId()):target_obj for target_obj in target_obj_l}
        ntarget_processed += len(target_d)

        rows = data[1:]
        for row in rows: # Iterate the CSV rows and search for the matching target
            target_id = row[idx_id]
            if target_id in target_d.keys():
                target_obj = target_d[target_id]
                if target_type in ["Dataset", "Image", "Plate"]:
                    print("Annotating Target:", f"{target_obj.getName()+':' if use_id else ''}{target_id}")
                else:
                    print("Annotating Target:", f"{target_id}") # Some object don't have a name
            else:
                missing_names += 1
                print(f"Target not found: {target_id}")
                continue

            cols_to_ignore = [idx_id, idx_name]
            updated = annotate_object(conn, target_obj, header, row, cols_to_ignore)
            if updated:
                ntarget_updated += 1

    message = f"Added kv pairs to {ntarget_updated}/{ntarget_processed} {target_type}"
    if missing_names > 0:
        message += f". {missing_names} {target_type} not found (using {'ID' if use_id else 'name'} to identify them)."
    return message


def annotate_object(conn, obj, header, row, cols_to_ignore):

    obj_updated = False
    existing_kv = get_existing_map_annotations(obj)
    updated_kv = copy.deepcopy(existing_kv)
    print("Existing kv:")
    for k, vset in existing_kv.items():
        for v in vset:
            print("   ", k, v)

    print("Adding kv:")
    for i in range(len(row)):
        if i in cols_to_ignore or i >= len(header):
            continue
        key = header[i].strip()
        vals = row[i].strip().split(';')
        if len(vals) > 0:
            for val in vals:
                if len(val) > 0:
                    if key not in updated_kv:
                        updated_kv[key] = set()
                    print("   ", key, val)
                    updated_kv[key].add(val)

    if existing_kv != updated_kv:
        obj_updated = True
        print("The key-values pairs are different")
        remove_map_annotations(conn, obj)
        map_ann = omero.gateway.MapAnnotationWrapper(conn)
        namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION
        map_ann.setNs(namespace)
        # convert the ordered dict to a list of lists
        kv_list = []
        for k, vset in updated_kv.items():
            for v in vset:
                kv_list.append([k, v])
        map_ann.setValue(kv_list)
        map_ann.save()
        print("Map Annotation created", map_ann.id)
        obj.linkAnnotation(map_ann)
    else:
        print("No change change in kv")

    return obj_updated


def run_script():

    source_types = [rstring("Project"), rstring("Dataset"),
                    rstring("Screen"), rstring("Plate"),
                    rstring("Well")]

    target_types = [rstring("Dataset"), rstring("Plate"),
                    rstring("Well"), rstring("Image")]

    client = scripts.client(
        'Add_Key_Val_from_csv',
        """
    This script reads an attached CSV file to annotate objects with key-value pairs.
        """,
        scripts.String(
            "Source_object_type", optional=False, grouping="1",
            description="Choose the object type containing the objects to annotate",
            values=source_types, default="Dataset"),

        scripts.List(
            "Source_IDs", optional=False, grouping="1.1",
            description="List of source IDs containing the images to annotate.").ofType(rlong(0)),

        scripts.List(
            "File_Annotation_ID", optional=True, grouping="1.2",
            description="List of file IDs containing metadata to populate. If given, must match length of 'Source IDs'. Otherwise, uses the CSV file with the highest ID.").ofType(rlong(0)),

        scripts.String(
            "Target_object_type", optional=False, grouping="2",
            description="Choose the object type to annotate (must be bellow the chosen source object type)",
            values=target_types, default="Image"),

        authors=["Christian Evenhuis", "Tom Boissonnet"],
        institutions=["MIF UTS", "CAi HHU"],
        contact="https://forum.image.sc/tag/omero",
        version="2.0.0"
    )


    try:
        # process the list of args above.
        script_params = {"File_Annotation_ID": [None]} # Set with defaults for optional parameters
        for key in client.getInputKeys():
            if client.getInput(key):
                script_params[key] = client.getInput(key, unwrap=True)

        # validate that target is bellow source
        source_name, target_name = script_params["Source_object_type"], script_params["Target_object_type"]
        assert target_name in HIERARCHY_OBJECTS[source_name], f"Invalid {source_name} => {target_name}. The target type must be a child of the source type"

        if len(script_params["File_Annotation_ID"]) == 1: # Poulate the parameter with None or same ID for all source
            script_params["File_Annotation_ID"] = script_params["File_Annotation_ID"] * len(script_params["Source_IDs"])
        assert len(script_params["File_Annotation_ID"]) ==  len(script_params["Source_IDs"]), "Number of Source IDs and FileAnnotation IDs must match"

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        print("script params")
        for k, v in script_params.items():
            print(k, v)
        message = keyval_from_csv(conn, script_params)
        client.setOutput("Message", rstring(message))

    except AssertionError as err: #Display assertion errors in OMERO.web activities
        client.setOutput("ERROR", rstring(err))
        raise AssertionError(str(err))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
