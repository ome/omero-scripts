# coding=utf-8
"""
 MIF/Create_Metadata_csv.py

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

import tempfile

import os,sys
import csv
import copy
import numpy as np
from collections import OrderedDict

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def GetExistingMapAnnotions( obj ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    ord_dict = OrderedDict()
    for ann in obj.listAnnotations():
        if( isinstance(ann, omero.gateway.MapAnnotationWrapper) ):
            kvs = ann.getValue()
            for k,v in kvs:
                ord_dict[k] = v
    return ord_dict



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def attach_csv_file( conn, obj, data ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    ''' writes the data (list of dicts) to a file
    and attaches it to the object
        conn : connection to OMERO (need to annotation creation
        obj  : the object to attach the file file to 
        data : the data
    '''
    # create the tmp directory
    tmp_dir = tempfile.mkdtemp(prefix='MIF_meta')
    (fd, tmp_file) = tempfile.mkstemp(dir=tmp_dir, text=True)

    print("tmp_dir", tmp_dir)
    #print("tmp_file",tmp_file)
    # get the union of the keys
    key_union=OrderedDict()
    for img_k,img_v in data.iteritems():
        key_union.update(img_v)

    all_keys = key_union.keys()
    def to_csv( ll ):
        nl = len(ll)
        fmstr = "{}, "*(nl-1)+"{}\n"
        return fmstr.format(*ll)
    tfile = os.fdopen(fd, 'w')

    header = ['filename']+all_keys
    tfile.write( to_csv( header ) )

    for fname,kv_dict in data.iteritems():
        row = [fname]+[ kv_dict.get(key,"") for key in all_keys ]
        tfile.write( to_csv( row ) )
    tfile.close()


    name = "{}_metadata_out.csv".format(obj.getName())
    # link it to the object
    ann = conn.createFileAnnfromLocalFile(
        tmp_file, origFilePathAndName=name,
        ns='MIF_test' )

    ann = obj.linkAnnotation(ann)

    # remove the tmp file
    os.remove(tmp_file)
    os.rmdir (tmp_dir )
    return "done"

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def run_script():
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

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

        dataType = script_params["Data_Type"]
        ids      = script_params["IDs"]
        datasets = list(conn.getObjects(dataType, ids))    # generator of images or datasets
        for ds in datasets:
            # name of the file
            csv_name = "{}_metadata_out.csv".format(ds.getName()) 
            print(csv_name)

            # check to see if the file exists
            for ann in ds.listAnnotations():
                if( isinstance(ann, omero.gateway.FileAnnotationWrapper) ):
                    if( ann.getFileName() == csv_name ):
                        # if the name matches delete it
                        try:
                            delete = Delete2(targetObjects={'FileAnnotation': [int(ann.getId())]})
                            handle = conn.c.sf.submit(delete)
                            conn.c.waitOnCmd(handle, loops=10, ms=500, failonerror=True,
                                         failontimeout=False, closehandle=False)
                            print("Deleted")
                        except Exception, ex:
                            print("Failed to delete links: {}".format(ex.message))
        
            # assemble the metadata 
            file_names = [ img.getName() for img in list(ds.listChildren()) ]
            kv_dict = OrderedDict()
            for img in ds.listChildren():
                fn = img.getName()
                im_kv =  GetExistingMapAnnotions(img)
                kv_dict[fn] = GetExistingMapAnnotions(img)

            for k,v in kv_dict.iteritems():
                print(k)
                print(v)    
 
            # attach the data
            mess = attach_csv_file( conn, ds, kv_dict )
        mess="done" 
        client.setOutput("Message", rstring(mess))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
