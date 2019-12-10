#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
-----------------------------------------------------------------------------
  Copyright (C) 2006-2014 University of Dundee. All rights reserved.


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

This script creates new images from existing images, applying x, y, and z
shifts to each channel independently, as specified in the parameters.

@author  Will Moore &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 3.0
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.3

"""

import omero
from omero.gateway import BlitzGateway
import omero.scripts as scripts
from omero.rtypes import rlong, rstring, robject
import omero.util.script_utils as script_utils

from numpy import zeros, hstack, vstack


def new_image_with_channel_offsets(conn, image_id, channel_offsets,
                                   dataset=None):
    """
    Process a single image here: creating a new image and passing planes from
    original image to new image - applying offsets to each channel as we go.

    @param image_id:            Original image
    @param channel_offsets:     List of map for each channel {'index':index,
                                'x':x, 'y'y, 'z':z}
    """

    old_image = conn.getObject("Image", image_id)
    if old_image is None:
        return

    if dataset is None:
        dataset = old_image.getParent()

    # these dimensions don't change
    size_z = old_image.getSizeZ()
    size_c = old_image.getSizeC()
    size_t = old_image.getSizeT()
    size_x = old_image.getSizeX()
    size_y = old_image.getSizeY()

    # check we're not dealing with Big image.
    rps = old_image.getPrimaryPixels()._prepareRawPixelsStore()
    big_image = rps.requiresPixelsPyramid()
    rps.close()
    if big_image:
        return

    # setup the (z,c,t) list of planes we need
    zct_list = []
    for z in range(size_z):
        for offset in channel_offsets:
            if offset['index'] < size_c:
                for t in range(size_t):
                    z_offset = offset['z']
                    zct_list.append((z-z_offset, offset['index'], t))

    # for convenience, make a map of channel:offsets
    offset_map = {}
    channel_list = []
    for c in channel_offsets:
        c_index = c['index']
        if c_index < size_c:
            channel_list.append(c_index)
            offset_map[c_index] = {'x': c['x'], 'y': c['y'], 'z': c['z']}

    def offset_plane(plane, x, y):
        """
        Takes a numpy 2D array and returns the same plane offset by x and y,
        adding rows and columns of 0 values
        """
        height, width = plane.shape
        data_type = plane.dtype
        # shift x by cropping, creating a new array of columns and stacking
        # horizontally
        if abs(x) > 0:
            new_cols = zeros((height, abs(x)), data_type)
            x1 = max(0, 0-x)
            x2 = min(width, width-x)
            crop = plane[0:height, x1:x2]
            if x > 0:
                plane = hstack((new_cols, crop))
            else:
                plane = hstack((crop, new_cols))
        # shift y by cropping, creating a new array of rows and stacking
        # vertically
        if abs(y) > 0:
            new_rows = zeros((abs(y), width), data_type)
            y1 = max(0, 0-y)
            y2 = min(height, height-y)
            crop = plane[y1:y2, 0:width]
            if y > 0:
                plane = vstack((new_rows, crop))
            else:
                plane = vstack((crop, new_rows))
        return plane

    def offset_plane_gen():
        pixels = old_image.getPrimaryPixels()
        dt = None
        # get the planes one at a time - exceptions on getPlane() don't affect
        # subsequent calls (new RawPixelsStore)
        for i in range(len(zct_list)):
            z, c, t = zct_list[i]
            offsets = offset_map[c]
            if z < 0 or z >= size_z:
                if dt is None:
                    # if we are on our first plane, we don't know datatype
                    # yet...
                    dt = pixels.getPlane(0, 0, 0).dtype
                    # hack! TODO: add method to pixels to supply dtype
                plane = zeros((size_y, size_x), dt)
            else:
                try:
                    plane = pixels.getPlane(*zct_list[i])
                    dt = plane.dtype
                except Exception:
                    # E.g. the Z-index is out of range - Simply supply an
                    # array of zeros.
                    if dt is None:
                        # if we are on our first plane, we don't know datatype
                        # yet...
                        dt = pixels.getPlane(0, 0, 0).dtype
                        # hack! TODO: add method to pixels to supply dtype
                    plane = zeros((size_y, size_x), dt)
            yield offset_plane(plane, offsets['x'], offsets['y'])

    # create a new image with our generator of numpy planes.
    new_image_name = "%s_offsets" % old_image.getName()
    desc_lines = [" Channel %s: Offsets x: %s y: %s z: %s" % (c['index'],
                  c['x'], c['y'], c['z']) for c in channel_offsets]
    desc = "Image created from Image ID: %s by applying Channel Offsets:\n" \
        % image_id
    desc += "\n".join(desc_lines)
    i = conn.createImageFromNumpySeq(
        offset_plane_gen(), new_image_name,
        sizeZ=size_z, sizeC=len(offset_map.items()), sizeT=size_t,
        description=desc, sourceImageId=image_id, channelList=channel_list)

    # Link image to dataset
    link = None
    if dataset and dataset.canLink():
        link = omero.model.DatasetImageLinkI()
        link.parent = omero.model.DatasetI(dataset.getId(), False)
        link.child = omero.model.ImageI(i.getId(), False)
        conn.getUpdateService().saveAndReturnObject(link)

    return i, link


def process_images(conn, script_params):
    """
    Process the script params to make a list of channel_offsets, then iterate
    through the images creating a new image from each with the specified
    channel offsets
    """

    message = ""

    # Get the images
    images, log_message = script_utils.get_objects(conn, script_params)
    message += log_message
    if not images:
        return None, None, message
    image_ids = [i.getId() for i in images]

    # Get the channel offsets
    channel_offsets = []
    for i in range(1, 5):
        p_name = "Channel_%s" % i
        if script_params[p_name]:
            index = i-1     # UI channel index is 1-based - we want 0-based
            x = "Channel%s_X_shift" % i in script_params and \
                script_params["Channel%s_X_shift" % i] or 0
            y = "Channel%s_Y_shift" % i in script_params and \
                script_params["Channel%s_Y_shift" % i] or 0
            z = "Channel%s_Z_shift" % i in script_params and \
                script_params["Channel%s_Z_shift" % i] or 0
            channel_offsets.append({'index': index, 'x': x, 'y': y, 'z': z})

    dataset = None
    if "New_Dataset_Name" in script_params:
        # create new Dataset...
        new_dataset_name = script_params["New_Dataset_Name"]
        dataset = omero.gateway.DatasetWrapper(conn,
                                               obj=omero.model.DatasetI())
        dataset.setName(rstring(new_dataset_name))
        dataset.save()
        # add to parent Project
        parent_ds = images[0].getParent()
        project = parent_ds is not None and parent_ds.getParent() or None
        if project is not None and project.canLink():
            link = omero.model.ProjectDatasetLinkI()
            link.parent = omero.model.ProjectI(project.getId(), False)
            link.child = omero.model.DatasetI(dataset.getId(), False)
            conn.getUpdateService().saveAndReturnObject(link)

    # need to handle Datasets eventually - Just do images for now
    new_images = []
    links = []
    for image_id in image_ids:
        new_img, link = new_image_with_channel_offsets(conn, image_id,
                                                       channel_offsets,
                                                       dataset)
        if new_img is not None:
            new_images.append(new_img)
            if link is not None:
                links.append(link)

    if not new_images:
        message += "No image created."
    else:
        if len(new_images) == 1:
            if not link:
                link_message = " but could not be attached"
            else:
                link_message = ""
            message += "New image created%s: %s." % (link_message,
                                                     new_images[0].getName())
        elif len(new_images) > 1:
            message += "%s new images created" % len(new_images)
            if not len(links) == len(new_images):
                message += " but some of them could not be attached."
            else:
                message += "."

    return new_images, dataset, message


def run_script():

    data_types = [rstring('Image')]

    client = scripts.client(
        'Channel_Offsets.py',
        """Create new Images from existing images, applying an x, y and z \
