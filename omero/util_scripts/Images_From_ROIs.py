#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 components/tools/OmeroPy/scripts/omero/util_scripts/Images_From_ROIs.py

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

import omero
import omero.scripts as scripts
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong, robject
import omero.util.script_utils as script_utils
from omero.util.tiles import TileLoopIteration, RPSTileLoop
from omero.model import PixelsI

import os

import time
startTime = 0


def printDuration(output=True):
    global startTime
    if startTime == 0:
        startTime = time.time()
    if output:
        print "Script timer = %s secs" % (time.time() - startTime)


def create_image_from_tiles(conn, source, image_name, description,
                            box, tileSize):

    pixelsService = conn.getPixelsService()
    queryService = conn.getQueryService()
    xbox, ybox, wbox, hbox, z1box, z2box, t1box, t2box = box
    sizeX = wbox
    sizeY = hbox
    sizeZ = source.getSizeZ()
    sizeT = source.getSizeT()
    sizeC = source.getSizeC()
    tileWidth = tileSize
    tileHeight = tileSize
    primary_pixels = source.getPrimaryPixels()

    def create_image():
        query = "from PixelsType as p where p.value='uint8'"
        pixelsType = queryService.findByQuery(query, None)
        channelList = range(sizeC)
        # bytesPerPixel = pixelsType.bitSize.val / 8
        iId = pixelsService.createImage(
            sizeX,
            sizeY,
            sizeZ,
            sizeT,
            channelList,
            pixelsType,
            image_name,
            description,
            conn.SERVICE_OPTS)

        image = conn.getObject("Image", iId)
        return image

    # Make a list of all the tiles we're going to need.
    # This is the SAME ORDER that RPSTileLoop will ask for them.
    zctTileList = []
    for t in range(0, sizeT):
        for c in range(0, sizeC):
            for z in range(0, sizeZ):
                for tileOffsetY in range(
                        0, ((sizeY + tileHeight - 1) / tileHeight)):
                    for tileOffsetX in range(
                            0, ((sizeX + tileWidth - 1) / tileWidth)):
                        x = tileOffsetX * tileWidth
                        y = tileOffsetY * tileHeight
                        w = tileWidth
                        if (w + x > sizeX):
                            w = sizeX - x
                        h = tileHeight
                        if (h + y > sizeY):
                            h = sizeY - y
                        tile_xywh = (xbox + x, ybox + y, w, h)
                        zctTileList.append((z, c, t, tile_xywh))

    # This is a generator that will return tiles in the sequence above
    # getTiles() only opens 1 rawPixelsStore for all the tiles
    # whereas getTile() opens and closes a rawPixelsStore for each tile.
    tileGen = primary_pixels.getTiles(zctTileList)

    def nextTile():
        return tileGen.next()

    class Iteration(TileLoopIteration):

        def run(self, data, z, c, t, x, y, tileWidth, tileHeight, tileCount):
            tile2d = nextTile()
            data.setTile(tile2d, z, c, t, x, y, tileWidth, tileHeight)

    new_image = create_image()
    pid = new_image.getPixelsId()
    loop = RPSTileLoop(conn.c.sf, PixelsI(pid, False))
    loop.forEachTile(tileWidth, tileHeight, Iteration())

    for theC in range(sizeC):
        pixelsService.setChannelGlobalMinMax(pid, theC, float(0),
                                             float(255), conn.SERVICE_OPTS)

    return new_image


def getRectangles(conn, imageId):
    """
    Returns a list of (x, y, width, height, zStart, zStop, tStart, tStop)
    of each rectange ROI in the image
    """

    rois = []

    roiService = conn.getRoiService()
    result = roiService.findByImage(imageId, None)

    for roi in result.rois:
        zStart = None
        zEnd = 0
        tStart = None
        tEnd = 0
        x = None
        for shape in roi.copyShapes():
            if type(shape) == omero.model.RectangleI:
                # check t range and z range for every rectangle
                # t and z (and c) for shape is optional
                # https://www.openmicroscopy.org/site/support/omero5.2/developers/Model/EveryObject.html#shape
                try:
                    t = shape.getTheT().getValue()
                except AttributeError:
                    t = 0
                try:
                    z = shape.getTheZ().getValue()
                except AttributeError:
                    z = 0
                if tStart is None:
                    tStart = t
                if zStart is None:
                    zStart = z
                tStart = min(t, tStart)
                tEnd = max(t, tEnd)
                zStart = min(z, zStart)
                zEnd = max(z, zEnd)
                if x is None:   # get x, y, width, height for first rect only
                    x = int(shape.getX().getValue())
                    y = int(shape.getY().getValue())
                    width = int(shape.getWidth().getValue())
                    height = int(shape.getHeight().getValue())
        # if we have found any rectangles at all...
        if zStart is not None:
            rois.append((x, y, width, height, zStart, zEnd, tStart, tEnd))

    return rois


