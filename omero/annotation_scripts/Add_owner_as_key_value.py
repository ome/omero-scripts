"""
 MIF/Add_owner_as_key_value.py
 Adds data owner as a key-value pair to images and/or containers
 (i.e. project, dataset, well, plate and screen).
-----------------------------------------------------------------------------
  Copyright (C) 2022
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
Created by Rémy Dornier, based on Christian Evenhuis work.
"""


import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong
import omero.scripts as scripts
#from omero.cmd import Delete2
from datetime import date

import sys
import copy

from collections import OrderedDict


def get_existing_map_annotations(obj, namespace):
    """Get all Map Annotations linked to the object"""
    ord_dict = OrderedDict()
    for ann in obj.listAnnotations(ns=namespace):
        if isinstance(ann, omero.gateway.MapAnnotationWrapper):
            kvs = ann.getValue()
            for k, v in kvs:
                if k not in ord_dict:
                    ord_dict[k] = set()
                ord_dict[k].add(v)
    return ord_dict

'''
def remove_map_annotations(conn, object, namespace):
    """Remove ALL Map Annotations on the object"""
    anns = list(object.listAnnotations(ns=namespace))
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
'''

"""Add a key value pair to the object"""
"""Code taken and adapted from Christian Evenhuis,  https://github.com/ome/omero-scripts/blob/develop/omero/annotation_scripts/KeyVal_from_csv.py"""
def annotate_object(conn, obj, key, val):
    obj_updated = False
    namespace = "Previous Owners"
    existing_kv = get_existing_map_annotations(obj, namespace)
    updated_kv = copy.deepcopy(existing_kv)

    print("Existing kv:")
    for k, vset in existing_kv.items():
        for v in vset:
            print("   ", k, v)

    print("Adding kv:")

    if key not in updated_kv:
        updated_kv[key] = set()
    print("   ", key, val)
    updated_kv[key].add(val)

    if existing_kv != updated_kv:
        try:
            print("The key-values pairs are different")
            anns = list(obj.listAnnotations(ns=namespace))
            map_anns = [ann for ann in anns if isinstance(ann, omero.gateway.MapAnnotationWrapper)]
            if len(map_anns) > 0:
                map_ann = map_anns[0]

                # convert the ordered dict to a list of lists
                kv_list = []
                for k, vset in updated_kv.items():
                    for v in vset:
                        kv_list.append([k, v])
                map_ann.append(kv_list)
                map_ann.save()
                print("Map Annotation created", map_ann.id)
                obj.linkAnnotation(map_ann)
                obj_updated = True
        except omero.SecurityViolation:
            print("You do not have the right to write annotations for ",obj.OMERO_CLASS, "", obj.getId())
    else:
        print("No change change in kv")

    return obj_updated


"""
Add the owner as key value pair to an image
return 1 if owner has been added, 0 otherwise
"""
def process_image(conn, image, key, owner):
    return (1 if annotate_object(conn, image, key, owner)== True else 0)


"""
Add the owner as key value pair to a dataset and its children
return the number of processed images
"""
def process_dataset(conn, dataset, key, owner):
    nImage = 0
    for image in dataset.listChildren():
        nImage += process_image(conn, image, key, owner)

    return nImage, (1 if annotate_object(conn, dataset, key, owner)== True else 0)


"""
Add the owner as key value pair to a project and its children
return the number of processed images & datasets
"""
def process_project(conn, project, key, owner):
    nDataset = 0
    nImage = 0
    for dataset in project.listChildren():
        nImageTmp, nDatasetTmp = process_dataset(conn, dataset, key, owner)
        nDataset += nDatasetTmp
        nImage += nImageTmp

    return nImage, nDataset, (1 if annotate_object(conn, project, key, owner)== True else 0)


"""
Add the owner as key value pair to a well and its children
return the number of processed images 
"""
def process_well(conn, well, key, owner):
    nImage = 0
    for wellSample in well.listChildren():
        nImage += process_image(conn, wellSample.getImage(), key, owner)

    return nImage, (1 if annotate_object(conn, well, key, owner)== True else 0)


