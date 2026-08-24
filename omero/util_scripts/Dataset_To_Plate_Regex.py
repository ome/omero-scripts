#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
#   Copyright (C) 2006-2026 University of Dundee. All rights reserved.
#
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# ------------------------------------------------------------------------------


"""
Adds a Dataset of Images to a new Plate, extracting <row> and <col> from Image names.
E.g. image_name='WellB01_image.tif', pattern='Well(?P<row>[A-P])(?P<col>[0-1]{1,2})_image.tif'

Optionally adds the new Plate to a new or existing Screen.

Notes:
- script assumes <row> is alphabetical (A-P), <col> is integer (1-24)
- where there are multiple Fields per Well,
  - the Images_Per_Well script parameter is required
  - assumes sorting by Image name groups all Images for a Well sequentially
  - assumes all Wells have the same number of Fields (Images_Per_Well)

See http://help.openmicroscopy.org/scripts.html
"""

# @authors Graeme Ball, Will Moore
# <a href="mailto:g.ball@dundee.ac.uk">g.ball@dundee.ac.uk</a>
# @version 1.1

# Use & misuse scenarios tested (v1.1):
# 1. dataset id not found - Pass (message: Dataset not found)
# 2a. regex invalid / cannot compile - Pass (message: regex error)
# 2b. regex doesn't match - Pass (message: No match)
# 2c. invalid row, col matched by regex - Pass (message: rol and col indices not in valid lists)
# 3a. multiple images per well, e.g. 3 per well - Pass (message: adding n images to well)
# 3b. multiple images per well, different number per well (1,2,3) - Pass** (adds groups of 3 images)
# 4. name a new screen - Pass
# 5a. add to existing screen by id (exists) - Pass
# 5b. add to existing screen by id (doesn't exist) - Pass (Plate created, message: cannot link to Screen)
# 6a. option to not remove images from dataset - Pass
# 6b. and then try to add images to a plate again - Pass (refuses unless first Plate deleted)
# ** Works as expected but not correctly. TODO: extract actual number of Fields per well using regex

import omero.scripts as scripts
from omero.gateway import BlitzGateway
import omero

from omero.rtypes import rint, rlong, rstring, robject, unwrap

import re, string


def extract_well_row_col(image_name, row_col_regex):
    """
    Return tuple of ((row, column), message) where:
    (row, column) is 0-based index tuple from image_name using regex with named <row> and <col> patterns.
    E.g. image_name='WellB01_image.tif', pattern='Well(?P<row>[A-P])(?P<col>[0-1]{1,2})_image.tif'
    N.B. assumes <row> is alphabetical (A-P), <col> is integer (1-24); returns None where pattern not found.
    """
    # row=A-P,col=1-24; i.e. maximum 384 well plate
    row_labels = list(string.ascii_uppercase)[0:16]
    col_labels = list(range(1, 25, 1))

    info = ""

    # try searching for regex pattern and convert to 0-based row,col indices if found
    m = row_col_regex.search(image_name)
    if m is None:
        info += "No match!"
        return None, info
    else:
        mg = m.groupdict()
        try:
            row = mg['row'].upper()
            col = int(mg['col'])
        except KeyError as e:
            info += "<row> and/or <col> named matches missing. "
            return None, info

        try:
            row_index = row_labels.index(row)
        except ValueError:
            info += f"row index not in {row_labels}. "
            row_index = None
        
        try:
            col_index = col_labels.index(col)
        except ValueError:
            info += f"column index not in {col_labels}. "
            col_index = None
        
        if (row_index is not None) and (col_index is not None):
            return (row_index, col_index), info
        else:
            return None, info
            

def add_images_to_plate(conn, images, plate_id, column, row, remove_from=None):
    """
    Add the Images to a Plate, creating a new Well at the specified row and column.
    NB - This will fail if the Well already exists.
    """
    update_service = conn.getUpdateService()

    well = omero.model.WellI()
    well.plate = omero.model.PlateI(plate_id, False)
    well.column = rint(column)
    well.row = rint(row)

    try:
        for image in images:
            ws = omero.model.WellSampleI()
            ws.image = omero.model.ImageI(image.id, False)
            ws.well = well
            well.addWellSample(ws)
        update_service.saveObject(well)
    except Exception:
        return False

    # remove from Dataset
    for image in images:
        if remove_from is not None:
            links = list(image.getParentLinks(remove_from.id))
            link_ids = [link.id for link in links]
            conn.deleteObjects('DatasetImageLink', link_ids)
    return True