def processImage(conn, imageId, parameterMap):
    """
    Process an image.
    If imageStack is True, we make a Z-stack using one tile from each ROI
    (c=0)
    Otherwise, we create a 5D image representing the ROI "cropping" the
    original image
    Image is put in a dataset if specified.
    """

    imageStack = parameterMap['Make_Image_Stack']

    image = conn.getObject("Image", imageId)
    if image is None:
        print "No image found for ID: %s" % imageId
        return

    parentDataset = image.getParent()
    parentProject = None
    if parentDataset is not None:
        parentProject = parentDataset.getParent()

    imageName = image.getName()
    updateService = conn.getUpdateService()

    pixels = image.getPrimaryPixels()
    # note pixel sizes (if available) to set for the new images
    physicalSizeX = pixels.getPhysicalSizeX()
    physicalSizeY = pixels.getPhysicalSizeY()

    # x, y, w, h, zStart, zEnd, tStart, tEnd
    rois = getRectangles(conn, imageId)

    imgW = image.getSizeX()
    imgH = image.getSizeY()

    for index, r in enumerate(rois):
        x, y, w, h, z1, z2, t1, t2 = r
        # Bounding box
        X = max(x, 0)
        Y = max(y, 0)
        X2 = min(x + w, imgW)
        Y2 = min(y + h, imgH)

        W = X2 - X
        H = Y2 - Y
        if (x, y, w, h) != (X, Y, W, H):
            print "\nCropping ROI (x, y, w, h) %s to be within image."\
                " New ROI: %s" % ((x, y, w, h), (X, Y, W, H))
            rois[index] = (X, Y, W, H, z1, z2, t1, t2)

    print "rois"
    print rois

    if len(rois) == 0:
        print "No rectangular ROIs found for image ID: %s" % imageId
        return

    # if making a single stack image...
    if imageStack:
        print "\nMaking Image stack from ROIs of Image:", imageId
        print "physicalSize X, Y:  %s, %s" % (physicalSizeX, physicalSizeY)
        # use width and height from first roi to make sure that all are the
        # same.
        x, y, width, height, z1, z2, t1, t2 = rois[0]

        def tileGen():
            # list a tile from each ROI and create a generator of 2D planes
            zctTileList = []
            # assume single channel image Electron Microscopy use case
            c = 0
            for r in rois:
                x, y, w, h, z1, z2, t1, t2 = r
                tile = (x, y, width, height)
                zctTileList.append((z1, c, t1, tile))
            for t in pixels.getTiles(zctTileList):
                yield t

        if 'Container_Name' in parameterMap:
            newImageName = "%s_%s" % (os.path.basename(imageName),
                                      parameterMap['Container_Name'])
        else:
            newImageName = os.path.basename(imageName)
        description = "Image from ROIS on parent Image:\n  Name: %s\n"\
            "  Image ID: %d" % (imageName, imageId)
        print description
        image = conn.createImageFromNumpySeq(
            tileGen(), newImageName,
            sizeZ=len(rois), sizeC=1, sizeT=1, description=description,
            dataset=None)

        # Link image to dataset
        if parentDataset and parentDataset.canLink():
            link = omero.model.DatasetImageLinkI()
            link.parent = omero.model.DatasetI(parentDataset.getId(), False)
            link.child = omero.model.ImageI(image.getId(), False)
            updateService.saveAndReturnObject(link)
        else:
            link = None

        return image, None, link

    # ...otherwise, we're going to make a new 5D image per ROI
    else:
        images = []
        iIds = []
        bigImageSize = conn.getMaxPlaneSize()
        bigImagePixelCount = bigImageSize[0] * bigImageSize[1]

        for index, r in enumerate(rois):
            newName = "%s_%0d" % (imageName, index)
            x, y, w, h, z1, z2, t1, t2 = r
            print "  ROI x: %s y: %s w: %s h: %s z1: %s z2: %s t1: %s t2: %s"\
                % (x, y, w, h, z1, z2, t1, t2)

            description = "Created from image:"\
                " \n  Name: %s\n  Image ID: %d"\
                " \n x: %d y: %d" % (imageName, imageId, x, y)
            if (h * w < bigImagePixelCount):
                # need a tile generator to get all the planes within the ROI
                sizeZ = z2-z1 + 1
                sizeT = t2-t1 + 1
                sizeC = image.getSizeC()
                zctTileList = []
                tile = (x, y, w, h)
                print "zctTileList..."
                for z in range(z1, z2+1):
                    for c in range(sizeC):
                        for t in range(t1, t2+1):
                            zctTileList.append((z, c, t, tile))

                def tileGen():
                    for i, t in enumerate(pixels.getTiles(zctTileList)):
                        yield t
                print "sizeZ, sizeC, sizeT", sizeZ, sizeC, sizeT
                newImg = conn.createImageFromNumpySeq(
                    tileGen(), newName,
                    sizeZ=sizeZ, sizeC=sizeC, sizeT=sizeT,
                    description=description, sourceImageId=imageId)
            else:
                s = time.time()
                tileSize = parameterMap['Tile_Size']
                newImg = create_image_from_tiles(conn, image, newName,
                                                 description, r, tileSize)
                print 'Tiled image creation took:', time.time()-s, 'seconds'

            print "New Image Id = %s" % newImg.getId()

            images.append(newImg)
            iIds.append(newImg.getId())

        if len(iIds) == 0:
            print "No new images created."
            return

        if 'Container_Name' in parameterMap and \
           len(parameterMap['Container_Name'].strip()) > 0:
            # create a new dataset for new images
            datasetName = parameterMap['Container_Name']
            print "\nMaking Dataset '%s' of Images from ROIs of Image: %s" \
                % (datasetName, imageId)
            print "physicalSize X, Y:  %s, %s" \
                % (physicalSizeX, physicalSizeY)
            dataset = omero.model.DatasetI()
            dataset.name = rstring(datasetName)
            desc = "Images in this Dataset are from ROIs of parent Image:\n"\
                "  Name: %s\n  Image ID: %d" % (imageName, imageId)
            dataset.description = rstring(desc)
            dataset = updateService.saveAndReturnObject(dataset)
            parentDataset = dataset
        else:
            # put new images in existing dataset
            dataset = None
            if parentDataset is not None and parentDataset.canLink():
                parentDataset = parentDataset._obj
            else:
                parentDataset = None
            parentProject = None    # don't add Dataset to parent.

        if parentDataset is None:
            link = None
            print "No dataset created or found for new images."\
                " Images will be orphans."
        else:
            link = []
            for iid in iIds:
                dsLink = omero.model.DatasetImageLinkI()
                dsLink.parent = omero.model.DatasetI(
                    parentDataset.id.val, False)
                dsLink.child = omero.model.ImageI(iid, False)
                updateService.saveObject(dsLink)
                link.append(dsLink)
            if parentProject and parentProject.canLink():
                # and put it in the   current project
                projectLink = omero.model.ProjectDatasetLinkI()
                projectLink.parent = omero.model.ProjectI(
                    parentProject.getId(), False)
                projectLink.child = omero.model.DatasetI(
                    dataset.id.val, False)
                updateService.saveAndReturnObject(projectLink)
        # Apply rnd settings of the source image to new images.
        svc = conn.getRenderingSettingsService()
        svc.applySettingsToSet(pixels.getId(), 'Image', iIds)
        return images, dataset, link