shift to each channel independently.
See http://help.openmicroscopy.org/scripts.html""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Pick Images by 'Image' ID or by the ID of their "
            "Dataset'", values=data_types, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs to "
            "process.").ofType(rlong(0)),

        scripts.String(
            "New_Dataset_Name", grouping="3",
            description="If you want the new image(s) in a new Dataset, "
            "put name here"),

        scripts.Bool(
            "Channel_1", grouping="4", default=True,
            description="Choose to include this channel in the output image"),

        scripts.Int(
            "Channel1_X_shift", grouping="4.1", default=0,
            description="Number of pixels to shift this channel in the X "
            "direction. (negative to shift left)"),

        scripts.Int(
            "Channel1_Y_shift", grouping="4.2", default=0,
            description="Number of pixels to shift this channel in the Y"
            " direction. (negative to shift up)"),

        scripts.Int(
            "Channel1_Z_shift", grouping="4.3", default=0,
            description="Offset channel by a number of Z-sections"),

        scripts.Bool(
            "Channel_2", grouping="5", default=True,
            description="Choose to include this channel in the output image"),

        scripts.Int(
            "Channel2_X_shift", grouping="5.1", default=0,
            description="Number of pixels to shift this channel in the X "
            "direction. (negative to shift left)"),

        scripts.Int(
            "Channel2_Y_shift", grouping="5.2", default=0,
            description="Number of pixels to shift this channel in the Y "
            "direction. (negative to shift up)"),

        scripts.Int(
            "Channel2_Z_shift", grouping="5.3", default=0,
            description="Offset channel by a number of Z-sections"),

        scripts.Bool(
            "Channel_3", grouping="6", default=True,
            description="Choose to include this channel in the output image"),

        scripts.Int(
            "Channel3_X_shift", grouping="6.1", default=0,
            description="Number of pixels to shift this channel in the X "
            "direction. (negative to shift left)"),

        scripts.Int(
            "Channel3_Y_shift", grouping="6.2", default=0,
            description="Number of pixels to shift this channel in the Y "
            "direction. (negative to shift up)"),

        scripts.Int(
            "Channel3_Z_shift", grouping="6.3", default=0,
            description="Offset channel by a number of Z-sections"),

        scripts.Bool(
            "Channel_4", grouping="7", default=True,
            description="Choose to include this channel in the output image"),

        scripts.Int(
            "Channel4_X_shift", grouping="7.1", default=0,
            description="Number of pixels to shift this channel in the X "
            "direction. (negative to shift left)"),

        scripts.Int(
            "Channel4_Y_shift", grouping="7.2", default=0,
            description="Number of pixels to shift this channel in the Y "
            "direction. (negative to shift up)"),

        scripts.Int(
            "Channel4_Z_shift", grouping="7.3", default=0,
            description="Offset channel by a number of Z-sections"),

        version="4.2.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        script_params = client.getInputs(unwrap=True)
        print(script_params)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        images, dataset, message = process_images(conn, script_params)
        print(message)

        # Return message, new image and new dataset (if applicable) to the
        # client
        client.setOutput("Message", rstring(message))
        if len(images) == 1:
            client.setOutput("Image", robject(images[0]._obj))
        if dataset is not None:
            client.setOutput("New Dataset", robject(dataset._obj))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
