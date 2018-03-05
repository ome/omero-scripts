#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 MIF/Key_Val_from_FileName.py

 Adds key-value (kv) metadata to images in a dataset in two ways:
    1. at the file level kv from parsing the filename
    2. common set of kv pairs from the dataset desciption
 The information is found by parsing the Description text for the data set

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

import sys, os
import re

from omero.gateway import BlitzGateway
import omero
from omero.cmd import Delete2
from omero.rtypes import rlong, rstring, robject
import omero.scripts as scripts
import copy
from collections import OrderedDict

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def GetExistingMapAnnotions( obj ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
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
def AddKeysToMatchingFiles( conn, Id, global_kv, template, file_keys, spec_kv=None ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    dataset = conn.getObject("Dataset",Id)

    # compile the regexp
    if( template is not None ):
        template="^{}$".format(template)
        template= template.replace("*","([^\s_\/]+)")
        template= template.replace("?","[^\s_\/]")
        regexp = re.compile(template)

    # add the metadata to the images
    nimg=dataset.countChildren()
    nimg_updated=0
    nkv_added=0
    for image in dataset.listChildren():
        if( not ( image.canAnnotate() and image.canLink() ) ):
            message = "You don't have permission to add annotations to {}".format(image.getName())
            client.setOutput("Message", rstring(message) )
            return

        existing_kv = GetExistingMapAnnotions(image)
        updated_kv  = copy.deepcopy(existing_kv)
        for key,vals in global_kv.iteritems():
            if key not in updated_kv: updated_kv[key] = set()
            for val in vals:
                updated_kv[key].add(val)

        if( template is not None ):
            # apply the template to the file name
            name = image.getName()

            # this adds directory path to filename
            # is probably better to extend name of file with path first
            #path = os.path.dirname(image.getImportedImageFilePaths()['client_paths'][0])
            #filename = path+"/"+name

            filename=name
            match = regexp.search(filename)

            if( match is not None ):
                print("Match found",filename)
                for i,val in enumerate(match.groups()):
                    i1 = i
                    if( i1 in file_keys ):
                        key = file_keys[i1]
                        if key not in updated_kv: updated_kv[key] = set()
                        updated_kv[key].add(val)

                if( spec_kv is not None ):
                    for key,vals in spec_kv.iteritems():
                        if key not in updated_kv: updated_kv[key] = set()
                        for val in vals:
                            updated_kv[key].add(val)


        #print("existing_kv")
        #for k,v in existing_kv.iteritems():
        #    print("  {} : {}".format(k,v))
        #print("updated_kv")
        #for k,v in updated_kv.iteritems():
        #    print("  {} : {}".format(k,v))
        #print("Are they the same?",existing_kv == updated_kv )
        nold = sum(map( len, existing_kv.values()))
        nnew = sum(map( len, updated_kv.values()))


        if( existing_kv != updated_kv ):
            RemoveMapAnnotations( conn, 'image', image.getId()  )
            map_ann = omero.gateway.MapAnnotationWrapper(conn)
            namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION
            map_ann.setNs(namespace)
            # convert the ordered dict to a list of lists
            kv_list=[]
            for k,vset in updated_kv.iteritems():
                for v in vset:
                    kv_list.append( [k,v] )
            map_ann.setValue( kv_list )
            map_ann.save()
            image.linkAnnotation(map_ann)

            nimg_updated = nimg_updated+1

    return nimg_updated,nold,nnew


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def AddMapAnnotations(conn, dtype, Id ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    ''' 
    * Reads information from the 'Dataset Details' field, 
    * constructs key-val data 
    * attaches it to the dataset and the images contained in it
    '''
    dataset = conn.getObject(dtype,int(Id))
    if( not ( dataset.canAnnotate() and dataset.canLink() ) ):
        message = "You don't have permission to add annotations to {}".format(dataset.getName()) 
        client.setOutput("Message", rstring(message) )
        return 

    description = dataset.getDescription().splitlines()

    modes ={"Summary"            : "default" , 
            "global key-value"   : "global"  ,
            "filename key-value" : "filename",
            "end key-value"      : "default"  }
    mode = 'default'

    global_kv = OrderedDict()   # stores the global key value pairs
    file_keys = OrderedDict()   # stores the 'slot' and key for the file keys
    spec_kv   = OrderedDict()   # stores the file specific kv's
    template  = None 

    nimg_updated=0
    nkv_tot=0
    for line in description:
        # 1. See if this is a mode string
        for key,value in modes.iteritems():
            match = re.search( "^#\s+{}".format(key),line.lower())
            if( match is not None ):
                print(">>>",mode,value)
                # start a new filename block
                if( mode!='filename' and value=='filename' ):
                    file_keys = OrderedDict()
                    spec_kv = OrderedDict()
                    template  = None



                # end a filename block
                if( mode=='filename' and value!='filename' ):
                    print("Trigger parse fileanames")
                    print(spec_kv)
                    nimg_up,nold,nnew = AddKeysToMatchingFiles( conn, Id, OrderedDict(), template, file_keys, spec_kv )
                    nimg_updated=nimg_updated+nimg_up
                    nkv_tot = nkv_tot + nnew-nold
                    print("filename {} {}".format(nimg_up,nold,nnew))
                if( mode=='global' and value!='global' ):                
                    # Add globals to all the images
                    nimg_up, nold, nnew =  AddKeysToMatchingFiles( conn, Id, global_kv, None, file_keys )
                    print("Global:  {}  {}".format(nimg_up,nnew-nold))

                mode = value
                continue

        if( mode == 'default' ):
            pass

        if( mode == 'global' ):
            # split the line for the kay value pair
            match = re.search("^\s*(\S+)\s*:\s*(\S+)",line)
            if( match is not None ):
                key = match.group(1)
                val = match.group(2)
                if( key not in global_kv ): global_kv[key]=set()
                global_kv[key].add(val)

        if( mode == 'filename' ):
             # the template
             match = re.search( "^\s*(\S+)\s+(\S+)",line)
             if( match and (match.group(1).lower()=='template') ):
                 template = match.group(2)
                 print("New template {}".format(template) )


             # file templated kvs
                           # Start line
                           #    | /----white space
                           #    | |full stop|    
                           #    V V      V  V        
             match = re.search("^\s*(\d)\.\s+(\S+)",line)
                           #          ^        ^           
                           #       position   key
             if( match is not None ):
                 i = int(match.group(1))-1
                 file_keys[i] = match.group(2)

             # file specific kvs
             match = re.search("^\s*(\S+)\s*:\s*(\S+)",line)
             if( match is not None ):
                 key = match.group(1)
                 val = match.group(2)
                 if( key not in spec_kv ): spec_kv[key]=set()
                 spec_kv[key].add(val)
    #print("Global k-v's")
    #for k,v in global_kv.iteritems():
    #    print( k,v)

    # now add the key value pairs to the dataset
    existing_kv = GetExistingMapAnnotions(dataset)
    if( existing_kv != global_kv ):
        RemoveMapAnnotations( conn, 'dataset', dataset.getId()  )
        map_ann = omero.gateway.MapAnnotationWrapper(conn)
        namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION
        map_ann.setNs(namespace)    
        # convert the ordered dict to a list of lists
        kv_list=[]
        for k,vset in global_kv.iteritems():
            for v in vset:
                kv_list.append( [k,v] )
        map_ann.setValue( kv_list )        
        map_ann.save()
        dataset.linkAnnotation(map_ann)



    # add the metadata to the images
    if( True ):  
        #AddKeysToMatchingFiles( conn, Id, global_kv, template, file_keys )    
        return "Added a total of {} kv pairs to {}/{} files  ".format(nkv_tot,nimg_updated,len(list(dataset.listChildren())))

    else:
        nimg=dataset.countChildren()
        nimg_updated=0
        nkv_tot=0
        for image in dataset.listChildren():
            if( not ( image.canAnnotate() and image.canLink() ) ):
                message = "You don't have permission to add annotations to {}".format(image.getName()) 
                client.setOutput("Message", rstring(message) )
                return 

            existing_kv = GetExistingMapAnnotions(image)
            updated_kv  = copy.deepcopy(global_kv)

            if( template is not None ): 
                # apply the template to the file name
                name = image.getName()
                path = os.path.dirname(image.getImportedImageFilePaths()['client_paths'][0])
                filename = path+"/"+name
                match = regexp.search(filename)

                if( match is not None ):
                    for i,val in enumerate(match.groups()):
                        i1 = i+1
                        if( i1 in file_keys ):
                            key = file_keys[i1]
                            if key not in updated_kv: updated_kv[key] = set()
                            updated_kv[key].add(val)

            print("existing_kv")
            for k,v in existing_kv.iteritems():
                print("  {} : {}".format(k,v))             
            print("updated_kv")
            for k,v in updated_kv.iteritems():
                print("  {} : {}".format(k,v))    
            print("Are they the same?",existing_kv == updated_kv )


            if( existing_kv != updated_kv ):
                print("The key-values pairs are different")
                RemoveMapAnnotations( conn, 'image', image.getId()  )
                map_ann = omero.gateway.MapAnnotationWrapper(conn)
                namespace = omero.constants.metadata.NSCLIENTMAPANNOTATION
                map_ann.setNs(namespace)
                # convert the ordered dict to a list of lists
                kv_list=[]
                for k,vset in updated_kv.iteritems():
                    for v in vset:
                        kv_list.append( [k,v] )            
                map_ann.setValue( kv_list )
                map_ann.save()
                image.linkAnnotation(map_ann)

                nimg_updated=nimg_updated+1
                nkv_tot = nkv_tot+len(updated_kv)-len(existing_kv)
        return "Added a total of {} kv pairs to {}/{} files  ".format(nkv_tot,nimg_updated,nimg)


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
        'Key_Val_from_Description.py',
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
            message = AddMapAnnotations( conn, 'Dataset', ds.getId() )
            client.setOutput("Message", rstring(message))


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
