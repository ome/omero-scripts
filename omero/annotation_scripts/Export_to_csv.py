# coding=utf-8
"""
 Export_to_csv.py

 Reads the metadata associated with the images in a dataset
 and creates a csv file attached to dataset

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
from omero.rtypes import rstring, rlong, robject
from omero.constants.metadata import NSCLIENTMAPANNOTATION
import omero.scripts as scripts

import tempfile
import os
from collections import OrderedDict

CHILD_OBJECTS = {
                    "Project": "Dataset",
                    "Dataset": "Image",
                    "Screen": "Plate",
                    "Plate": "Well",
                    "Well": "WellSample",
                    "WellSample": "Image"
                }

# To allow duplicated keys
# (3 means up to 1000 same key on a single object)
ZERO_PADDING = 3
WEBCLIENT_URL = "https://omero-cai-test.hhu.de/webclient"


def get_obj_name(omero_obj):
    if omero_obj.OMERO_CLASS == "Well":
        return omero_obj.getWellPos()
    else:
        return omero_obj.getName()


def get_existing_map_annotions(obj, namespace_l):
    key_l = []
    result = OrderedDict()
    for namespace in namespace_l:
        for ann in obj.listAnnotations(ns=namespace):
            if isinstance(ann, omero.gateway.MapAnnotationWrapper):
                for (k, v) in ann.getValue():
                    n_occurence = key_l.count(k)
                    pad_key = f"{str(n_occurence).rjust(ZERO_PADDING, '0')}{k}"
                    result[pad_key] = v
                    key_l.append(k)  # To count the multiple occurence of keys
    return result


def group_keyvalue_dictionaries(annotation_dicts):
    """ Groups the keys and values of each object into a single dictionary """
    all_key = OrderedDict()  # To keep the keys in order, for what it's worth
    for annotation_dict in annotation_dicts:
        all_key.update({k: None for k in annotation_dict.keys()})
    all_key = list(all_key.keys())

    result = []
    for annotation_dict in annotation_dicts:
        obj_dict = OrderedDict((k, "") for k in all_key)
        obj_dict.update(annotation_dict)
        for k, v in obj_dict.items():
            if v is None:
                obj_dict[k]
        result.append(list(obj_dict.values()))

    # Removing temporary padding
    all_key = [key[ZERO_PADDING:] for key in all_key]
    return all_key, result


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


def attach_csv_file(conn, obj_, csv_name, obj_id_l, obj_name_l,
                    obj_ancestry_l, annotation_dicts, separator, is_well):
    def to_csv(ll):
        """convience function to write a csv line"""
        nl = len(ll)
        fmstr = ("{}"+separator)*(nl-1)+"{}\n"
        return fmstr.format(*ll)

    def sort_items(obj_name_l, obj_ancestry_l, whole_values_l, is_well):
        result_name = []
        result_ancestry = []
        result_value = []

        # That's an imbricated list of list of tuples, making it simplier first
        tmp_ancestry_l = []
        for ancestries in obj_ancestry_l:
            tmp_ancestry_l.append(["".join(list(obj_name))
                                   for obj_name in ancestries])

        start_idx = 0
        stop_idx = 1
        while start_idx < len(tmp_ancestry_l):
            while (stop_idx < len(tmp_ancestry_l)
                    and ("".join(tmp_ancestry_l[stop_idx])
                         == "".join(tmp_ancestry_l[start_idx]))):
                stop_idx += 1

            subseq = obj_name_l[start_idx:stop_idx]
            if not is_well:
                # Get the sort index from the range object (argsort)
                sort_order = sorted(range(len(subseq)), key=subseq.__getitem__)
            else:
                # Same but pad the 'well-name keys number' with zeros first
                sort_order = sorted(range(len(subseq)),
                                    key=lambda x: f"{subseq[x][0]}\
                                        {int(subseq[x][1:]):03}")

            for idx in sort_order:
                result_name.append(obj_name_l[start_idx:stop_idx][idx])
                result_ancestry.append(obj_ancestry_l[start_idx:stop_idx][idx])
                result_value.append(whole_values_l[start_idx:stop_idx][idx])

            start_idx = stop_idx
            stop_idx += 1

        return result_name, result_ancestry, result_value

    all_key, whole_values_l = group_keyvalue_dictionaries(annotation_dicts)

    counter = 0

    if len(obj_ancestry_l) > 0:  # If there's anything to add at all
        # Only sort when there are parents to group childs
        obj_name_l, obj_ancestry_l, whole_values_l = sort_items(obj_name_l,
                                                                obj_ancestry_l,
                                                                whole_values_l,
                                                                is_well)
        for (parent_type, _) in obj_ancestry_l[0]:
            all_key.insert(counter, parent_type)
            counter += 1
    all_key.insert(counter, "OBJECT_ID")
    all_key.insert(counter + 1, "OBJECT_NAME")
    print(f"\tColumn names: {all_key}", "\n")

    for k, (obj_id, obj_name, whole_values) in enumerate(zip(obj_id_l,
                                                             obj_name_l,
                                                             whole_values_l)):
        counter = 0
        if len(obj_ancestry_l) > 0:  # If there's anything to add at all
            for (_, parent_name) in obj_ancestry_l[k]:
                whole_values.insert(counter, parent_name)
                counter += 1
        whole_values.insert(counter, obj_id)
        whole_values.insert(counter + 1, obj_name)

    # create the tmp directory
    tmp_dir = tempfile.mkdtemp(prefix='MIF_meta')
    (fd, tmp_file) = tempfile.mkstemp(dir=tmp_dir, text=True)
    tfile = os.fdopen(fd, 'w')
    tfile.write(to_csv(all_key))
    # write the keys values for each file
    for whole_values in whole_values_l:
        tfile.write(to_csv(whole_values))
    tfile.close()

    # link it to the object
    file_ann = conn.createFileAnnfromLocalFile(
        tmp_file, origFilePathAndName=csv_name,
        ns='KeyVal_export')
    obj_.linkAnnotation(file_ann)

    print(f"{file_ann} linked to {obj_}")

    # remove the tmp file
    os.remove(tmp_file)
    os.rmdir(tmp_dir)

    return file_ann.getFile()


def target_iterator(conn, source_object, target_type, is_tag):
    if target_type == source_object.OMERO_CLASS:
        target_obj_l = [source_object]
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
    ''' writes the data (list of dicts) to a file
    @param conn:             Blitz Gateway connection wrapper
    @param script_params:     A map of the input parameters
    '''
    source_type = script_params["Data_Type"]
    target_type = script_params["Target Data_Type"]
    source_ids = script_params["IDs"]
    namespace_l = script_params["Namespace (leave blank for default)"]
    separator = script_params["Separator"]
    include_parent = script_params["Include column(s) of parents name"]

    is_well = False

    # One file output per given ID
    obj_ancestry_l = []
    annotation_dicts = []
    obj_id_l, obj_name_l = [], []
    for source_object in conn.getObjects(source_type, source_ids):

        result_obj = source_object
        if source_type == "TagAnnotation":
            result_obj = None  # Attach result csv on the first object
        is_tag = source_type == "TagAnnotation"

        for target_obj in target_iterator(conn, source_object,
                                          target_type, is_tag):
            is_well = target_obj.OMERO_CLASS == "Well"
            annotation_dicts.append(get_existing_map_annotions(target_obj,
                                                               namespace_l))
            obj_id_l.append(target_obj.getId())
            obj_name_l.append(get_obj_name(target_obj))
            if include_parent:
                ancestry = [(o.OMERO_CLASS, get_obj_name(o))
                            for o in target_obj.getAncestry()
                            if o.OMERO_CLASS != "WellSample"]
                obj_ancestry_l.append(ancestry[::-1])
            if result_obj is None:
                result_obj = target_obj
        print("\n------------------------------------\n")
    csv_name = "{}_keyval.csv".format(get_obj_name(source_object))
    file_ann = attach_csv_file(conn, result_obj, csv_name, obj_id_l,
                               obj_name_l, obj_ancestry_l,
                               annotation_dicts, separator, is_well)

    message = ("The csv is attached to " +
               f"{result_obj.OMERO_CLASS}:{result_obj.getId()}")

    return message, file_ann, result_obj


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    # Cannot add fancy layout if we want auto fill and selct of object ID
    source_types = [rstring("Project"), rstring("Dataset"), rstring("Image"),
                    rstring("Screen"), rstring("Plate"),
                    rstring("Well"), rstring("Image"), rstring("Tag"),
                    ]

    # Duplicate Image for UI, but not a problem for script
    target_types = [rstring("<on current>"), rstring("Project"),
                    rstring("- Dataset"), rstring("-- Image"),
                    rstring("Screen"), rstring("- Plate"),
                    rstring("-- Well"), rstring("--- Image")]

    separators = [";", ",", "TAB"]
    # Here we define the script name and description.
    # Good practice to put url here to give users more guidance on how to run
    # your script.
    client = scripts.client(
        'Export_KV_to_csv.py',
        """
    This script exports key-value pairs of objects to a .csv file.
    Can also export a blank .csv with only of target objects' name and IDs.
    (for example by providing a non-existing namespace)
    TODO: add hyperlink to readthedocs
    \t
    Parameters:
    \t
    - Data Type: parent-objects type in which target-objects are searched.
    - IDs: IDs of the parent-objects.
    - Target Data Type: target-objects type from which KV-pairs are exported.
    - Namespace: Annotations having one of these namespace(s) will be exported.
    \t
    - Separator: Separator to be used in the .csv file.
    - Include column(s) of parents name: Add columns for target-data parents.
    \t
        """,  # Tabs are needed to add line breaks in the HTML

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Parent data type of the objects to annotate.",
            values=source_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of parent data IDs containing the objects \
                to delete annotation from.").ofType(rlong(0)),

        scripts.String(
            "Target Data_Type", optional=True, grouping="1.2",
            description="Choose the object type to delete annotation from.",
            values=target_types, default="<on current>"),

        scripts.List(
            "Namespace (leave blank for default)", optional=True,
            grouping="1.3",
            description="Namespace(s) to include for the export of key-" +
                        "value pairs annotations. Default is the client" +
                        "namespace, meaning editable in " +
                        "OMERO.web").ofType(rstring("")),

        scripts.Bool(
            "Advanced parameters", optional=True, grouping="2", default=False,
            description="Ticking or unticking this has no effect"),

        scripts.String(
            "Separator", optional=False, grouping="2.1",
            description="Choose the .csv separator.",
            values=separators, default=";"),

        scripts.Bool(
            "Include column(s) of parents name", optional=False,
            grouping="2.2",
            description="Weather to include or not the name of the parent(s) \
                objects as columns in the .csv.", default=False),

        authors=["Christian Evenhuis", "MIF", "Tom Boissonnet"],
        institutions=["University of Technology Sydney", "CAi HHU"],
        contact="https://forum.image.sc/tag/omero",
    )

    params = parameters_parsing(client)
    print("Input parameters:")
    keys = ["Data_Type", "IDs", "Target Data_Type",
            "Namespace (leave blank for default)",
            "Separator", "Include column(s) of parents name"]
    for k in keys:
        print(f"\t- {k}: {params[k]}")
    print("\n####################################\n")
    try:
        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        message, fileann, res_obj = main_loop(conn, params)
        client.setOutput("Message", rstring(message))

        if WEBCLIENT_URL != "":
            url = omero.rtypes.wrap({
                "type": "URL",
                "href": f"{WEBCLIENT_URL}/download_original_file/{fileann.getId()}",
                "title": "CSV file of Key-Value pairs",
            })
            client.setOutput("URL", url)
        elif res_obj is not None:
            client.setOutput("Result", robject(res_obj))

    except AssertionError as err:
        # Display assertion errors in OMERO.web activities
        client.setOutput("ERROR", rstring(err))
        raise AssertionError(str(err))
    finally:
        client.closeSession()


def parameters_parsing(client):
    params = {}
    # Param dict with defaults for optional parameters
    params["Namespace (leave blank for default)"] = [NSCLIENTMAPANNOTATION]

    for key in client.getInputKeys():
        if client.getInput(key):
            # unwrap rtypes to String, Integer etc
            params[key] = client.getInput(key, unwrap=True)

    # Getting rid of the trailing '---' added for the UI
    if params["Target Data_Type"] == "<on current>":
        assert params["Data_Type"] != "Tag", ("Choose a Target type " +
                                              "with 'Tag' as Data Type ")
        params["Target Data_Type"] = params["Data_Type"]
    elif " " in params["Target Data_Type"]:
        params["Target Data_Type"] = params["Target Data_Type"].split(" ")[1]

    if params["Separator"] == "TAB":
        params["Separator"] = "\t"

    if params["Data_Type"] == "Tag":
        params["Data_Type"] = "TagAnnotation"
    return params


if __name__ == "__main__":
    run_script()
