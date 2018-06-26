#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  5 10:09:13 2018

@author: evenhuis
"""
#from Parse_OMERO_Properties import datasetId, imageId, plateId

import sys
import argparse
import os
from collections import OrderedDict
import omero

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def download_dataset( conn, Id, path, orig=False, tif=False ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    ''' download a dataset from OMERO
    INPUT : conn   : the connection needs to be open
        Id     : ID of the dataset
        path   : location of local filesystem
        fmt    : "o" is orginal , "t" is tiff
    '''
   
    # get the data set
    dataset = conn.getObject('Dataset',Id)
    if( dataset==None ):
        print("Dataset ID {} not found in group".format(Id))
        sys.exit(1)
    print("here")

    # get the images
    imgs    = list(dataset.listChildren())
   
    # this is the directory to place the data in
    ds_name = dataset.getName()
    print("{}/".format(ds_name) )
    reldir  = os.path.join( path, ds_name)
    if( not os.path.isdir(reldir) ):
        os.makedirs(reldir)
    
    for img in imgs:
        print(" "*len(ds_name)+"/{}".format(img.getName()))
    
        if( orig ):
            for orig in img.getImportedImageFiles():
                name = orig.getName()
                file_path = os.path.join( reldir, name)

                print name, orig.getId(),orig.canDownload()

                if( not os.path.exists( file_path)  ):
                    with open(str(file_path), 'w') as f:
                        for chunk in orig.getFileInChunks():
                            f.write(chunk)

        if( tif ):
            name = os.path.basename(img.getName())+".ome.tif"
            file_path = os.path.join(reldir, name)
            file_size, block_gen = img.exportOmeTiff(bufsize=65536)
            with open(str(file_path), "wb") as f:
                for piece in block_gen:
                    f.write(piece)
         
    return 

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def download_file( conn, Id, reldir, new_name ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    img = conn.getObject('Image',Id)
    if( img is None ): return False

    # create the directory if it does not exist
    if( not os.path.isdir(reldir) ):
        os.makedirs(reldir)

    # dowload the files
    for orig in img.getImportedImageFiles():
        name,ext = os.path.splitext(orig.getName())
        file_path = os.path.join( reldir, new_name+ext)
        print name
        print orig.getId()
        print orig.canDownload()

        if( not os.path.exists( file_path)  ):
            with open(str(file_path), 'w') as f:
                for chunk in orig.getFileInChunks():
                    f.write(chunk)    

    # get the thumbnail
    thumb_dir = os.path.join(reldir,'thumbs')
    if( not os.path.isdir(thumb_dir) ):
        os.makedirs(thumb_dir)
        
    thumb_name = os.path.join(thumb_dir,new_name+".jpg")
    if( not os.path.exists( thumb_name ) ):
        thumb=conn.getThumbnailSet([Id],128)
        fobj = open(thumb_name, "wb") 
        fobj.write(thumb[Id])
        fobj.close() 


    return


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def setup_dict():
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    meta_dict={}
    meta_dict["@context"]=OrderedDict([
        ("@vocab", "http://schema.org/"),  
        ("schema", "http://schema.org/"),  
        ("path", "schema:path"),           
        ("identifier", "schema:identifier"),
        ("startTime", "schema:startTime"),
        ("endTime", "schema:endTime"),
        ("description", "schema:description"),
        ("dateCreated", "schema:dateCreated"),
        ("contentSize", "schema:contentSize"),
        ("creator", "schema:creator"),
        ("category", "schema:category"),
        ("fileFormat", "schema:fileFormat"),
        ("dateModified", "schema:dateModified")
    ])

    institute=OrderedDict([
        ("@id", "http://uts.edu.au"),
        ("@type", "Organization"),
        ("address", "Broadway, 2007, NSW Australia"),
        ("identifier", "http://uts.edu.au"),
        ("name", "University of Technology Sydney")
    ])
    person=OrderedDict([
        ("@id", "http://github.com/moisbo"),
        ("@type", "Person"),
        ("affiliation", {
           "@id": "http://uts.edu.au"
        }),
        ("email", "moises.sacal@uts.edu.au"),
        ("familyName", "Sacal"),
        ("givenName", "Moises"),
        ("identifier", "http://github.com/moisbo"),
        ("name", "Moises Sacal")
    ])
    crate=OrderedDict([
        ("@id", "https://dx.doi.org/10.5281/zenodo.1009240"),
        ("@type", "Dataset"),
        ("isOutputOf", "DataCrate"),
        ("contact", {
           "@id": "http://github.com/moisbo"
        }), 
        ("contentLocation", {
          "@id": "http://uts.edu.au"
        }),
        ("path", "./"),
        ("creator", {
          "@id": "http://github.com/moisbo"
        }),
        ("datePublished", "2017-06-29"),
        ("description", "This is sample data of OMERO"),
        ("hasPart", [
          {
            "@id": "images"
          }
        ]),
        ("identifier", "https://dx.doi.org/10.5281/zenodo.1009240"),
        ("keywords", "OMERO"),
        ("name", "Sample dataset OMERO"),
        ("publisher", {
          "@id": "http://uts.edu.au"
        }),
        ("relatedLink", {
          "@id": "http://github.com/moisbo",
          "OmeroURl": "https://omero.research.uts.edu.au"
        }),
        ("temporalCoverage", "2017")
    ])
    images=OrderedDict([
        ("@id", "images"),
        ("@type", "Dataset"),
        ("path", "data"),
        ("identifier", "images"),
        ("startTime", "2016-01-21T11:00:00+11:00"),
        ("endTime", "2016-11-21T11:00:00+11:00"),
        ("description", "This is a test datacrate of files pulled from OMERO"),
        ("hasPart", list(dict())),
        ("funder", [{
          "@id": "http://uts.edu.au"
        }])
      ])
    meta_dict["@graph"]=list([institute,person,crate,images])
    return meta_dict
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def json_metadata( conn, Id, reldir, new_name ):
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    img = conn.getObject("Image",Id)
    name,ext  = os.path.splitext(img.getName())
    filepath  = os.path.join(reldir,new_name+ext)
    thumbpath = os.path.join(reldir,'thumbs',new_name+'.jpg')
    file_dict=OrderedDict([
        ("@id", filepath),
        ("@type", "File"),
        ("creator", {
          "@id": "http://github.com/moisbo"
        }),
        ("category", "PROCESSED"),
        ("fileFormat", "text/plain"),
        ("path",     filepath),
        ("filename", filepath),
        ("thumbnail", [
          {
            "@id": thumbpath
          }
        ])
    ])

    details=img.getDetails()
    file_dict["omeroName"]   =img.getName()
    file_dict["description"] =img.getDescription()
    file_dict["omeroId" ]    =Id
    file_dict["omeroAuthor"] =img.getAuthor()
    file_dict["omeroGroup"]  =details.getGroup().getName()

    # print the dataset/proj (if they exist)
    otype=""
    parent = img.getParent()
    while( parent is not None ):
        otype=parent.OMERO_CLASS
        file_dict["omero"+otype] = parent.getName()
        parent = parent.getParent()

    file_dict["dateUploaded"]=img.getDate().isoformat()
    file_dict["dateCreated" ]=img.creationEventDate().isoformat()
    
    file_dict["channels"]=img.getChannelLabels()

    # list the user added kvs' from the mapAnnotation
    for ann in img.listAnnotations():
        if( isinstance(ann, omero.gateway.MapAnnotationWrapper) ):
            for k,v in ann.getValue():
                file_dict[k]=v

    thumb_dict=      {
        "@type": "File",
        "path": [
          thumbpath
        ],
        "@id": thumbpath
    }
    return file_dict,thumb_dict

"""
start-code
"""
import sys
import json

parser = argparse.ArgumentParser(description='Download datasets and projects from OMERO')
parser.add_argument('-p','--project', nargs="+", default=[],help="IDs of projects to download")
parser.add_argument('-d','--dataset', nargs="+", default=[],help="IDs of datasets to download")
parser.add_argument('-g','--group'  , nargs="?", help="name of group")
parser.add_argument('-o','--orig'   , action="store_true", default=False, help="download originals")
parser.add_argument('-t','--tif'    , action="store_true", default=False, help="download OME-TIFs" )

args = parser.parse_args()

# Create a connection
# ===================
try:
    from omero.gateway import BlitzGateway
    from Parse_OMERO_Properties import USERNAME, PASSWORD, HOST, PORT
    print(HOST)
    conn = BlitzGateway(USERNAME, PASSWORD, host=HOST, port=PORT)
    conn.connect()
    
    user = conn.getUser()
    print "Current user:"
    print "   ID:", user.getId()
    print "   Username:", user.getName()
    print "   Full Name:", user.getFullName()

    if( args.group is not None ):
        print("change group")
        new_group = args.group
        groups = [ g.getName() for g in conn.listGroups() ]
        print(groups)
        if( new_group not in groups ):
            print("{} not found in groups:".format(new_group))
            for gn in groups:
                print("    {}".format(gn))
            sys.exit(1)
        else:
            conn.setGroupNameForSession(group)
    print conn.getGroupFromContext().getName()
    path    = os.getcwd()

    mdict= setup_dict()

    def package_file( mdict,conn, group, Id, path, name ):
        print "processing {} {} as : {}/{}".format(group,Id,path,name)
        groups = [ g.getName() for g in conn.listGroups() ]
        if( group not in groups ):
            print "    no group found"
            return
        if( group != conn.getGroupFromContext().getName() ):
            conn.setGroupNameForSession(group)

        download_file(    conn, Id, path, name )
        file_dict,thumb_dict = json_metadata(conn, Id, path, name)
        mdict["@graph"][3]['hasPart'].append({"@id":file_dict['@id']})
        mdict["@graph"].append(file_dict)
        mdict["@graph"].append(thumb_dict)

        return mdict


    mdict=package_file( mdict, conn, 'training',   30666, 'data',   'treat4')
    mdict=package_file( mdict, conn, 'default',     1130, 'data',   'treat3')
    mdict=package_file( mdict, conn, 'default',    22422, 'data',   'treat1')
    mdict=package_file( mdict, conn, 'default',     1159, 'data',   'treat2')
    mdict=package_file( mdict, conn, 'whitchurch', 17242, 'control','control1')
    mdict=package_file( mdict, conn, 'djordjevic',  4128, 'control','control2')



    # write the JSON
    j = json.dumps(mdict, indent=4)
    f = open('CATALOG.json', 'w')
    print >> f, j
    f.close()

    #print( args.dataset )
    #for d_id in args.dataset:
    #    download_dataset( conn, d_id, path, orig=args.orig, tif=args.tif )

    #print(args.project)
    #for p_id in args.project:
    #    project = conn.getObject('Project',p_id)
    #    path_p = os.path.join(path,project.getName())
    #    if( project==None ):
    #        print("project ID {} not found in group {}".format(p_id, orig=args.orig, tif=args.tif))
    #        sys.exit(1)

    #    for ds in list(project.listChildren()):
    #        download_dataset( conn, ds.getId(), path_p, orig=args.orig, tif=args.tif )

    #    
finally:    
    # When you are done, close the session to free up server resources.
    conn.close()
conn.close()