"""
Add the owner as key value pair to a plate and its children
return the number of processed images & wells
"""
def process_plate(conn, plate, key, owner):
    nImage = 0
    nWell = 0
    for well in plate.listChildren():
        nImageTmp, nWellTmp = process_well(conn, well, key, owner)
        nWell += nWellTmp
        nImage += nImageTmp

    return nImage, nWell, (1 if annotate_object(conn, plate, key, owner)== True else 0)


"""
Add the owner as key value pair to a screen and its children
return the number of processed images, wells & plates
"""
def process_screen(conn, screen, key, owner):
    nImage = 0
    nWell = 0
    nPlate = 0
    for plate in screen.listChildren():
        nImageTmp, nWellTmp, nPlateTmp = process_plate(conn, plate, key, owner)
        nImage += nImageTmp
        nWell += nWellTmp
        nPlate += nPlateTmp

    return nImage, nWell, nPlate, (1 if annotate_object(conn, screen, key, owner)== True else 0)


"""
Get the given container(s) or given experimenter(s) and scan all their children to add 
data owner as a key-value pair to all of them.
"""
def add_owner_as_keyval(conn, script_params):
    # select the object type (image, dataset, project, well, plate, screen, user)
    object_type = script_params["Data_Type"]
    # enter its corresponding ID (except for 'user' : enter the username)
    object_id_list = script_params["IDs"]

    today = date.today().strftime("%Y%m%d")
    key = "Owner_"+today

    nImage = 0
    nDataset = 0
    nProject = 0
    nWell = 0
    nPlate = 0
    nScreen = 0
    owner = ""

    for object_id in object_id_list:
        """ add owner to all objects owned by the specified user"""
        if(object_type == 'User'):
            # set the group to all
            conn.SERVICE_OPTS.setOmeroGroup('-1')

            # get the user
            user = conn.getObject("experimenter", attributes={"omeName": object_id})

            if not user == None:
                # get the list of groups to search in
                group_list = []
                if(conn.getUser().isAdmin()):
                    for gem in user.copyGroupExperimenterMap():
                        group_list.append(gem.getParent().getId().getValue())

                    # get sudo connection
                    user_name = user.getName()
                    user_conn = conn.suConn(user_name, ttl=600000)
                    user_id = user_conn.getUser().getId()
                else:
                    for g in conn.getGroupsMemberOf():
                        group_list.append(g.getId())
                    user_conn = conn
                    user_id = user.getId()

                # get the owner
                owner = ""
                owner += user.getFirstName() + " "
                owner += user.getLastName()

                for g_id in group_list:
                    # set the group
                    user_conn.SERVICE_OPTS.setOmeroGroup(g_id)

                    # list all user's projects
                    projects = user_conn.getObjects("Project", opts={'owner': user_id})
                    for project in projects:
                        nImageTmp, nDatasetTmp, nProjectTmp = process_project(user_conn, project, key, owner)
                        nImage += nImageTmp
                        nDataset += nDatasetTmp
                        nProject += nProjectTmp

                    # lists all user's screens
                    screens = user_conn.getObjects("screen", opts={'owner': user_id})
                    for screen in screens:
                        nImageTmp, nWellTmp, nPlateTmp, nScreenTmp = process_screen(user_conn, screen, key, owner)
                        nImage += nImageTmp
                        nWell += nWellTmp
                        nPlate += nPlateTmp
                        nScreen += nScreenTmp

                    # lists all user's orpahned dataset
                    orphaned_datasets = user_conn.getObjects("dataset", opts={'owner': user_id, 'orphaned': True})
                    for orphaned_dataset in orphaned_datasets:
                        nImageTmp, nDatasetTmp = process_dataset(user_conn, orphaned_dataset, key, owner)
                        nDataset += nDatasetTmp
                        nImage += nImageTmp

                    # lists all user's orpahned plates
                    orphaned_plates = user_conn.getObjects("plate", opts={'owner': user_id, 'orphaned': True})
                    for orphaned_plate in orphaned_plates:
                        nImageTmp, nWellTmp, nPlateTmp = process_plate(user_conn, orphaned_plate, key, owner)
                        nImage += nImageTmp
                        nWell += nWellTmp
                        nPlate += nPlateTmp

                    # lists all user's orpahned images
                    orphaned_images = user_conn.getObjects("image", opts={'owner': user_id, 'orphaned': True})
                    for orphaned_image in orphaned_images:
                        nImage += process_image(user_conn, orphaned_image, key, owner)

                # close the user connection
                if(conn.getUser().isAdmin()):
                    user_conn.close()

            else:
                print("The user",object_id,"does not exists or you do not have access to his/her data")

        else:
            """ add owner to the specified object and its children"""
            # convert to long
            object_id = int(object_id)

            # search in all the user's group
            conn.SERVICE_OPTS.setOmeroGroup('-1')

            # get the object
            omero_object = conn.getObject(object_type, object_id)

            if not omero_object == None:
                if(conn.getUser().isAdmin()):
                    # get sudo connection
                    user_name = omero_object.getOwner().getOmeName()
                    user_conn = conn.suConn(user_name, ttl=600000)
                    user_conn.SERVICE_OPTS.setOmeroGroup('-1')
                    omero_object = user_conn.getObject(object_type, object_id)
                else:
                    user_conn = conn

            if not omero_object == None:
                # set the correct group Id
                user_conn.SERVICE_OPTS.setOmeroGroup(omero_object.getDetails().getGroup().getId())

                # get the owner
                owner = ""
                owner += omero_object.getOwner().getFirstName() + " "
                owner += omero_object.getOwner().getLastName()

                # select object type and add owner as key-value pair
                if object_type == 'Image':
                    nImage += process_image(user_conn, omero_object, key, owner)
                if object_type == 'Dataset':
                    nImageTmp, nDatasetTmp = process_dataset(user_conn, omero_object, key, owner)
                    nDataset += nDatasetTmp
                    nImage += nImageTmp
                if object_type == 'Project':
                    nImageTmp, nDatasetTmp, nProjectTmp = process_project(user_conn, omero_object, key, owner)
                    nImage += nImageTmp
                    nDataset += nDatasetTmp
                    nProject += nProjectTmp
                if object_type == 'Well':
                    nImageTmp, nWellTmp = process_well(user_conn, omero_object, key, owner)
                    nWell += nWellTmp
                    nImage += nImageTmp
                if object_type == 'Plate':
                    nImageTmp, nWellTmp, nPlateTmp = process_plate(user_conn, omero_object, key, owner)
                    nImage += nImageTmp
                    nWell += nWellTmp
                    nPlate += nPlateTmp
                if object_type == 'Screen':
                    nImageTmp, nWellTmp, nPlateTmp, nScreenTmp = process_screen(user_conn, omero_object, key, owner)
                    nImage += nImageTmp
                    nWell += nWellTmp
                    nPlate += nPlateTmp
                    nScreen += nScreenTmp

                # close the user connection                
                if(conn.getUser().isAdmin()):
                    user_conn.close()

            else:
                print(object_type, object_id, "does not exist or you do not have access to it")

    # build summary message        
    if(owner == ""):
        message = "Owner cannot be added"
    else:
        message = "Added {} as owner to {} image(s), {} dataset(s), {} project(s), {} well(s), {} plate(s), {} screen(s) ".format(owner, nImage, nDataset, nProject, nWell, nPlate, nScreen)
    print(message)

    return message


def run_script():

    data_types = [rstring('Image'), rstring('Dataset'),rstring('Project'), rstring('Well'), rstring('Plate'),rstring('Screen'), rstring('User')]
    client = scripts.client(
        'Add_Owner_as_KeyVal',
        """
    This script adds the owner of data as a key-value pair to the selected source(s) and its children.
        """,
        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=data_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="Object ID(s) or username(s).").ofType(rstring('')),

        authors=["Rémy Dornier"],
        institutions=["EPFL - BIOP"],
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
        message = add_owner_as_keyval(conn, script_params)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()