def makeImagesFromRois(conn, parameterMap):
    """
    Processes the list of Image_IDs, either making a new image-stack or a new
    dataset from each image, with new image planes coming from the regions in
    Rectangular ROIs on the parent images.
    """

    dataType = parameterMap["Data_Type"]

    message = ""

    # Get the images
    objects, logMessage = script_utils.getObjects(conn, parameterMap)
    message += logMessage
    if not objects:
        return None, message

    # Concatenate images from datasets
    if dataType == 'Image':
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

    imageIds = [i.getId() for i in images]
    newImages = []
    newDatasets = []
    links = []
    for iId in imageIds:
        newImage, newDataset, link = processImage(conn, iId, parameterMap)
        if newImage is not None:
            if isinstance(newImage, list):
                newImages.extend(newImage)
            else:
                newImages.append(newImage)
        if newDataset is not None:
            newDatasets.append(newDataset)
        if link is not None:
            if isinstance(link, list):
                links.extend(link)
            else:
                links.append(link)

    if newImages:
        if len(newImages) > 1:
            message += "Created %s new images" % len(newImages)
        else:
            message += "Created a new image"
    else:
        message += "No image created"

    if newDatasets:
        if len(newDatasets) > 1:
            message += " and %s new datasets" % len(newDatasets)
        else:
            message += " and a new dataset"

    if not links or not len(links) == len(newImages):
        message += " but some images could not be attached"
    message += "."

    robj = (len(newImages) > 0) and newImages[0]._obj or None
    return robj, message


def runAsScript():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """
    printDuration(False)    # start timer
    dataTypes = [rstring('Dataset'), rstring('Image')]

    client = scripts.client(
        'Images_From_ROIs.py',
        """Crop an Image using Rectangular ROIs, to create new Images.
ROIs that extend across Z and T will crop according to the Z and T limits
of each ROI.
If you choose to 'make an image stack' from all the ROIs, the script \
will create a single new Z-stack image with a single plane from each ROI.
ROIs that are 'Big', typically over 3k x 3k pixels will create 'tiled'
images using the specified tile size.
""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose Images via their 'Dataset' or directly by "
            " 'Image' IDs.", values=dataTypes, default="Image"),

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
        parameterMap = client.getInputs(unwrap=True)
        print parameterMap

        # create a wrapper so we can use the Blitz Gateway.
        conn = BlitzGateway(client_obj=client)

        robj, message = makeImagesFromRois(conn, parameterMap)

        client.setOutput("Message", rstring(message))
        if robj is not None:
            client.setOutput("Result", robject(robj))

    finally:
        conn.close()
        printDuration()


if __name__ == "__main__":
    runAsScript()
