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
from collections import OrderedDict, defaultdict

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

# Add your OMERO.web URL for direct download from link:
# eg https://omero-adress.org/webclient
WEBCLIENT_URL = ""


def get_obj_name(omero_obj):
    if omero_obj.OMERO_CLASS == "Well":
        return omero_obj.getWellPos()
    else:
        return omero_obj.getName()


def get_existing_map_annotions(obj, namespace_l):
    "Return list of KV with updated keys with NS and occurences"
    annotation_dict_l = defaultdict(list)
    for ns in namespace_l:
        for ann in obj.listAnnotations(ns=ns):
            if isinstance(ann, omero.gateway.MapAnnotationWrapper):
                annotation_dict_l[ns].append(ann.getValue())
    return annotation_dict_l


def group_keyvalue_dicts(annotation_dict_l, include_namespace):
    """ Groups the keys and values of each object into a single dictionary """

    # STEP 1: finding all namespace
    set_ns = set()
    for ann_dict in annotation_dict_l:
        set_ns.update(list(ann_dict.keys()))
    set_ns = list(set_ns)

    # STEP 2: Changing keys for every object according to occurence
    # if use namespace, the occurence are given a namespace
    header_row = []
    ns_row = []
    n_obj = len(annotation_dict_l)
    count_k_l = [[] for i in range(n_obj)]
    annotation_dict_l_upd = [OrderedDict() for i in range(n_obj)]
    for idx_ns, ns in enumerate(set_ns):
        # Iterating by namespace to group the keys
        if not include_namespace:
            idx_ns = 0
        for i, ann_dict in enumerate(annotation_dict_l):
            for keyval in ann_dict[ns]:
                for (k, v) in keyval:
                    # Count key occurence per namespace for that object
                    n_iden = count_k_l[i].count(f"{idx_ns}#{k}")
                    count_k_l[i].append(k)
                    pad_key = f"{idx_ns}#{n_iden}${k}"
                    annotation_dict_l_upd[i][pad_key] = v
                    if pad_key not in header_row:
                        header_row.append(pad_key)
                        ns_row.append(ns)

    # STEP 3: Populating objects values
    object_rows = []
    for annotation_dict in annotation_dict_l_upd:
        obj_dict = OrderedDict((k, "") for k in header_row)
        obj_dict.update(annotation_dict)
        object_rows.append(list(obj_dict.values()))

    # Removing temporary padding
    header_row = list(map(lambda x: x[x.index("$")+1:], header_row))
    return ns_row, header_row, object_rows


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
                    obj_ancestry_l, annotation_dict_l, separator,
                    is_well, include_namespace):
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

    ns_row, header_row, object_rows = group_keyvalue_dicts(annotation_dict_l,
                                                           include_namespace)

    counter = 0
    if len(obj_ancestry_l) > 0:  # If there's anything to add at all
        # Sorting rows
        # Only sort when there are parents to group childs
        obj_name_l, obj_ancestry_l, object_rows = sort_items(obj_name_l,
                                                             obj_ancestry_l,
                                                             object_rows,
                                                             is_well)
        for (parent_type, _) in obj_ancestry_l[0]:
            header_row.insert(counter, parent_type)
            ns_row.insert(counter, "")  # padding namespace like all keys
            counter += 1
    header_row.insert(counter, "OBJECT_ID")
    header_row.insert(counter + 1, "OBJECT_NAME")
    ns_row.insert(counter, "")
    ns_row.insert(counter + 1, "")
    ns_row[0] = "namespace"  # Finalizing the namespace row
    print(f"\tColumn names: {header_row}", "\n")

    for k, (obj_id, obj_name, whole_values) in enumerate(zip(obj_id_l,
                                                             obj_name_l,
                                                             object_rows)):
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
    if include_namespace:
        tfile.write(to_csv(ns_row))
    tfile.write(to_csv(header_row))
    # write the keys values for each file
    for object_row in object_rows:
        tfile.write(to_csv(object_row))
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
    include_namespace = script_params["Include namespace"]

    is_well = False

    # One file output per given ID
    obj_ancestry_l = []
    annotation_dict_l = []
    obj_id_l, obj_name_l = [], []
    for source_object in conn.getObjects(source_type, source_ids):

        result_obj = source_object
        if source_type == "TagAnnotation":
            result_obj = None  # Attach result csv on the first object
        is_tag = source_type == "TagAnnotation"

        for target_obj in target_iterator(conn, source_object,
                                          target_type, is_tag):
            is_well = target_obj.OMERO_CLASS == "Well"
            annotation_dict_l.append(get_existing_map_annotions(target_obj,
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
                               annotation_dict_l, separator, is_well,
                               include_namespace)

    message = ("The csv is attached to " +
               f"{result_obj.OMERO_CLASS}:{result_obj.getId()}")

    return message, file_ann, result_obj


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
    Default namespace: openmicroscopy.org/omero/client/mapAnnotation
    \t
        """,  # Tabs are needed to add line breaks in the HTML

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Parent data type of the objects to annotate.",
            values=source_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="1.1",
            description="List of parent data IDs containing the objects " +
                        "to delete annotation from.").ofType(rlong(0)),

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
            values=separators, default="TAB"),

        scripts.Bool(
            "Include column(s) of parents name", optional=False,
            grouping="2.2",
            description="Weather to include or not the name of the parent(s)" +
                        " objects as columns in the .csv.", default=False),

        scripts.Bool(
            "Include namespace", optional=False,
            grouping="2.3",
            description="Weather to include or not the namespace" +
                        " of the annotations in the .csv.", default=False),

        authors=["Christian Evenhuis", "MIF", "Tom Boissonnet"],
        institutions=["University of Technology Sydney", "CAi HHU"],
        contact="https://forum.image.sc/tag/omero",
    )
    try:
        params = parameters_parsing(client)
        print("Input parameters:")
        keys = ["Data_Type", "IDs", "Target Data_Type",
                "Namespace (leave blank for default)",
                "Separator", "Include column(s) of parents name",
                "Include namespace"]
        for k in keys:
            print(f"\t- {k}: {params[k]}")
        print("\n####################################\n")

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        message, fileann, res_obj = main_loop(conn, params)
        client.setOutput("Message", rstring(message))

        href = f"{WEBCLIENT_URL}/download_original_file/{fileann.getId()}"
        if res_obj is not None and fileann is not None:
            if WEBCLIENT_URL != "":
                url = omero.rtypes.wrap({
                    "type": "URL",
                    "href": href,
                    "title": "CSV file of Key-Value pairs",
                })
                client.setOutput("URL", url)
            else:
                client.setOutput("Result", robject(res_obj._obj))

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

    if params["Target Data_Type"] == "<on current>":
        params["Target Data_Type"] = params["Data_Type"]
    elif " " in params["Target Data_Type"]:
        # Getting rid of the trailing '---' added for the UI
        params["Target Data_Type"] = params["Target Data_Type"].split(" ")[1]

    assert params["Target Data_Type"] in ALLOWED_PARAM[params["Data_Type"]], \
           (f"{params['Target Data_Type']} is not a valid target for " +
            f"{params['Data_Type']}.")

    if params["Separator"] == "TAB":
        params["Separator"] = "\t"

    if params["Data_Type"] == "Tag":
        params["Data_Type"] = "TagAnnotation"

    if params["Data_Type"] == "Run":
        params["Data_Type"] = "Acquisition"
    if params["Target Data_Type"] == "Run":
        params["Target Data_Type"] = "PlateAcquisition"

    return params


if __name__ == "__main__":
    run_script()
