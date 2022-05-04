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


def attach_csv_file(conn, obj, data):
    ''' writes the data (list of dicts) to a file
    and attaches it to the object
        conn : connection to OMERO (need to annotation creation
        obj  : the object to attach the file file to
        data : the data
    '''
    # create the tmp directory
    tmp_dir = tempfile.mkdtemp(prefix='MIF_meta')
    (fd, tmp_file) = tempfile.mkstemp(dir=tmp_dir, text=True)
    tfile = os.fdopen(fd, 'w')

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
    header = ['filename']
    for key, count in key_union.items():
        header.extend([key] * count)      # keys can repeat multiple times
    tfile.write(to_csv(header))

    # write the keys values for each file
    for filename, kv_dict in data.items():
        row = [""] * len(header)   # empty row
        row[0] = filename
        for key, vset in kv_dict.items():
            n0 = header.index(key)     # first occurence of key in header
            for i, val in enumerate(vset):
                row[n0 + i] = val
        tfile.write(to_csv(row))
    tfile.close()

    name = "{}_metadata_out.csv".format(obj.getName())
    # link it to the object
    ann = conn.createFileAnnfromLocalFile(
        tmp_file, origFilePathAndName=name,
        ns='MIF_test')
    ann = obj.linkAnnotation(ann)

    # remove the tmp file
    os.remove(tmp_file)
    os.rmdir(tmp_dir)
    return "done"


def run_script():

    data_types = [rstring('Dataset')]
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
            description="Plate or Screen ID.").ofType(rlong(0)),


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

        data_type = script_params["Data_Type"]
        print(data_type)
        ids = script_params["IDs"]
        datasets = list(conn.getObjects(data_type, ids))
        print(ids)
        print("datasets:")
        print(datasets)
        for ds in datasets:
            # name of the file
            csv_name = "{}_metadata_out.csv".format(ds.getName())
            print(csv_name)

            # remove the csv if it exists
            for ann in ds.listAnnotations():
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
            for img in ds.listChildren():
                fn = img.getName()
                kv_dict[fn] = get_existing_map_annotions(img)

            # attach the data
            mess = attach_csv_file(conn, ds, kv_dict)
            print(mess)
        mess = "done"
        client.setOutput("Message", rstring(mess))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
