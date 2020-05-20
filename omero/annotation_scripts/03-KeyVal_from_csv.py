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
@author Christian Evenhuis
<a href="mailto:christian.evenhuis@gmail.com">christian.evenhuis@gmail.com</a>
@version 5.3
@since 5.3

"""

import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong
import omero.scripts as scripts
from omero.model import PlateI, ScreenI, DatasetI
from omero.rtypes import *
from omero.cmd import Delete2

import sys
import csv
import copy

# this is for downloading a temp file
from omero.util.temp_files import create_path

from omero.util.populate_roi import DownloadingOriginalFileProvider
from omero.util.populate_metadata import ParsingContext

from collections import OrderedDict



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def get_existing_MapAnnotions( obj ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    print("getting the existing kv's")
    ord_dict = OrderedDict()
    for ann in obj.listAnnotations():
        if( isinstance(ann, omero.gateway.MapAnnotationWrapper) ):
            kvs = ann.getValue()
            for k,v in kvs:
                if k not in ord_dict:
                    ord_dict[k]=set()
                ord_dict[k].add(v)
    return ord_dict

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def remove_MapAnnotations(conn, dtype, Id ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    image = conn.getObject(dtype,int(Id))
    namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION

    filename = image.getName()

    anns = list( image.listAnnotations())
    mapann_ids = [ann.id for ann in anns
         if isinstance(ann, omero.gateway.MapAnnotationWrapper) ]

    try:
        delete = Delete2(targetObjects={'MapAnnotation': mapann_ids})
        handle = conn.c.sf.submit(delete)
        conn.c.waitOnCmd(handle, loops=10, ms=500, failonerror=True,
                     failontimeout=False, closehandle=False)

    except Exception as ex:
        print("Failed to delete links: {}".format(ex.message))
    return

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def get_original_file(conn, object_type, object_id, file_ann_id=None):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    omero_object = conn.getObject("Dataset", int(object_id))
    if omero_object is None:
        sys.stderr.write("Error: Dataset does not exist.\n")
        sys.exit(1)
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


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def populate_metadata(client, conn, script_params):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    dataType = script_params["Data_Type"]
    ids      = script_params["IDs"]

    datasets = list(conn.getObjects(dataType, ids))
    for ds in datasets:
        ID = ds.getId()

        # not sure what this is doing
        file_ann_id = None
        if "File_Annotation" in script_params:
            file_ann_id = long(script_params["File_Annotation"])
            print("set ann id")

        original_file = get_original_file(
            conn, dataType, ID, file_ann_id)
        provider = DownloadingOriginalFileProvider(conn)

        # read the csv 
        file_handle = provider.get_original_file_data(original_file)
        data =list(csv.reader(file_handle,delimiter=','))   
        file_handle.close()

        # create a dictionary for image_name:id
        dict_name_id={}
        for img in ds.listChildren():
            img_name = img.getName()
            if( img_name in dict_name_id ):
                sys.stderr.write("File names not unique: {}".format(imageaname))
                sys.exit(1)
            dict_name_id[img_name] = int(img.getId())



        # keys are in the header row
        header =data[0]
        kv_data = header[1:]  # first header is the fimename columns
        rows    = data[1:]

        nimg_updated = 0
        for row in rows: # loop over images
            img_name = row[0]
            if( img_name not in dict_name_id ):
                print("Can't find filename : {}".format(img_name) )
            else:
                img_ID = dict_name_id[img_name]         # look up the ID
                img    = conn.getObject('Image',img_ID) # get the img

                existing_kv = get_existing_MapAnnotions( img )
                updated_kv  = copy.deepcopy(existing_kv)
                print("Existing kv ")
                for k,vset in existing_kv.items():
                    print(type(vset),len(vset))
                    for v in vset:
                        print(k,v)

                for i in range(1,len(row)):  # first entry is the filename
                    key = header[i].strip()
                    vals = row[i].strip().split(';')
                    if( len(vals) > 0 ):
                        for val in vals:
                            if len(val)>0 : 
                                if key not in updated_kv: updated_kv[key] = set()
                                print("adding",key,val)
                                updated_kv[key].add(val)
                          

                if( existing_kv != updated_kv ):
                    nimg_updated = nimg_updated + 1
                    print("The key-values pairs are different")
                    remove_MapAnnotations( conn, 'Image', img.getId()  )
                    map_ann = omero.gateway.MapAnnotationWrapper(conn)
                    namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION
                    map_ann.setNs(namespace)
                    # convert the ordered dict to a list of lists
                    kv_list=[]
                    for k,vset in updated_kv.items():
                        for v in vset:
                            kv_list.append( [k,v] )
                    map_ann.setValue(kv_list)
                    map_ann.save()
                    img.linkAnnotation(map_ann)                     
                else:
                    print("No change change in kv's")

    return "Added {} kv pairs to {}/{} files  ".format(len(header)-1,nimg_updated,len(dict_name_id))


def run_script():

    data_types = [rstring('Dataset')]
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
            description="Plate or Screen ID.").ofType(rlong(0)),

        scripts.String(
            "File_Annotation", grouping="3",
            description="File ID containing metadata to populate."),

        authors=["Christian Evenhuis"],
        institutions=["MIF UTS"],
        contact="christian.evenhuis@gmail.com"
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
        for k,v in script_params.items():
            print(k,v)
        message = populate_metadata(client, conn, script_params)
        client.setOutput("Message", rstring(message))
    
    except:
        pass

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
