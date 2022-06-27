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

from omero.util.populate_roi import DownloadingOriginalFileProvider

from collections import OrderedDict


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
            if (file_ann_id is None and file_name.endswith(".csv")) or (
                    ann.getId() == file_ann_id):
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


def get_children_by_name(omero_obj):

    images_by_name = {}
    wells_by_name = {}

    if omero_obj.OMERO_CLASS == "Dataset":
        for img in omero_obj.listChildren():
            img_name = img.getName()
            if img_name in images_by_name:
                sys.stderr.write("File names not unique: {}".format(img_name))
                sys.exit(1)
            images_by_name[img_name] = img
    elif omero_obj.OMERO_CLASS == "Plate":
        for well in omero_obj.listChildren():
            label = well.getWellPos()
            wells_by_name[label] = well
            for ws in well.listChildren():
                img = ws.getImage()
                img_name = img.getName()
                if img_name in images_by_name:
                    sys.stderr.write(
                        "File names not unique: {}".format(img_name))
                    sys.exit(1)
                images_by_name[img_name] = img
    else:
        sys.stderr.write(f'{omero_obj.OMERO_CLASS} objects not supported')

    return images_by_name, wells_by_name


def keyval_from_csv(conn, script_params):
    data_type = script_params["Data_Type"]
    ids = script_params["IDs"]

    nimg_processed = 0
    nimg_updated = 0
    missing_names = 0

    for target_object in conn.getObjects(data_type, ids):

        # file_ann_id is Optional. If not supplied, use first .csv attached
        file_ann_id = None
        if "File_Annotation" in script_params:
            file_ann_id = int(script_params["File_Annotation"])
            link_file_ann(conn, data_type, target_object.id, file_ann_id)
            print("set ann id", file_ann_id)

        original_file = get_original_file(target_object, file_ann_id)
        print("Original File", original_file.id.val, original_file.name.val)
        provider = DownloadingOriginalFileProvider(conn)

        # read the csv
        temp_file = provider.get_original_file_data(original_file)
        # Needs omero-py 5.9.1 or later
        temp_name = temp_file.name
        with open(temp_name, 'rt', encoding='utf-8-sig') as file_handle:
            try:
                delimiter = csv.Sniffer().sniff(
                    file_handle.read(500), ",;\t").delimiter
                print("Using delimiter: ", delimiter,
                      " after reading 500 characters")
            except Exception:
                file_handle.seek(0)
                try:
                    delimiter = csv.Sniffer().sniff(
                        file_handle.read(1000), ",;\t").delimiter
                    print("Using delimiter: ", delimiter,
                          " after reading 1000 characters")
                except Exception:
                    file_handle.seek(0)
                    try:
                        delimiter = csv.Sniffer().sniff(
                            file_handle.read(2000), ";,\t").delimiter
                        print("Using delimiter: ", delimiter,
                              " after reading 2000 characters")
                    except Exception:
                        print("Failed to sniff delimiter, using ','")
                        delimiter = ","
            # reset to start and read whole file...
            file_handle.seek(0)
            data = list(csv.reader(file_handle, delimiter=delimiter))

        # keys are in the header row
        header = data[0]
        print("header", header)

        # create dictionaries for well/image name:object
        images_by_name, wells_by_name = get_children_by_name(target_object)
        nimg_processed += len(images_by_name)

        image_index = header.index("image") if "image" in header else -1
        well_index = header.index("well") if "well" in header else -1
        plate_index = header.index("plate") if "plate" in header else -1
        if image_index == -1:
            # first header is the img-name column, if 'image' not found
            image_index = 0
        print("image_index:", image_index, "well_index:", well_index,
              "plate_index:", plate_index)
        rows = data[1:]

        # loop over csv rows...
        for row in rows:
            # try to find 'image', then 'well', then 'plate'
            image_name = row[image_index]
            well_name = None
            plate_name = None
            obj = None
            if len(image_name) > 0:
                if image_name in images_by_name:
                    obj = images_by_name[image_name]
                    print("Annotating Image:", obj.id, image_name)
                else:
                    missing_names += 1
                    print("Image not found:", image_name)
            if obj is None and well_index > -1 and len(row[well_index]) > 0:
                well_name = row[well_index]
                if well_name in wells_by_name:
                    obj = wells_by_name[well_name]
                    print("Annotating Well:", obj.id, well_name)
                else:
                    missing_names += 1
                    print("Well not found:", well_name)
            # always check that Plate name matches if it is given:
            if data_type == "Plate" and plate_index > -1 and \
                    len(row[plate_index]) > 0:
                if row[plate_index] != target_object.name:
                    print("plate", row[plate_index],
                          "doesn't match object", target_object.name)
                    continue
                if obj is None:
                    obj = target_object
                    print("Annotating Plate:", obj.id, plate_name)
            if obj is None:
                msg = "Can't find object by image, well or plate name"
                print(msg)
                continue

            cols_to_ignore = [image_index, well_index, plate_index]
            updated = annotate_object(conn, obj, header, row, cols_to_ignore)
            if updated:
                nimg_updated += 1

    message = "Added kv pairs to {}/{} files".format(
        nimg_updated, nimg_processed)
    if missing_names > 0:
        message += f". {missing_names} image names not found."
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

    data_types = [rstring('Dataset'), rstring('Plate')]
    client = scripts.client(
        'Add_Key_Val_from_csv',
        """
    This script processes a csv file, attached to a Dataset
        """,
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=data_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="Dataset or Plate ID(s).").ofType(rlong(0)),

        scripts.String(
            "File_Annotation", grouping="3",
            description="File ID containing metadata to populate."),

        authors=["Christian Evenhuis"],
        institutions=["MIF UTS"],
        contact="https://forum.image.sc/tag/omero"
    )

    try:
        # process the list of args above.
        script_params = {}
        for key in client.getInputKeys():
            if client.getInput(key):
                script_params[key] = client.getInput(key, unwrap=True)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        print("script params")
        for k, v in script_params.items():
            print(k, v)
        message = keyval_from_csv(conn, script_params)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
