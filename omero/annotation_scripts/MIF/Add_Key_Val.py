#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 MIF/Add_Key_Val.py

 Adds key-value (kv) metadata to images in a dataset in two ways:
    1. common set of kv pairs from the desciption
    2. at the file level kv from parsing the filename
 The information is found by parsing the description text for the data set

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
from __future__ import print_function

import re

from omero.gateway import BlitzGateway
import omero
from omero.cmd import Delete2
from omero.rtypes import rlong, rstring, robject
import omero.scripts as scripts
import copy


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def AddMapAnnotations(conn, dtype, Id ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    dataset = conn.getObject(dtype,int(Id))
    description = dataset.getDescription().splitlines()

    modes ={ "default" :"Summary",
             "global"  :"global key-value",
             "filename":"filename key-value"}
    mode = 'default'

    file_keys = {}		
    global_kv = []
    for line in description:
        # 1. See if this is a mode string
        for key,value in modes.iteritems():
            match = re.search( "^#\s+{}".format(value),line)
            if( match is not None ):
                mode = key
                continue

        if( mode == 'default' ):
            pass

        if( mode == 'global' ):
            # split the line for the kay value pair
            match = re.search("^\s*(\S+)\s*:\s*(\S+)",line)
            if( match is not None ):
                key = match.group(1)
                val = match.group(2)
                global_kv.append([key,val])

        if( mode == 'filename' ):
             match = re.search( "^\s*template\s+(\S+)",line)
             if( match is not None ):
                 template = match.group(1)
                 print(template)
                           # Start line
                           #    | /----white space
                           #    | |full stop|    
                           #    V V      V  V        
             match = re.search("^\s*(\d)\.\s+(\S+)",line)
                           #          ^        ^           
                           #       position   key
             if( match is not None ):
                 i = match.group(1)
                 file_keys[i] = match.group(2)

    # convert the template to a regexp
                                 # not white space 
                                 # or undersciore
    template= template.replace("%","([^\s_]+)")
    template= template.replace("x","[^\s_]")
    regexp = re.compile(template)

    # now add the key value pairs to the dataset
    map_ann = omero.gateway.MapAnnotationWrapper(conn)
    namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION
    map_ann.setNs(namespace)    
    map_ann.setValue(global_kv)
    map_ann.save()
    dataset.linkAnnotation(map_ann)

    # at the metadata to the images
    for image in dataset.listChildren():
        filename = image.getName()
        match = regexp.search(filename)
        file_kv = copy.deepcopy(global_kv)
        for i,key in file_keys.iteritems():
            file_kv.append( [key, match.group(int(i))] )
        map_ann = omero.gateway.MapAnnotationWrapper(conn)
        namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION
        map_ann.setNs(namespace)
        map_ann.setValue(file_kv)
        map_ann.save()
        image.linkAnnotation(map_ann)
    return

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def RemoveMapAnnotations(conn, dtype, Id ):
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

    except Exception, ex:
        print("Failed to delete links: {}".format(ex.message))
    return

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def getObjects(conn, scriptParams):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    """
    collect the object list from the script patameters
    @param conn:             Blitz Gateway connection wrapper
    @param scriptParams:     A map of the input parameters
    """
    # we know scriptParams will have "Data_Type" and "IDs" since these
    # parameters are not optional
    dataType = scriptParams["Data_Type"]
    ids      = scriptParams["IDs"]

    # dataType is 'Dataset' or 'Image' so we can use it directly in
    # getObjects()
    obs = conn.getObjects(dataType, ids)    # generator of images or datasets
    objects = list(obs)
    return objects


if __name__ == "__main__":
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    dataTypes = [rstring('Dataset')] # only works on datasets

    # Here we define the script name and description.
    # Good practice to put url here to give users more guidance on how to run
    # your script.
    client = scripts.client(
        'Add_Key_Vals.py',
        (" Adds key-value metadata pairs to images in a data set from "
         " the description for a dataset or collections of datasets"
         " k-v pairs taken from the dataset description"
         " and by parsing the filename"
         " Image IDs or by the Dataset IDs.\nSee"
         " http://www.openmicroscopy.org/site/support/omero5.2/developers/"
         "scripts/user-guide.html for the tutorial that uses this script."),

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=dataTypes,
            default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        scripts.String(
            "New_Description", grouping="3",
            description="The new description to set for each Image in the"
            " Dataset"),

        version="5.3",
        authors=["Christian Evenhuis", "MIF"],
        institutions=["University of Technology Sydney"],
        contact="christian.evenhuis@gmail.com"

    )

    try:
        scriptParams = {}
        for key in client.getInputKeys():
            if client.getInput(key):
                # unwrap rtypes to String, Integer etc
                scriptParams[key] = client.getInput(key, unwrap=True)

        print(scriptParams)   # handy to have inputs in the std-out log

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        ## do the editing...
        datasets= getObjects(conn, scriptParams)

        for ds in datasets:
            print(ds.getName())
            AddMapAnnotations( conn, 'Dataset', ds.getId() )


        ## now handle the result, displaying message and returning image if
        ## appropriate
        #if editedImgIds is None:
        #    message = "Script failed. See 'error' or 'info' for more details"
        #else:
        #    if len(editedImgIds) == 1:
        #        # image-wrapper
        #        img = conn.getObject("Image", editedImgIds[0])
        #        message = "One Image edited: %s" % img.getName()
        #        # omero.model object
        #        omeroImage = img._obj
        #        # Insight will display 'View' link to image
        #        client.setOutput("Edited Image", robject(omeroImage))
        #    elif len(editedImgIds) > 1:
        #        message = "%s Images edited" % len(editedImgIds)
        #    else:
        #        message = ("No images edited. See 'error' or 'info' for more"
        #                   " details")
        #        # Insight will display the 'Message' parameter
        #client.setOutput("Message", rstring(message))
    finally:
        client.closeSession()