def dataset_to_plate(conn, script_params):
    """Try to add Dataset Images to Plate using parameters provided.""" 

    message = ""

    # get script parameters and update service 
    dataset_id = script_params['Dataset_ID']
    well_row_col_regex = script_params['Well_Row_Col_Regex']
    images_per_well = script_params['Images_Per_Well']
    remove_from_dataset = script_params['Remove_From_Dataset']
    screen_id = None
    if "Screen" in script_params:
        screen = script_params["Screen"]
        try:
            screen_id = int(screen)
        except ValueError:
            pass  # i.e. screen is a string and screen_id is None
    else:
        screen = None

    update_service = conn.getUpdateService()

    # check the regex compiles without error!
    try:
        regex_compiled = re.compile(well_row_col_regex)  # raises RegexError
    except re.error as e:
        message += f"ERROR! for regex '{well_row_col_regex}': {e}"
        return None, message
    
    # Get the dataset using ID and abort if Wells already linked or no permission
    dataset = conn.getObject("Dataset", dataset_id)
    if dataset is None:
        message += f"Dataset {dataset_id} not found! "
        return None, message
    
    def has_images_linked_to_well(dataset):
        params = omero.sys.ParametersI()
        query = "select count(well) from Well as well "\
                "left outer join well.wellSamples as ws " \
                "left outer join ws.image as img "\
                "where img.id in (:ids)"
        params.addIds([i.getId() for i in dataset.listChildren()])
        n_wells = unwrap(conn.getQueryService().projection(
            query, params, conn.SERVICE_OPTS)[0])[0]
        if n_wells > 0:
            return True
        else:
            return False

    if has_images_linked_to_well(dataset):
        message += f"Dataset {dataset_id} already has image-well links! "
        return None, message

    if not dataset.canLink():
        message += f"No permission to add images from dataset {dataset_id}. "
        return None, message

    # find Screen if specified by ID or create new Screen if name string provided
    newscreen = None
    if screen_id:
        screen = conn.getObject("Screen", screen_id)
    elif screen is not None:
        message += f"Creating new screen '{screen}'" 
        newscreen = omero.model.ScreenI()
        newscreen.name = rstring(screen)
        newscreen = update_service.saveAndReturnObject(newscreen)
        screen = conn.getObject("Screen", newscreen.getId().getValue())
        screen_id = screen.id
        
    # create Plate & link to Screen if specified
    plate = omero.model.PlateI()
    plate.name = omero.rtypes.RStringI(dataset.name)
    plate.columnNamingConvention = rstring(str('number'))
    plate.rowNamingConvention = rstring(str('letter'))
    plate = update_service.saveAndReturnObject(plate)
    message += f"New Plate created: {plate.getName().getValue()}. "
    if screen is not None and screen.canLink():
        link = omero.model.ScreenPlateLinkI()
        link.parent = omero.model.ScreenI(screen.id, False)
        link.child = omero.model.PlateI(plate.id.val, False)
        update_service.saveObject(link)
        message += f"Linked Plate to Screen (screen_id={screen_id}). "
    else:
        message += f"Could not link Plate to Screen! (screen_id={screen_id}). "

    # list Images in Dataset and sort by name
    # FIXME, this assumes sorting by Image name can be used to group Well images! 
    images = list(dataset.listChildren())
    dataset_img_count = len(images)
    images.sort(key=lambda x: x.name.lower())
    
    # Do we try to remove images from Dataset and Delte Datset when/if empty?
    remove_from = None
    if remove_from_dataset:
        remove_from = dataset

    # iterate over Image list, in groups of images_per_well, adding to Plate
    image_index = 0
    added_count = 0
    while image_index < len(images):
        well_images = images[image_index: image_index + images_per_well]
        if (images_per_well > 1):
            message += f"adding {images_per_well} images to well. "
        # FIXME: here we extract row,col indices from first well image only!
        # TODO: also extract Well "Field" for each image
        message += f"extracting row,col for {well_images[0].name}: "
        row_col, info = extract_well_row_col(well_images[0].name, regex_compiled)
        message += info
        if row_col is not None:
            message += f"row={row_col[0]}, col={row_col[1]}. "
            if add_images_to_plate(conn, well_images, plate.getId().getValue(),
                                   row_col[1], row_col[0], remove_from):
                added_count += images_per_well

        image_index += images_per_well

    message += f"Added {added_count} Images to Plate. "
    if newscreen is not None:
        robj = newscreen
    elif plate is not None:
        robj = plate
    else:
        robj = None

    return robj, message    


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    data_types = [rstring('Dataset')]
    first_axis = [rstring('column'), rstring('row')]
    row_col_naming = [rstring('letter'), rstring('number')]

    client = scripts.client(
        "Dataset_To_Plate_Regex.py",
        "Take all Images found in a Dataset and add them to a new Plate, " +
        "extracting Well row and column info from Image names using a python regex (regular expression).\n\n" +
        "E.g. for Image names such as 'WellB01_image.tif', 'WellC02_image.tif'\n" +
        "...a matching regex would be: 'Well(?P<row>[A-P])(?P<col>[0-1]{1,2})_image.tif'\n" +
        "N.B. named <row> and <col> patterns must be captured by the regex!\n--\n" +
        "Optionally add the Plate to a new or existing Screen.\nFor help see:\n" +
        "- OMERO scripts: http://help.openmicroscopy.org/scripts.html\n" +
        "- Regular expressions: https://cellprofiler-manual.s3.amazonaws.com/CPmanual/Metadata.html",

        scripts.Int(
            "Dataset_ID", optional=False, grouping="1",
            description="Dataset ID to convert to new Plate"
            ),

        scripts.String(
            "Well_Row_Col_Regex", optional=False, grouping="2.1", default="",
            description="Regex to capture <row> and <col> from image names."),

        scripts.Int(
            "Images_Per_Well", grouping="2.2", optional=False, default=1,
            description="Number of Images (Well Samples) per Well", min=1),

        scripts.String(
            "Screen", grouping="3",
            description="Option: put Plate in a Screen. Enter ID of existing screen " +
            "or Name of new Screen"),

        scripts.Bool(
            "Remove_From_Dataset", grouping="4", default=True,
            description="Remove Images from Dataset as they are added to Plate"),

        version="1.1",
        authors=["Graeme Ball", "William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="g.ball@dundee.ac.uk",
    )

    try:
        script_params = client.getInputs(unwrap=True)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        # Convert Dataset to Plate. Returns new plate or screen.
        new_obj, message = dataset_to_plate(conn, script_params)

        client.setOutput("Message", rstring(message))
        if new_obj is not None:
            client.setOutput("New_Object", robject(new_obj))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
