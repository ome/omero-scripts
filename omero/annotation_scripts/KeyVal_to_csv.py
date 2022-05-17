# coding=utf-8
"""
 MIF/Key_Val_to_csv.py

 Reads the metadata associated with the images in a dataset
 a creates a csv file attached to dataset

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

import tempfile

import csv
import os

from collections import OrderedDict


def get_existing_map_annotions(obj):
    ord_dict = OrderedDict()
    for ann in obj.listAnnotations():
        if(isinstance(ann, omero.gateway.MapAnnotationWrapper)):
            kvs = ann.getValue()
            for k, v in kvs:
                if k not in ord_dict:
                    ord_dict[k] = set()
                ord_dict[k].add(v)
    return ord_dict


def listChildren(obj, export_wells):
    children = []
    if obj.OMERO_CLASS == "Dataset":
        children = list(obj.listChildren())
    elif obj.OMERO_CLASS == "Plate":
        for well in obj.listChildren():
            if export_wells:
                children.append(well)
            else:
                for ws in well.listChildren():
                    children.append(ws.getImage())
    return children


def getName(obj):
    print("hasstr", hasattr(obj, "getWellPos"))
    if hasattr(obj, "getWellPos"):
        # Handle Wells
        return obj.getWellPos()
    else:
        return obj.getName()


def attach_csv_file(conn, obj, data, export_wells):
    ''' writes the data (list of dicts) to a file
    and attaches it to the object
        conn : connection to OMERO (need to annotation creation
        obj  : the object to attach the file file to
        data : the data
    '''
    # create the tmp directory
    tmp_dir = tempfile.mkdtemp(prefix='MIF_meta')
    (fd, tmp_file) = tempfile.mkstemp(dir=tmp_dir, text=True)

    # get the list of  keys and maximum number of occurences
    # A key can appear multiple times, for example multiple dyes can be used
    key_union = OrderedDict()
    for img_n, img_kv in data.items():
        for key, vset in img_kv.items():
            key_union[key] = max(key_union.get(key, 0), len(vset))

    # convience function to write a csv line
    def to_csv(ll):
        nl = len(ll)
        fmstr = "{}, "*(nl-1)+"{}\n"
        return fmstr.format(*ll)

    # construct the header of the CSV file
    header = ['well' if export_wells else 'image']
    for key, count in key_union.items():
        header.extend([key] * count)      # keys can repeat multiple times
    print("header", header)

    with open(fd, 'w') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        writer.writerow(header)

        # write the keys values for each file
        for filename, kv_dict in data.items():
            row = [""] * len(header)   # empty row
            row[0] = filename
            for key, vset in kv_dict.items():
                n0 = header.index(key)     # first occurence of key in header
                for i, val in enumerate(vset):
                    row[n0 + i] = val
            writer.writerow(row)

    name = "{}_metadata_out.csv".format(obj.getName())
    # link it to the object
    ann = conn.createFileAnnfromLocalFile(
        tmp_file, origFilePathAndName=name,
        ns='MIF_test')
    ann = obj.linkAnnotation(ann)

    # remove the tmp file
    os.remove(tmp_file)
    os.rmdir(tmp_dir)
    return name


def run_script():

    data_types = [rstring('Dataset'), rstring('Plate')]
    client = scripts.client(
        'Create_Metadata_csv',
        """
    This script reads the metadata attached data set and creates
    a csv file attached to the Dataset
        """,
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=data_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="Dataset or Plate ID(s).").ofType(rlong(0)),

        scripts.Bool(
            "Export_Wells", optional=True, grouping="3",
            default=False,
            description=("For Plates, export KeyValue pairs from Wells "
                         "(instead of Images)?")),


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
        print("connection made")
        print(script_params)
        export_wells = script_params.get("Export_Wells", False)

        data_type = script_params["Data_Type"]
        ids = script_params["IDs"]
        parents = list(conn.getObjects(data_type, ids))
        print(ids)
        print(parents)
        message = ""
        file_names = []
        for obj in parents:
            # name of the file
            csv_name = "{}_metadata_out.csv".format(obj.getName())
            print(csv_name)

            # remove the csv if it exists
            for ann in obj.listAnnotations():
                if(isinstance(ann, omero.gateway.FileAnnotationWrapper)):
                    if(ann.getFileName() == csv_name):
                        # if the name matches delete it
                        try:
                            delete = Delete2(
                                targetObjects={'FileAnnotation':
                                               [ann.getId()]})
                            handle = conn.c.sf.submit(delete)
                            conn.c.waitOnCmd(
                                handle, loops=10,
                                ms=500, failonerror=True,
                                failontimeout=False, closehandle=False)
                            print("Deleted existing csv")
                        except Exception as ex:
                            print("Failed to delete existing csv: {}".format(
                                ex.message))
                else:
                    print("No exisiting file")

            # assemble the metadata into an OrderedDict
            kv_dict = OrderedDict()
            for child in listChildren(obj, export_wells):
                fn = getName(child)
                print("processing...", child, fn)
                kv_dict[fn] = get_existing_map_annotions(child)

            print("kv_dict", kv_dict)
            # attach the data
            file_name = attach_csv_file(conn, obj, kv_dict, export_wells)
            file_names.append(file_name)
        if len(file_names) == 1:
            message = f"Attached {file_names[0]} to {data_type}"
        else:
            message = f"Attached {len(file_names)} files to {data_type}s"
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
