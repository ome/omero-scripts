# coding=utf-8
"""
 Import_from_csv.py

 Adds key-value pairs to a target object on OMERO from a CSV file.

-----------------------------------------------------------------------------
  Copyright (C) 2018 - 2024
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
from omero.gateway import BlitzGateway, TagAnnotationWrapper
from omero.rtypes import rstring, rlong, robject
import omero.scripts as scripts
from omero.constants.metadata import NSCLIENTMAPANNOTATION, NSINSIGHTTAGSET
from omero.model import AnnotationAnnotationLinkI
from omero.util.populate_roi import DownloadingOriginalFileProvider

import csv
from collections import defaultdict, OrderedDict
import re


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
    "Screen": ["Screen", "Plate", "Well", "Acquisition", "Image"],
    "Plate": ["Plate", "Well", "Acquisition", "Image"],
    "Well": ["Well", "Image"],
    "Acquisition": ["Acquisition", "Image"],
    "Tag": ["Project", "Dataset", "Image",
            "Screen", "Plate", "Well", "Acquisition"]
}

P_DTYPE = "Data_Type"  # Do not change
P_FILE_ANN = "File_Annotation"  # Do not change
P_IDS = "IDs"  # Do not change
P_TARG_DTYPE = "Target Data_Type"
P_NAMESPACE = "Namespace (blank for default or from csv)"
P_CSVSEP = "CSV separator"
P_EXCL_COL = "Columns to exclude"
P_TARG_COLID = "Target ID colname"
P_TARG_COLNAME = "Target name colname"
P_EXCL_EMPTY = "Exclude empty values"
P_ATTACH = "Attach CSV file"
P_SPLIT_CELL = "Split values on"
P_IMPORT_TAGS = "Import tags"
P_OWN_TAG = "Only use personal tags"
P_ALLOW_NEWTAG = "Allow tag creation"


def get_obj_name(omero_obj):
    """ Helper function """
    if omero_obj.OMERO_CLASS == "Well":
        return omero_obj.getWellPos().upper()
    else:
        return omero_obj.getName()


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
        if target_obj.canAnnotate():
            print(f"\t- {target_obj}")
            yield target_obj
        else:
            print(f"\t- Annotate {target_obj} is not permitted, skipping")
    print()


def main_loop(conn, script_params):
    """
    Startup:
     - Find CSV and read
    For every object:
     - Gather name and ID
    Finalize:
     - Find a match between CSV rows and objects
     - Annotate the objects
     - (opt) attach the CSV to the source object
    """
    source_type = script_params[P_DTYPE]
    target_type = script_params[P_TARG_DTYPE]
    source_ids = script_params[P_IDS]
    file_ids = script_params[P_FILE_ANN]
    namespace = script_params[P_NAMESPACE]
    to_exclude = script_params[P_EXCL_COL]
    target_id_colname = script_params[P_TARG_COLID]
    target_name_colname = script_params[P_TARG_COLNAME]
    separator = script_params[P_CSVSEP]
    attach_file = script_params[P_ATTACH]
    exclude_empty_value = script_params[P_EXCL_EMPTY]
    split_on = script_params[P_SPLIT_CELL]
    use_personal_tags = script_params[P_OWN_TAG]
    create_new_tags = script_params[P_ALLOW_NEWTAG]
    import_tags = script_params[P_IMPORT_TAGS]
    file_ann_multiplied = script_params["File_Annotation_multiplied"]

    ntarget_processed = 0
    ntarget_updated = 0
    missing_names = set()
    processed_names = set()
    total_missing_names = 0

    result_obj = None

    # Dictionaries needed for the tags
    tag_d, tagset_d, tagtree_d, tagid_d = None, None, None, None

    # One file output per given ID
    source_objects = conn.getObjects(source_type, source_ids)
    for source_object, file_ann_id in zip(source_objects, file_ids):
        ntarget_updated_curr = 0
        if file_ann_id is not None:
            file_ann = conn.getObject("Annotation", oid=file_ann_id)
            assert file_ann is not None, f"Annotation {file_ann_id} not found"
            assert file_ann.OMERO_TYPE == omero.model.FileAnnotationI, \
                ("The provided annotation ID must reference a " +
                 f"FileAnnotation, not a {file_ann.OMERO_TYPE}")
        else:
            file_ann = get_original_file(source_object)
        original_file = file_ann.getFile()._obj

        rows, header, namespaces = read_csv(conn, original_file,
                                            separator, import_tags)
        if namespace is not None:
            namespaces = [namespace] * len(header)
        elif len(namespaces) == 0:
            namespaces = [NSCLIENTMAPANNOTATION] * len(header)

        is_tag = source_type == "TagAnnotation"
        target_obj_l = target_iterator(conn, source_object,
                                       target_type, is_tag)

        # Index of the column used to identify the targets. Try for IDs first
        idx_id, idx_name = -1, -1
        if target_id_colname in header:
            idx_id = header.index(target_id_colname)
        if target_name_colname in header:
            idx_name = header.index(target_name_colname)
        cols_to_ignore = [header.index(el) for el in to_exclude
                          if el in header]

        assert (idx_id != -1) or (idx_name != -1), \
            ("Neither the column for the objects' name or" +
             " the objects' index were found")

        use_id = idx_id != -1  # use the obj_idx column if exist
        if not use_id:
            idx_id = idx_name
            # check if the names in the .csv contain duplicates
            name_list = [row[idx_id] for row in rows]
            duplicates = {name for name in name_list
                          if name_list.count(name) > 1}
            print("duplicates:", duplicates)
            assert not len(duplicates) > 0, \
                (f"The .csv contains duplicates {duplicates} which makes" +
                 " it impossible to correctly allocate the annotations.")

            # Identify target-objects by name fail if two have identical names
            target_d = dict()
            for target_obj in target_obj_l:
                name = get_obj_name(target_obj)
                assert name not in target_d.keys(), \
                    ("Target objects identified by name have at " +
                     f"least one duplicate: {name}")
                target_d[name] = target_obj
        else:
            # Setting the dictionnary target_id:target_obj
            # keys as string to match CSV reader output
            target_d = {str(target_obj.getId()): target_obj
                        for target_obj in target_obj_l}
        ntarget_processed += len(target_d)

        if tag_d is None and "tag" in [h.lower() for h in header]:
            # Create the tag dictionary a single time if needed
            tag_d, tagset_d, tagtree_d, tagid_d = get_tag_dict(
                conn, use_personal_tags
            )
        # Replace the tags in the CSV by the tag_id to use
        rows, tag_d, tagset_d, tagtree_d, tagid_d = preprocess_tag_rows(
            conn, header, rows, tag_d, tagset_d, tagtree_d, tagid_d,
            create_new_tags, split_on
        )

        ok_idxs = [i for i in range(len(header)) if i not in cols_to_ignore]
        for row in rows:
            # Iterate the CSV rows and search for the matching target
            target_id = row[idx_id]
            # skip empty rows
            if target_id == "":
                continue
            if target_id in target_d.keys():
                target_obj = target_d[target_id]
                # add name/id to processed set
                if file_ann_multiplied:
                    processed_names.add(target_id)
            else:
                # add name/id to missing set
                if file_ann_multiplied:
                    missing_names.add(target_id)
                else:
                    total_missing_names += 1
                    print(f"Not found: {target_id}")
                continue

            if split_on != "":
                parsed_row, parsed_ns, parsed_head = [], [], []
                for i in ok_idxs:
                    curr_vals = row[i].strip().split(split_on)
                    parsed_row.extend(curr_vals)
                    parsed_ns.extend([namespaces[i]] * len(curr_vals))
                    parsed_head.extend([header[i]] * len(curr_vals))
            else:
                parsed_row = [row[i] for i in ok_idxs]
                parsed_ns = [namespaces[i] for i in ok_idxs]
                parsed_head = [header[i] for i in ok_idxs]

            updated = annotate_object(
                conn, target_obj, parsed_row, parsed_head,
                parsed_ns, exclude_empty_value, tagid_d, split_on
            )

            if updated:
                if result_obj is None:
                    result_obj = target_obj
                ntarget_updated += 1
                ntarget_updated_curr += 1

        if ntarget_updated_curr > 0 and attach_file:
            # Only attaching if this is successful
            link_file_ann(conn, source_type, source_object, file_ann)
        print("\n------------------------------------\n")

    message = f"Added Annotations to \
        {ntarget_updated}/{ntarget_processed} {target_type}(s)"

    if file_ann_multiplied and len(missing_names) > 0:
        # subtract the processed names/ids from the
        # missing ones and print the missing names/ids
        missing_names = missing_names - processed_names
        if len(missing_names) > 0:
            print(f"Not found: {missing_names}")
        total_missing_names = len(missing_names)

    if total_missing_names > 0:
        message += f". {total_missing_names} {target_type}(s) not found \
            (using {'ID' if use_id else 'name'} to identify them)."

    return message, result_obj


def get_original_file(omero_obj):
    """Find last AnnotationFile linked to object if no annotation is given"""
    file_ann = None
    for ann in omero_obj.listAnnotations():
        if ann.OMERO_TYPE == omero.model.FileAnnotationI:
            file_name = ann.getFile().getName()
            # Pick file by Ann ID (or name if ID is None)
            if file_name.endswith(".csv") or file_name.endswith(".tsv"):
                if (file_ann is None) or (ann.getDate() > file_ann.getDate()):
                    # Get the most recent file
                    file_ann = ann

    assert file_ann is not None, \
        (f"No .csv FileAnnotation was found on {omero_obj.OMERO_CLASS}" +
         f":{get_obj_name(omero_obj)}:{omero_obj.getId()}")

    return file_ann


def read_csv(conn, original_file, delimiter, import_tags):
    """ Dedicated function to read the CSV file """
    print("Using FileAnnotation",
          f"{original_file.id.val}:{original_file.name.val}")
    provider = DownloadingOriginalFileProvider(conn)
    # read the csv
    # Needs omero-py 5.9.1 or later

    try:
        temp_file = provider.get_original_file_data(original_file)
        with open(temp_file.name, mode="rt", encoding='utf-8') as f:
            csv_content = f.readlines()
    except UnicodeDecodeError as e:
        assert False, ("Error while reading the csv, convert your " +
                       "file to utf-8 encoding" +
                       str(e))

    if delimiter is None:
        try:
            # Sniffing on a maximum of four lines
            delimiter = csv.Sniffer().sniff("\n".join(csv_content[:4]),
                                            ",;\t").delimiter
        except Exception as e:
            assert False, ("Failed to sniff CSV delimiter: " + str(e))
    rows = list(csv.reader(csv_content, delimiter=delimiter))

    rowlen = len(rows[0])
    error_msg = (
        "CSV rows lenght mismatch: Header has {} " +
        "items, while line {} has {}"
    )
    for i in range(1, len(rows)):
        assert len(rows[i]) == rowlen, error_msg.format(
            rowlen, i, len(rows[i])
        )

    # keys are in the header row (first row for no namespaces
    # second row with namespaces declared)
    namespaces = []
    if rows[0][0].lower() == "namespace":
        namespaces = [el.strip() for el in rows[0]]
        namespaces = [ns if ns else NSCLIENTMAPANNOTATION for ns in namespaces]
        rows = rows[1:]
    header = [el.strip() for el in rows[0]]
    rows = rows[1:]

    if not import_tags:
        idx_l = [i for i in range(len(header)) if header[i].lower() != "tag"]
        header = [header[i] for i in idx_l]
        namespaces = [namespaces[i] for i in idx_l]
        for j in range(len(rows)):
            rows[j] = [rows[j][i] for i in idx_l]

    print(f"Header: {header}\n")
    return rows, header, namespaces


def annotate_object(conn, obj, row, header, namespaces,
                    exclude_empty_value, tagid_d, split_on):
    updated = False
    print(f"-->processing {obj}")
    for curr_ns in list(OrderedDict.fromkeys(namespaces)):
        updated = False
        kv_list = []
        tag_id_l = []
        for ns, h, r in zip(namespaces, header, row):
            if ns == curr_ns and (len(r) > 0 or not exclude_empty_value):
                if h.lower() == "tag":
                    if r == "":
                        continue
                    # check for "tag" in header and create&link a TagAnnotation
                    if split_on == "":  # Default join for tags is ","
                        tag_id_l.extend(r.split(","))
                    else:  # given split_on is used (ahead of this function)
                        tag_id_l.append(r)
                else:
                    kv_list.append([h, r])
        if len(kv_list) > 0:  # Always exclude empty KV pairs
            # creation and linking of a MapAnnotation
            map_ann = omero.gateway.MapAnnotationWrapper(conn)
            map_ann.setNs(curr_ns)
            map_ann.setValue(kv_list)
            map_ann.save()
            obj.linkAnnotation(map_ann)
            print(f"MapAnnotation:{map_ann.id} created on {obj}")
            updated = True
        if len(tag_id_l) > 0:
            exist_ids = [ann.getId() for ann in obj.listAnnotations()]
            for tag_id in tag_id_l:
                tag_id = int(tag_id)
                if tag_id not in exist_ids:
                    tag_ann = tagid_d[tag_id]
                    obj.linkAnnotation(tag_ann)
                    exist_ids.append(tag_id)
                    print(f"TagAnnotation:{tag_ann.id} created on {obj}")
                    updated = True

    return updated


def get_tag_dict(conn, use_personal_tags):
    """
    Generate dictionnaries of the tags in the group.

    Parameters:
    --------------
    conn : ``omero.gateway.BlitzGateway`` object
        OMERO connection.
    use_personal_tags: ``Boolean``, indicates the use of only tags
    owned by the user.

    Returns:
    -------------
    tag_d: dictionary of tag_ids {"tagA": [12], "tagB":[34,56]}
    tagset_d: dictionary of tagset_ids {"tagsetX":[78]}
    tagtree_d: dictionary of tags in tagsets {"tagsetX":{"tagA":[12]}}
    tagid_d: dictionary of tag objects {12:tagA_obj, 34:tagB_obj}

    """
    tagtree_d = defaultdict(lambda: defaultdict(list))
    tag_d, tagset_d = defaultdict(list), defaultdict(list)
    tagid_d = {}

    max_id = -1

    uid = conn.getUserId()
    for tag in conn.getObjects("TagAnnotation"):
        is_owner = tag.getOwner().id == uid
        if use_personal_tags and not is_owner:
            continue

        tagid_d[tag.id] = tag
        max_id = max(max_id, tag.id)
        tagname = tag.getValue()
        if (tag.getNs() == NSINSIGHTTAGSET):
            # It's a tagset
            tagset_d[tagname].append((int(is_owner), tag.id))
            for lk in conn.getAnnotationLinks("TagAnnotation",
                                              parent_ids=[tag.id]):
                # Add all tags of this tagset in the tagtree
                cname = lk.child.textValue.val
                cid = lk.child.id.val
                cown = int(lk.child.getDetails().owner.id.val == uid)
                tagtree_d[tagname][cname].append((cown, cid))
        else:
            tag_d[tagname].append((int(is_owner), tag.id))

    # Sorting the tag by index (and if owned or not)
    # to keep only one
    for k, v in tag_d.items():
        v.sort(key=lambda x: (x[0]*max_id + x[1]))
        tag_d[k] = v[0][1]
    for k, v in tagset_d.items():
        v.sort(key=lambda x: (x[0]*max_id + x[1]))
        tagset_d[k] = v[0][1]
    for k1, v1 in tagtree_d.items():
        for k2, v2 in v1.items():
            v2.sort(key=lambda x: (x[0]*max_id + x[1]))
            tagtree_d[k1][k2] = v2[0][1]

    return tag_d, tagset_d, tagtree_d, tagid_d


def preprocess_tag_rows(conn, header, rows, tag_d, tagset_d,
                        tagtree_d, tagid_d,
                        create_new_tags, split_on):
    """
    Replace the tags in the rows by tag_ids.
    All done in preprocessing means that the script will fail before
    annotations process starts.
    """
    regx_tag = re.compile(r"([^\[\]]+)?(?:\[(\d+)\])?(?:\[([^[\]]+)\])?")
    update = conn.getUpdateService()

    col_idxs = [i for i in range(len(header)) if header[i].lower() == "tag"]
    res_rows = []
    for row in rows:
        for col_idx in col_idxs:
            values = row[col_idx]
            tagid_l = []
            if split_on == "":
                split_on = ","
            values = values.split(split_on)

            for val in values:
                val.strip()
                # matching a regex to the value
                re_match = regx_tag.match(val)
                if re_match is None:
                    continue
                tagname, tagid, tagset = re_match.groups()
                has_tagset = (tagset is not None and tagset != "")
                if tagid is not None:
                    # If an ID is found, take precedence
                    assert int(tagid) in tagid_d.keys(), \
                        (f"The tag ID:'{tagid}' is not" +
                         " in the permitted selection of tags")
                    tag_o = tagid_d[tagid]
                    if tagname is not None or tagname != "":
                        assert tag_o.getValue() == tagname, (
                            f"The tag {tagname} doesn't correspond" +
                            f" to the tag on the server with ID:{tagid}"
                        )
                    tagid_l.append(str(tagid))
                    # We found the tag
                    continue
                elif tagname is None or tagname == "":
                    continue

                if not has_tagset:
                    tag_exist = tagname in tag_d.keys()
                    assert (tag_exist or create_new_tags), (
                        f"The tag '{tagname}'" +
                        " does not exist while" +
                        " creation of new tags" +
                        " is not permitted"
                    )
                    if not tag_exist:
                        tag_o = TagAnnotationWrapper(conn)
                        tag_o.setValue(tagname)
                        tag_o.save()
                        tagid_d[tag_o.id] = tag_o
                        tag_d[tagname] = tag_o.id
                        print(f"creating new Tag for '{tagname}'")
                    tagid_l.append(str(tag_d[tagname]))

                else:  # has tagset
                    tagset_exist = tagset in tagset_d.keys()
                    tag_exist = (tagset_exist
                                 and (tagname in tagtree_d[tagset].keys()))
                    assert (tag_exist or create_new_tags), (
                        f"The tag '{tagname}' " +
                        f"in TagSet '{tagset}'" +
                        " does not exist while" +
                        " creation of new tags" +
                        " is not permitted"
                    )
                    if not tag_exist:
                        tag_o = TagAnnotationWrapper(conn)
                        tag_o.setValue(tagname)
                        tag_o.save()
                        tagid_d[tag_o.id] = tag_o
                        tag_d[tagname] = tag_o.id
                        if not tagset_exist:
                            tagset_o = TagAnnotationWrapper(conn)
                            tagset_o.setValue(tagset)
                            tagset_o.setNs(NSINSIGHTTAGSET)
                            tagset_o.save()
                            tagid_d[tagset_o.id] = conn.getObject("TagAnnotation", tagset_o.id)
                            tagset_d[tagset] = tagset_o.id
                            print(f"Created new TagSet {tagset}:{tagset_o.id}")
                        # else:
                        tagset_o = tagid_d[tagset_d[tagset]]
                        link = AnnotationAnnotationLinkI()
                        link.parent = tagset_o._obj
                        link.child = tag_o._obj
                        update.saveObject(link)
                        tagtree_d[tagset][tagname] = tag_o.id
                        print(f"creating new Tag for '{tagname}' " +
                              f"in the tagset '{tagset}'")
                    tagid_l.append(str(tagtree_d[tagset][tagname]))

            # joined list of tag_ids instead of ambiguous names
            row[col_idx] = split_on.join(tagid_l)
        res_rows.append(row)
    return res_rows, tag_d, tagset_d, tagtree_d, tagid_d


def link_file_ann(conn, object_type, object_, file_ann):
    """Link File Annotation to the Object, if not already linked."""
    # Check for existing links
    if object_type == "TagAnnotation":
        print("CSV file cannot be attached to the parent tag")
        return
    links = list(conn.getAnnotationLinks(
        object_type, parent_ids=[object_.getId()],
        ann_ids=[file_ann.getId()]
        ))
    if len(links) == 0:
        object_.linkAnnotation(file_ann)


def run_script():
    # Cannot add fancy layout if we want auto fill and selct of object ID
    source_types = [
                    rstring("Project"), rstring("Dataset"), rstring("Image"),
                    rstring("Screen"), rstring("Plate"), rstring("Well"),
                    rstring("Acquisition"), rstring("Image"), rstring("Tag"),
    ]

    # Duplicate Image for UI, but not a problem for script
    target_types = [
                    rstring("<on current>"), rstring("Project"),
                    rstring("- Dataset"), rstring("-- Image"),
                    rstring("Screen"), rstring("- Plate"),
                    rstring("-- Well"), rstring("-- Acquisition"),
                    rstring("--- Image")
    ]

    separators = ["guess", ";", ",", "TAB"]

    client = scripts.client(
        'Import from CSV',
        """
    Reads a .csv file to annotate the given objects with key-value pairs.
    \t
    Check the guide for more information on parameters and errors:
    https://guide-kvpairs-scripts.readthedocs.io/en/latest/index.html
    \t
    Default namespace: openmicroscopy.org/omero/client/mapAnnotation
        """,  # Tabs are needed to add line breaks in the HTML

        scripts.String(
            P_DTYPE, optional=False, grouping="1",
            description="Parent-data type of the objects to annotate.",
            values=source_types, default="Dataset"),

        scripts.List(
            P_IDS, optional=False, grouping="1.1",
            description="List of parent-data IDs containing" +
                        " the objects to annotate.").ofType(rlong(0)),

        scripts.String(
            P_TARG_DTYPE, optional=False, grouping="1.2",
            description="The data type which will be annotated. " +
                        "Entries in the .csv correspond to these objects.",
            values=target_types, default="<on current>"),

        scripts.String(
            P_FILE_ANN, optional=True, grouping="1.3",
            description="If no file is provided, list of file IDs " +
                        "containing metadata to populate (must match length" +
                        " of 'IDs'). If neither, searches the most recently " +
                        "attached CSV file on each parent object."),

        scripts.String(
            P_NAMESPACE,
            optional=True, grouping="1.4",
            description="Namespace given to the created key-value " +
                        "pairs annotations. Default is the client" +
                        "namespace, meaning editable in OMERO.web"),

        scripts.Bool(
            P_IMPORT_TAGS, optional=True, grouping="2", default=True,
            description="Untick this to prevent importing tags specified " +
                        "in the CSV."),

        scripts.Bool(
            P_OWN_TAG, grouping="2.1", default=False,
            description="Determines if tags of other users in the group" +
            " can be used on objects.\n Using only personal tags might " +
            "lead to multiple tags with the same name in one OMERO-group."),

        scripts.Bool(
            P_ALLOW_NEWTAG, grouping="2.2", default=False,
            description="Creates new tags and tagsets if the ones" +
            " specified in the .csv do not exist."),

        scripts.Bool(
            "Other parameters", optional=True, grouping="3", default=True,
            description="Ticking or unticking this has no effect"),

        scripts.Bool(
            P_EXCL_EMPTY, grouping="3.1", default=True,
            description="Exclude a key-value if the value is empty."),

        scripts.String(
            P_CSVSEP, optional=True, grouping="3.2",
            description="The separator used in the .csv file. 'guess' will " +
                        "attempt to detetect automatically which of " +
                        ",;\\t is used.",
            values=separators, default="guess"),

        scripts.String(
            P_SPLIT_CELL, optional=True, grouping="3.3",
            default="",
            description="Split cells according to this into multiple " +
                        "values for a given key."),

        scripts.List(
            P_EXCL_COL, optional=True, grouping="3.4",
            default="<ID>,<NAME>,<PARENTS>",
            description="List of columns in the .csv file to exclude " +
                        "from the key-value pair import. <ID>" +
                        " and <NAME> correspond to the two " +
                        "following parameters. <PARENTS> corresponds " +
                        "to the six container types.").ofType(rstring("")),

        scripts.String(
            P_TARG_COLID, optional=False, grouping="3.5",
            default="OBJECT_ID",
            description="The column name in the .csv containing the id" +
                        " of the objects to annotate. " +
                        "Matches <ID> in exclude parameter."),

        scripts.String(
            P_TARG_COLNAME, optional=False, grouping="3.6",
            default="OBJECT_NAME",
            description="The column name in the .csv containing the name of " +
                        "the objects to annotate (used if no column " +
                        "ID is provided or  found in the .csv). Matches " +
                        "<NAME> in exclude parameter."),

        scripts.Bool(
            P_ATTACH, grouping="3.7", default=False,
            description="Attach the given CSV to the selected objects" +
            "when not already attached to it."),

        authors=["Christian Evenhuis", "Tom Boissonnet", "Jens Wendt"],
        institutions=["MIF UTS", "CAi HHU", "MiN WWU"],
        contact="https://forum.image.sc/tag/omero",
        version="2.0.0",
    )

    try:
        params = parameters_parsing(client)

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
    params[P_FILE_ANN] = None
    params[P_NAMESPACE] = None
    params[P_SPLIT_CELL] = ""

    for key in client.getInputKeys():
        if client.getInput(key):
            params[key] = client.getInput(key, unwrap=True)

    if params[P_TARG_DTYPE] == "<on current>":
        params[P_TARG_DTYPE] = params[P_DTYPE]
    elif " " in params[P_TARG_DTYPE]:
        # Getting rid of the trailing '---' added for the UI
        params[P_TARG_DTYPE] = params[P_TARG_DTYPE].split(" ")[1]

    assert params[P_TARG_DTYPE] in ALLOWED_PARAM[params[P_DTYPE]], \
           (f"{params['Target Data_Type']} is not a valid target for " +
            f"{params['Data_Type']}.")

    if params[P_DTYPE] == "Tag":
        assert None not in params[P_FILE_ANN], \
            "File annotation ID must be given when using Tag as source"

    if ((params[P_FILE_ANN]) is not None
            and ("," in params[P_FILE_ANN])):
        # List of ID provided, have to do the split
        params[P_FILE_ANN] = params[P_FILE_ANN].split(",")
    else:
        params[P_FILE_ANN] = [int(params[P_FILE_ANN])]
    if len(params[P_FILE_ANN]) == 1:
        # Poulate the parameter with None or same ID for all source
        params[P_FILE_ANN] *= len(params[P_IDS])
        params["File_Annotation_multiplied"] = True
    params[P_FILE_ANN] = list(map(int, params[P_FILE_ANN]))

    assert len(params[P_FILE_ANN]) == len(params[P_IDS]), \
        "Number of IDs and FileAnnotation IDs must match"

    # Replacing the placeholders <ID> and <NAME> with values from params
    to_exclude = list(map(lambda x: x.replace('<ID>',
                                              params[P_TARG_COLID]),
                          params[P_EXCL_COL]))
    to_exclude = list(map(lambda x: x.replace('<NAME>',
                                              params[P_TARG_COLNAME]),
                          to_exclude))
    if "<PARENTS>" in to_exclude:
        to_exclude.remove("<PARENTS>")
        to_exclude.extend(["PROJECT", "DATASET", "SCREEN",
                           "PLATE", "RUN", "WELL"])

    params[P_EXCL_COL] = to_exclude

    assert (params[P_CSVSEP] is None
            or params[P_CSVSEP] not in params[P_SPLIT_CELL]), (
                "Cannot split cells with a character used as CSV separator"
        )

    print("Input parameters:")
    keys = [P_DTYPE, P_IDS, P_TARG_DTYPE, P_FILE_ANN,
            P_NAMESPACE, P_CSVSEP, P_EXCL_COL, P_TARG_COLID,
            P_TARG_COLNAME, P_EXCL_EMPTY, P_ATTACH, P_SPLIT_CELL,
            P_IMPORT_TAGS, P_OWN_TAG, P_ALLOW_NEWTAG]

    for k in keys:
        print(f"\t- {k}: {params[k]}")
    print("\n####################################\n")

    if params[P_CSVSEP] == "guess":
        params[P_CSVSEP] = None
    elif params[P_CSVSEP] == "TAB":
        params[P_CSVSEP] = "\t"

    if params[P_DTYPE] == "Tag":
        params[P_DTYPE] = "TagAnnotation"
    if params[P_TARG_DTYPE] == "Acquisition":
        params[P_TARG_DTYPE] = "PlateAcquisition"

    return params


if __name__ == "__main__":
    run_script()
