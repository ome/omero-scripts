#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
-----------------------------------------------------------------------------
  Copyright (C) 2006-2016 University of Dundee. All rights reserved.


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

This script gets all the Rectangles from a particular image, then creates new
images with the regions within the ROIs, and saves them back to the server.

@author  Will Moore &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 3.0
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.2

"""
from __future__ import print_function
import omero
import omero.scripts as scripts
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong, robject, unwrap
import omero.util.script_utils as script_utils
from omero.util.tiles import TileLoopIteration, RPSTileLoop
from omero.model import PixelsI

import os


def create_image_from_tiles(conn, source, image_name, description,
                            box, tile_size):

    pixels_service = conn.getPixelsService()
    query_service = conn.getQueryService()
    xbox, ybox, wbox, hbox, z1box, z2box, t1box, t2box, xy_by_time = box
    size_x = wbox
    size_y = hbox
    size_z = source.getSizeZ()
    size_t = source.getSizeT()
    size_c = source.getSizeC()
    tile_width = tile_size
    tile_height = tile_size
    primary_pixels = source.getPrimaryPixels()

    def create_image():
        query = "from PixelsType as p where p.value='uint8'"
        pixels_type = query_service.findByQuery(query, None)
        channel_list = range(size_c)
        # bytesPerPixel = pixelsType.bitSize.val / 8
        iid = pixels_service.createImage(
            size_x,
            size_y,
            size_z,
            size_t,
            channel_list,
            pixels_type,
            image_name,
            description,
            conn.SERVICE_OPTS)

        return conn.getObject("Image", iid)

    # Make a list of all the tiles we're going to need.
    # This is the SAME ORDER that RPSTileLoop will ask for them.
    zct_tile_list = []
    for t in range(0, size_t):
        for c in range(0, size_c):
            for z in range(0, size_z):
                for tile_offset_y in range(
                        0, ((size_y + tile_height - 1) // tile_height)):
                    for tile_offset_x in range(
                            0, ((size_x + tile_width - 1) // tile_width)):
                        x = tile_offset_x * tile_width
                        y = tile_offset_y * tile_height
                        w = tile_width
                        if (w + x > size_x):
                            w = size_x - x
                        h = tile_height
                        if (h + y > size_y):
                            h = size_y - y
                        tile_xywh = (xbox + x, ybox + y, w, h)
                        zct_tile_list.append((z, c, t, tile_xywh))

    # This is a generator that will return tiles in the sequence above
    # getTiles() only opens 1 rawPixelsStore for all the tiles
    # whereas getTile() opens and closes a rawPixelsStore for each tile.
    tile_gen = primary_pixels.getTiles(zct_tile_list)

    def next_tile():
        return next(tile_gen)

    class Iteration(TileLoopIteration):

        def run(self, data, z, c, t, x, y, tile_width, tile_height,
                tile_count):
            tile2d = next_tile()
            data.setTile(tile2d, z, c, t, x, y, tile_width, tile_height)

    new_image = create_image()
    pid = new_image.getPixelsId()
    loop = RPSTileLoop(conn.c.sf, PixelsI(pid, False))
    loop.forEachTile(tile_width, tile_height, Iteration())

    for the_c in range(size_c):
        pixels_service.setChannelGlobalMinMax(pid, the_c, float(0),
                                              float(255), conn.SERVICE_OPTS)

    return new_image


def get_rectangles(conn, image_id):
    """
    Returns a list of (x, y, width, height, zStart, zStop, tStart, tStop)
    of each rectange ROI in the image
    """

    rois = []

    roi_service = conn.getRoiService()
    result = roi_service.findByImage(image_id, None)

    for roi in result.rois:
        width = None
        z_indexes = []
        t_indexes = []
        # note x and y for every T, to track moving object
        xy_by_time = {}
        for shape in roi.copyShapes():
            if type(shape) == omero.model.RectangleI:
                # check t range and z range for every rectangle
                # t and z (and c) for shape is optional
                # https://www.openmicroscopy.org/site/support/omero5.2/developers/Model/EveryObject.html#shape
                the_t = unwrap(shape.getTheT())
                the_z = unwrap(shape.getTheZ())
                if the_t is not None:
                    t_indexes.append(the_t)
                if the_z is not None:
                    z_indexes.append(the_z)

                if width is None:   # get width, height for first rect only
                    width = int(shape.getWidth().getValue())
                    height = int(shape.getHeight().getValue())
                x = int(shape.getX().getValue())
                y = int(shape.getY().getValue())
                if the_t is not None:
                    xy_by_time[the_t] = {'x': x, 'y': y}
        # if we have found any rectangles at all for this ROI...
        if width is not None:
            t_start = min(t_indexes) if t_indexes else None
            t_end = max(t_indexes) if t_indexes else None
            z_start = min(z_indexes) if z_indexes else None
            z_end = max(z_indexes) if z_indexes else None
            rois.append((x, y, width, height, z_start, z_end,
                         t_start, t_end, xy_by_time))

    return rois


def process_image(conn, image_id, parameter_map):
    """
    Process an image.
    If imageStack is True, we make a Z-stack using one tile from each ROI
    (c=0)
    Otherwise, we create a 5D image representing the ROI "cropping" the
    original image
    Image is put in a dataset if specified.
    """

    image_stack = parameter_map['Make_Image_Stack']

    image = conn.getObject("Image", image_id)
    if image is None:
        return

    parent_dataset = image.getParent()
    parent_project = None
    if parent_dataset is not None:
        parent_project = parent_dataset.getParent()

    image_name = image.getName()
    print("Processing image", image.getId(), image_name)
    update_service = conn.getUpdateService()

    pixels = image.getPrimaryPixels()

    # x, y, w, h, zStart, zEnd, tStart, tEnd
    rois = get_rectangles(conn, image_id)

    img_w = image.getSizeX()
    img_h = image.getSizeY()

    for index, roi in enumerate(rois):
        x, y, w, h, z1, z2, t1, t2, xy_by_time = roi
        # Bounding box
        x_max = max(x, 0)
        y_max = max(y, 0)
        x2_max = min(x + w, img_w)
        y2_max = min(y + h, img_h)

        w_max = x2_max - x_max
        h_max = y2_max - y_max
        if (x, y, w, h) != (x_max, y_max, w_max, h_max):
            rois[index] = (x_max, y_max, w_max, h_max, z1, z2, t1, t2)

    if len(rois) == 0:
        return

    # if making a single stack image...
    if image_stack:
        # use width and height from first roi to make sure that all are the
        # same.
        x, y, width, height, z1, z2, t1, t2, xy_by_time = rois[0]

        def tile_gen():
            # list a tile from each ROI and create a generator of 2D planes
            zct_tile_list = []
            # assume single channel image Electron Microscopy use case
            c = 0
            for roi in rois:
                x, y, w, h, z1, z2, t1, t2, xy_by_time = roi
                tile = (x, y, width, height)
                the_z = z1 if z1 is not None else 0
                the_t = t1 if t1 is not None else 0
                zct_tile_list.append((the_z, c, the_t, tile))
            print('image_stack zct_tile_list:', zct_tile_list)
            for tile in pixels.getTiles(zct_tile_list):
                yield tile

        if 'Container_Name' in parameter_map:
            new_image_name = "%s_%s" % (os.path.basename(image_name),
                                        parameter_map['Container_Name'])
        else:
            new_image_name = os.path.basename(image_name)
        description = "Image from ROIS on parent Image:\n  Name: %s\n"\
            "  Image ID: %d" % (image_name, image_id)

        image = conn.createImageFromNumpySeq(
            tile_gen(), new_image_name,
            sizeZ=len(rois), sizeC=1, sizeT=1, description=description,
            dataset=None)

        # Link image to dataset
        if parent_dataset and parent_dataset.canLink():
            link = omero.model.DatasetImageLinkI()
            link.parent = omero.model.DatasetI(parent_dataset.getId(), False)
            link.child = omero.model.ImageI(image.getId(), False)
            update_service.saveAndReturnObject(link)
        else:
            link = None

        return image, None, link

    # ...otherwise, we're going to make a new 5D image per ROI
    else:
        images = []
        iids = []
        big_image_size = conn.getMaxPlaneSize()
        big_image_pixel_count = big_image_size[0] * big_image_size[1]

        for index, roi in enumerate(rois):
            new_name = "%s_%0d" % (image_name, index)
            x, y, w, h, z1, z2, t1, t2, xy_by_time = roi
            x_max = img_w - w
            y_max = img_h - h

            if z1 is None:
                z1 = 0
                z2 = image.getSizeZ() - 1
            if t1 is None:
                t1 = 0
                t2 = image.getSizeT() - 1

            print("  ROI: x: %s, y: %s, w: %s, h: %s, z: %s-%s, t: %s-%s" % (
                x, y, w, h, z1, z2, t1, t2))

            description = "Created from image:"\
                " \n  Name: %s\n  Image ID: %d"\
                " \n x: %d y: %d" % (image_name, image_id, x, y)
            if (h * w < big_image_pixel_count):
                # need a tile generator to get all the planes within the ROI
                size_z = z2-z1 + 1
                size_t = t2-t1 + 1
                size_c = image.getSizeC()
                zct_tile_list = []
                for z in range(z1, z2+1):
                    for c in range(size_c):
                        for t in range(t1, t2+1):
                            if t in xy_by_time:
                                x = xy_by_time[t]['x']
                                y = xy_by_time[t]['y']
                            tile = (max(0, min(x, x_max)),
                                    max(0, min(y, y_max)), w, h)
                            zct_tile_list.append((z, c, t, tile))

                def tile_gen():
                    for i, t in enumerate(pixels.getTiles(zct_tile_list)):
                        yield t

                new_img = conn.createImageFromNumpySeq(
                    tile_gen(), new_name,
                    sizeZ=size_z, sizeC=size_c, sizeT=size_t,
                    description=description, sourceImageId=image_id)
            else:
                tile_size = parameter_map['Tile_Size']
                new_img = create_image_from_tiles(conn, image, new_name,
                                                  description, roi, tile_size)

            images.append(new_img)
            iids.append(new_img.getId())

        if len(iids) == 0:
            return

        if 'Container_Name' in parameter_map and \
           len(parameter_map['Container_Name'].strip()) > 0:
            # create a new dataset for new images
            dataset_name = parameter_map['Container_Name']
            dataset = omero.model.DatasetI()
            dataset.name = rstring(dataset_name)
            desc = "Images in this Dataset are from ROIs of parent Image:\n"\
                "  Name: %s\n  Image ID: %d" % (image_name, image_id)
            dataset.description = rstring(desc)
            dataset = update_service.saveAndReturnObject(dataset)
            parent_dataset = dataset
        else:
            # put new images in existing dataset
            dataset = None
            if parent_dataset is not None and parent_dataset.canLink():
                parent_dataset = parent_dataset._obj
            else:
                parent_dataset = None
            parent_project = None    # don't add Dataset to parent.

        if parent_dataset is None:
            link = None
        else:
            link = []
            for iid in iids:
                ds_link = omero.model.DatasetImageLinkI()
                ds_link.parent = omero.model.DatasetI(
                    parent_dataset.id.val, False)
                ds_link.child = omero.model.ImageI(iid, False)
                update_service.saveObject(ds_link)
                link.append(ds_link)
            if parent_project and parent_project.canLink():
                # and put it in the   current project
                project_link = omero.model.ProjectDatasetLinkI()
                project_link.parent = omero.model.ProjectI(
                    parent_project.getId(), False)
                project_link.child = omero.model.DatasetI(
                    dataset.id.val, False)
                update_service.saveAndReturnObject(project_link)
        # Apply rnd settings of the source image to new images.
        svc = conn.getRenderingSettingsService()
        svc.applySettingsToSet(pixels.getId(), 'Image', iids)
        return images, dataset, link


def make_images_from_rois(conn, parameter_map):
    """
    Processes the list of Image_IDs, either making a new image-stack or a new
    dataset from each image, with new image planes coming from the regions in
    Rectangular ROIs on the parent images.
    """

    data_type = parameter_map["Data_Type"]

    message = ""

    # Get the images
    objects, log_message = script_utils.get_objects(conn, parameter_map)
    message += log_message
    if not objects:
        return None, message

    # Concatenate images from datasets
    if data_type == 'Image':
        images = objects
    else:
        images = []
        for ds in objects:
            images += ds.listChildren()

    # Check for rectangular ROIs and filter images list
    images = [image for image in images if image.getROICount("Rectangle") > 0]
    if not images:
        message += "No rectangle ROI found."
        return None, message

    image_ids = [i.getId() for i in images]
    new_images = []
    new_datasets = []
    links = []
    for iid in image_ids:
        new_image, new_dataset, link = process_image(conn, iid, parameter_map)
        if new_image is not None:
            if isinstance(new_image, list):
                new_images.extend(new_image)
            else:
                new_images.append(new_image)
        if new_dataset is not None:
            new_datasets.append(new_dataset)
        if link is not None:
            if isinstance(link, list):
                links.extend(link)
            else:
                links.append(link)

    if new_images:
        if len(new_images) > 1:
            message += "Created %s new images" % len(new_images)
        else:
            message += "Created a new image"
    else:
        message += "No image created"

    if new_datasets:
        if len(new_datasets) > 1:
            message += " and %s new datasets" % len(new_datasets)
        else:
            message += " and a new dataset"

    if not links or not len(links) == len(new_images):
        message += " but some images could not be attached"
    message += "."

    robj = (len(new_images) > 0) and new_images[0]._obj or None
    return robj, message


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """
    data_types = [rstring('Dataset'), rstring('Image')]

    client = scripts.client(
        'Images_From_ROIs.py',
        """Crop an Image using Rectangular ROIs, to create a new Image
for each ROI. ROIs that extend across Z and T will crop according to
the Z and T limits of each ROI.
If you choose to 'make an image stack' from all the ROIs, the script \
will create a single new Z-stack image with a single plane from each ROI.
ROIs that are 'Big', typically over 3k x 3k pixels will create 'tiled'
images using the specified tile size.
""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose Images via their 'Dataset' or directly by "
            " 'Image' IDs.", values=data_types, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs to "
            " process.").ofType(rlong(0)),

        scripts.String(
            "Container_Name", grouping="3",
            description="Option: put Images in new Dataset with this name"
            " OR use this name for new Image stacks, if 'Make_Image_Stack')",
            default="From_ROIs"),

        scripts.Bool(
            "Make_Image_Stack", grouping="4", default=False,
            description="If true, make a single Image (stack) from all the"
            " ROIs of each parent Image"),

        scripts.Int(
            "Tile_Size", optional=False, grouping="5",
            min=50, max=2500,
            description="If the new image is large and tiled, "
            "create tiles of this width & height", default=1024),

        version="5.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        parameter_map = client.getInputs(unwrap=True)

        # create a wrapper so we can use the Blitz Gateway.
        conn = BlitzGateway(client_obj=client)

        robj, message = make_images_from_rois(conn, parameter_map)

        client.setOutput("Message", rstring(message))
        if robj is not None:
            client.setOutput("Result", robject(robj))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
