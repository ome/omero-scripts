#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 MIF/Remove_Key_Value.py"

 Remove all key-value  pairs from:
   * selected image(s)
   * selected dataset(s) and the images contained in them

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
@version 4.4
@since 4.4

"""
from __future__ import print_function


from omero.gateway import BlitzGateway
import omero
from omero.cmd import Delete2
from omero.rtypes import rlong, rstring, robject
import omero.scripts as scripts

import re

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def RemoveMapAnnotations(conn, dtype, Id ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    obj = conn.getObject(dtype,int(Id))
    name = obj.getName()

    anns = list( obj.listAnnotations())
    mapann_ids = [ann.id for ann in anns
         if isinstance(ann, omero.gateway.MapAnnotationWrapper) ]

    print(mapann_ids )
    try:
        delete = Delete2(targetObjects={'MapAnnotation': mapann_ids})
        handle = conn.c.sf.submit(delete)
        conn.c.waitOnCmd(handle, loops=10, ms=500, failonerror=True,
                     failontimeout=False, closehandle=False)
        return 0
    except Exception, ex:
        print("Failed to delete links: {} ".format(ex.message) )
        return 1
    return

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def getObjects(conn, scriptParams):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    """
    File the list of objects
    @param conn:             Blitz Gateway connection wrapper
    @param scriptParams:     A map of the input parameters
    """
    # we know scriptParams will have "Data_Type" and "IDs" since these
    # parameters are not optional
    dataType = scriptParams["Data_Type"]
    ids      = scriptParams["IDs"]

    # dataType is 'Dataset' or 'Image' so we can use it directly in
    # getObjects()
    objs = list(conn.getObjects(dataType, ids))   # generator of images or datasets

    if len(objs) == 0:
        print("No {} found for specified IDs".format(dataType) )
        return 


    objs_ret = []

    if dataType == 'Dataset':
        for ds in objs:
            print("Processing Images from Dataset: {}".format(ds.getName()) )
            objs_ret.append( ds )
            imgs = list(ds.listChildren())
            objs_ret.extend(imgs)
    else:
        print("Processing Images identified by ID")
        objs_ret= objs

    return objs_ret


if __name__ == "__main__":
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    dataTypes = [rstring('Dataset'),rstring('Image')] # only works on datasets
  

    # Here we define the script name and description.
    # Good practice to put url here to give users more guidance on how to run
    # your script.
    client = scripts.client(
        'Remove_Key_Value.py',
        ("Remove key-value pairs from"
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

        version="0.1",
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
        objs  = getObjects(conn, scriptParams)

        nfailed = 0
        for obj in objs:
            print("Processing : {}".format(obj.getName() ))
            ret = RemoveMapAnnotations( conn, obj.OMERO_CLASS, obj.getId() )
            nfailed = nfailed + ret


        ## now handle the result, displaying message and returning image if
        ## appropriate
        nobjs = len(objs)
        message = "Key value data deleted from  {} of {} files".format( nobjs-nfailed, nobjs)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()
