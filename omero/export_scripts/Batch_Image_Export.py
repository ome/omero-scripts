#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 components/tools/OmeroPy/scripts/omero/export_scripts/Batch_Image_Export.py

-----------------------------------------------------------------------------
  Copyright (C) 2006-2011 University of Dundee. All rights reserved.


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

This script takes a number of images and saves individual image planes in a
zip file for download.

@author Will Moore
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 4.3
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.3
"""

import omero.scripts as scripts
from omero.gateway import BlitzGateway
import omero.util.script_utils as script_utils
import omero
from omero.rtypes import rstring, rlong, robject
from omero.constants.namespaces import NSCREATED, NSOMETIFF
import os

import glob
import zipfile
from datetime import datetime

try:
    from PIL import Image  # see ticket:2597
except ImportError:
    import Image

# keep track of log strings.
logStrings = []


def log(text):
    """
    Adds the text to a list of logs. Compiled into text file at the end.
    """
    print text
    logStrings.append(str(text))


def compress(target, base):
    """
    Creates a ZIP recursively from a given base directory.

    @param target:      Name of the zip file we want to write E.g.
                        "folder.zip"
    @param base:        Name of folder that we want to zip up E.g. "folder"
    """
    zip_file = zipfile.ZipFile(target, 'w')
    try:
        files = os.path.join(base, "*")
        for name in glob.glob(files):
            zip_file.write(name, os.path.basename(name), zipfile.ZIP_DEFLATED)

    finally:
        zip_file.close()


def savePlane(image, format, cName, zRange, projectZ, t=0, channel=None,
              greyscale=False, zoomPercent=None, folder_name=None):
    """
    Renders and saves an image to disk.

    @param renderingEngine: Rendering Engine should already be initialised wi
                            with the correct pixels etc
    @param imgName:         The name or path to save to disk, with extension
                            E.g. imgDir/image01_DAPI_T01_Z01.png
    @param zRange:          Tuple of (zIndex,) OR (zStart, zStop) for
                            projection
    @param t:               T index
    @param channel:         Active channel index. If None, use current
                            rendering settings
    @param greyscale:       If true, all visible channels will be
                            greyscale
    @param zoomPercent:     Resize image by this percent if specified.
    """

    originalName = image.getName()
    log("")
    log("savePlane..")
    #log("originalName %s" % originalName)
    #log("format %s" % format)
    log("channel: %s" % cName)
    log("z: %s" % zRange)
    log("t: %s" % t)
    #log("channel %s" % channel)
    #log("greyscale %s" % greyscale)
    #log("zoomPercent %s" % zoomPercent)

    # if channel == None: use current rendering settings
    if channel is not None:
        image.setActiveChannels([channel+1])    # use 1-based Channel indices
        if greyscale:
            image.setGreyscaleRenderingModel()
        else:
            image.setColorRenderingModel()
    if projectZ:
        # imageWrapper only supports projection of full Z range (can't
        # specify)
        image.setProjection('intmax')

    # All Z and T indices in this script are 1-based, but this method uses
    # 0-based.
    plane = image.renderImage(zRange[0]-1, t-1)
    if zoomPercent:
        w, h = plane.size
        fraction = (float(zoomPercent) / 100)
        plane = plane.resize((w * fraction, h * fraction), Image.ANTIALIAS)

    if format == "PNG":
        imgName = makeImageName(
            originalName, cName, zRange, t, "png", folder_name)
        log("Saving image: %s" % imgName)
        plane.save(imgName, "PNG")
    elif format == 'TIFF':
        imgName = makeImageName(
            originalName, cName, zRange, t, "tiff", folder_name)
        log("Saving image: %s" % imgName)
        plane.save(imgName, 'TIFF')
    else:
        imgName = makeImageName(
            originalName, cName, zRange, t, "jpg", folder_name)
        log("Saving image: %s" % imgName)
        plane.save(imgName)


def makeImageName(originalName, cName, zRange, t, extension, folder_name):
    """
    Produces the name for the saved image.
    E.g. imported/myImage.dv -> myImage_DAPI_z13_t01.png
    """
    name = os.path.basename(originalName)
    #name = name.rsplit(".",1)[0]  # remove extension
    if len(zRange) == 2:
        z = "%02d-%02d" % (zRange[0], zRange[1])
    else:
        z = "%02d" % zRange[0]
    imgName = "%s_%s_z%s_t%02d.%s" % (name, cName, z, t, extension)
    if folder_name is not None:
        imgName = os.path.join(folder_name, imgName)
    # check we don't overwrite existing file
    i = 1
    name = imgName[:-(len(extension)+1)]
    while os.path.exists(imgName):
        imgName = "%s_(%d).%s" % (name, i, extension)
        i += 1
    return imgName


def saveAsOmeTiff(conn, image, folder_name=None):
    """
    Saves the image as an ome.tif in the specified folder
    """

    extension = "ome.tif"
    name = os.path.basename(image.getName())
    imgName = "%s.%s" % (name, extension)
    if folder_name is not None:
        imgName = os.path.join(folder_name, imgName)
    # check we don't overwrite existing file
    i = 1
    pathName = imgName[:-(len(extension)+1)]
    while os.path.exists(imgName):
        imgName = "%s_(%d).%s" % (pathName, i, extension)
        i += 1

    log("  Saving file as: %s" % imgName)
    fileSize, block_gen = image.exportOmeTiff(bufsize=65536)
    f = open(str(imgName), "wb")
    for piece in block_gen:
        f.write(piece)
    #f.seek(0)
    f.close()


def savePlanesForImage(conn, image, sizeC, splitCs, mergedCs,
                       channelNames=None, zRange=None, tRange=None,
                       greyscale=False, zoomPercent=None, projectZ=False,
                       format="PNG", folder_name=None):
    """
    Saves all the required planes for a single image, either as individual
    planes or projection.

    @param renderingEngine:     Rendering Engine, NOT initialised.
    @param queryService:        OMERO query service
    @param imageId:             Image ID
    @param zRange:              Tuple: (zStart, zStop). If None, use default
                                Zindex
    @param tRange:              Tuple: (tStart, tStop). If None, use default
                                Tindex
    @param greyscale:           If true, all visible channels will be
                                greyscale
    @param zoomPercent:         Resize image by this percent if specified.
    @param projectZ:            If true, project over Z range.
    """

    channels = []
    if mergedCs:
        # render merged first with current rendering settings
        channels.append(None)
    if splitCs:
        for i in range(sizeC):
            channels.append(i)

    # set up rendering engine with the pixels
    """
    renderingEngine.lookupPixels(pixelsId)
    if not renderingEngine.lookupRenderingDef(pixelsId):
        renderingEngine.resetDefaults()
    if not renderingEngine.lookupRenderingDef(pixelsId):
        raise "Failed to lookup Rendering Def"
    renderingEngine.load()
    """

    if tRange is None:
        # use 1-based indices throughout script
        tIndexes = [image.getDefaultT()+1]
    else:
        if len(tRange) > 1:
            tIndexes = range(tRange[0], tRange[1])
        else:
            tIndexes = [tRange[0]]

    cName = 'merged'
    for c in channels:
        if c is not None:
            gScale = greyscale
            if c < len(channelNames):
                cName = channelNames[c].replace(" ", "_")
            else:
                cName = "c%02d" % c
        else:
            # if we're rendering 'merged' image - don't want grey!
            gScale = False
        for t in tIndexes:
            if zRange is None:
                defaultZ = image.getDefaultZ()+1
                savePlane(image, format, cName, (defaultZ,), projectZ, t, c,
                          gScale, zoomPercent, folder_name)
            elif projectZ:
                savePlane(image, format, cName, zRange, projectZ, t, c,
                          gScale, zoomPercent, folder_name)
            else:
                if len(zRange) > 1:
                    for z in range(zRange[0], zRange[1]):
                        savePlane(image, format, cName, (z,), projectZ, t, c,
                                  gScale, zoomPercent, folder_name)
                else:
                    savePlane(image, format, cName, zRange, projectZ, t, c,
                              gScale, zoomPercent, folder_name)


def batchImageExport(conn, scriptParams):

    # for params with default values, we can get the value directly
    splitCs = scriptParams["Export_Individual_Channels"]
    mergedCs = scriptParams["Export_Merged_Image"]
    greyscale = scriptParams["Individual_Channels_Grey"]
    dataType = scriptParams["Data_Type"]
    folder_name = scriptParams["Folder_Name"]
    folder_name = os.path.basename(folder_name)
    format = scriptParams["Format"]
    projectZ = "Choose_Z_Section" in scriptParams and \
        scriptParams["Choose_Z_Section"] == 'Max projection'

    if (not splitCs) and (not mergedCs):
        log("Not chosen to save Individual Channels OR Merged Image")
        return

    # check if we have these params
    channelNames = []
    if "Channel_Names" in scriptParams:
        channelNames = scriptParams["Channel_Names"]
    zoomPercent = None
    if "Zoom" in scriptParams and scriptParams["Zoom"] != "100%":
        zoomPercent = int(scriptParams["Zoom"][:-1])

    # functions used below for each imaage.
    def getZrange(sizeZ, scriptParams):
        zRange = None
        if "Choose_Z_Section" in scriptParams:
            zChoice = scriptParams["Choose_Z_Section"]
            # NB: all Z indices in this script are 1-based
            if zChoice == 'ALL Z planes':
                zRange = (1, sizeZ+1)
            elif "OR_specify_Z_index" in scriptParams:
                zIndex = scriptParams["OR_specify_Z_index"]
                zIndex = min(zIndex, sizeZ)
                zRange = (zIndex,)
            elif "OR_specify_Z_start_AND..." in scriptParams and \
                    "...specify_Z_end" in scriptParams:
                start = scriptParams["OR_specify_Z_start_AND..."]
                start = min(start, sizeZ)
                end = scriptParams["...specify_Z_end"]
                end = min(end, sizeZ)
                # in case user got zStart and zEnd mixed up
                zStart = min(start, end)
                zEnd = max(start, end)
                if zStart == zEnd:
                    zRange = (zStart,)
                else:
                    zRange = (zStart, zEnd+1)
        return zRange

    def getTrange(sizeT, scriptParams):
        tRange = None
        if "Choose_T_Section" in scriptParams:
            tChoice = scriptParams["Choose_T_Section"]
            # NB: all T indices in this script are 1-based
            if tChoice == 'ALL T planes':
                tRange = (1, sizeT+1)
            elif "OR_specify_T_index" in scriptParams:
                tIndex = scriptParams["OR_specify_T_index"]
                tIndex = min(tIndex, sizeT)
                tRange = (tIndex,)
            elif "OR_specify_T_start_AND..." in scriptParams and \
                    "...specify_T_end" in scriptParams:
                start = scriptParams["OR_specify_T_start_AND..."]
                start = min(start, sizeT)
                end = scriptParams["...specify_T_end"]
                end = min(end, sizeT)
                # in case user got zStart and zEnd mixed up
                tStart = min(start, end)
                tEnd = max(start, end)
                if tStart == tEnd:
                    tRange = (tStart,)
                else:
                    tRange = (tStart, tEnd+1)
        return tRange

    # Get the images or datasets
    message = ""
    objects, logMessage = script_utils.getObjects(conn, scriptParams)
    message += logMessage
    if not objects:
        return None, message

    # Attach figure to the first image
    parent = objects[0]

    if dataType == 'Dataset':
        images = []
        for ds in objects:
            images.extend(list(ds.listChildren()))
        if not images:
            message += "No image found in dataset(s)"
            return None, message
    else:
        images = objects

    log("Processing %s images" % len(images))

    # somewhere to put images
    curr_dir = os.getcwd()
    exp_dir = os.path.join(curr_dir, folder_name)
    try:
        os.mkdir(exp_dir)
    except:
        pass

    # do the saving to disk

    for img in images:
        if img._prepareRE().requiresPixelsPyramid():
            log("  ** Can't export a 'Big' image to %s. **" % format)
            if len(images) == 1:
                return None, "Can't export a 'Big' image to %s." % format
            continue
        else:
            log("Exporting image as %s: %s" % (format, img.getName()))

        if format == 'OME-TIFF':
            saveAsOmeTiff(conn, img, folder_name)
        else:
            if img._prepareRE().requiresPixelsPyramid():
                log("  ** Can't export a 'Big' image to OME-TIFF. **")
            log("\n----------- Saving planes from image: '%s' ------------"
                % img.getName())
            sizeC = img.getSizeC()
            sizeZ = img.getSizeZ()
            sizeT = img.getSizeT()
            zRange = getZrange(sizeZ, scriptParams)
            tRange = getTrange(sizeT, scriptParams)
            log("Using:")
            if zRange is None:
                log("  Z-index: Last-viewed")
            elif len(zRange) == 1:
                log("  Z-index: %d" % zRange[0])
            else:
                log("  Z-range: %s-%s" % (zRange[0], zRange[1]-1))
            if projectZ:
                log("  Z-projection: ON")
            if tRange is None:
                log("  T-index: Last-viewed")
            elif len(tRange) == 1:
                log("  T-index: %d" % tRange[0])
            else:
                log("  T-range: %s-%s" % (tRange[0], tRange[1]-1))
            log("  Format: %s" % format)
            if zoomPercent is None:
                log("  Image Zoom: 100%")
            else:
                log("  Image Zoom: %s" % zoomPercent)
            log("  Greyscale: %s" % greyscale)
            log("Channel Rendering Settings:")
            for ch in img.getChannels():
                log("  %s: %d-%d"
                    % (ch.getLabel(), ch.getWindowStart(), ch.getWindowEnd()))

            savePlanesForImage(
                conn, img, sizeC, splitCs, mergedCs, channelNames, zRange,
                tRange, greyscale, zoomPercent, projectZ=projectZ,
                format=format, folder_name=folder_name)

        # write log for exported images (not needed for ome-tiff)
        logFile = open(os.path.join(exp_dir, 'Batch_Image_Export.txt'), 'w')
        try:
            for s in logStrings:
                logFile.write(s)
                logFile.write("\n")
        finally:
            logFile.close()

    if len(os.listdir(exp_dir)) == 0:
        return None, "No files exported. See 'info' for more details"
    # zip everything up (unless we've only got a single ome-tiff)
    if format == 'OME-TIFF' and len(os.listdir(exp_dir)) == 1:
        ometiffIds = [t.id for t in parent.listAnnotations(ns=NSOMETIFF)]
        print "Deleting OLD ome-tiffs: %s" % ometiffIds
        conn.deleteObjects("Annotation", ometiffIds)
        export_file = os.path.join(folder_name, os.listdir(exp_dir)[0])
        namespace = NSOMETIFF
        outputDisplayName = "OME-TIFF"
        mimetype = 'image/tiff'
    else:
        export_file = "%s.zip" % folder_name
        compress(export_file, folder_name)
        mimetype = 'application/zip'
        outputDisplayName = "Batch export zip"
        namespace = NSCREATED + "/omero/export_scripts/Batch_Image_Export"

    fileAnnotation, annMessage = script_utils.createLinkFileAnnotation(
        conn, export_file, parent, output=outputDisplayName, ns=namespace,
        mimetype=mimetype)
    message += annMessage
    return fileAnnotation, message


def runScript():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    dataTypes = [rstring('Dataset'), rstring('Image')]
    formats = [rstring('JPEG'), rstring('PNG'), rstring('TIFF'),
               rstring('OME-TIFF')]
    defaultZoption = 'Default-Z (last-viewed)'
    zChoices = [rstring(defaultZoption),
                rstring('ALL Z planes'),
                # currently ImageWrapper only allows full Z-stack projection
                rstring('Max projection'),
                rstring('Other (see below)')]
    defaultToption = 'Default-T (last-viewed)'
    tChoices = [rstring(defaultToption),
                rstring('ALL T planes'),
                rstring('Other (see below)')]
    zoomPercents = omero.rtypes.wrap(["25%", "50%", "100%", "200%",
                                      "300%", "400%"])

    client = scripts.client(
        'Batch_Image_Export.py',
        """Save multiple images as jpegs or pngs in a zip file available for \
download as a batch export.
See http://www.openmicroscopy.org/site/support/omero4/\
users/client-tutorials/insight/insight-util-scripts.html""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=dataTypes,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        scripts.Bool(
            "Export_Individual_Channels", grouping="3",
            description="Save individual channels as separate images",
            default=True),

        scripts.Bool(
            "Individual_Channels_Grey", grouping="3.1",
            description="If true, all individual channel images will be"
            " greyscale", default=False),

        scripts.List(
            "Channel_Names", grouping="3.2",
            description="Names for saving individual channel images"),

        scripts.Bool(
            "Export_Merged_Image", grouping="4",
            description="Save merged image, using current rendering settings",
            default=True),

        scripts.String(
            "Choose_Z_Section", grouping="5",
            description="Default Z is last viewed Z for each image, OR choose"
            " Z below.", values=zChoices, default=defaultZoption),

        scripts.Int(
            "OR_specify_Z_index", grouping="5.1",
            description="Choose a specific Z-index to export", min=1),

        scripts.Int(
            "OR_specify_Z_start_AND...", grouping="5.2",
            description="Choose a specific Z-index to export", min=1),

        scripts.Int(
            "...specify_Z_end", grouping="5.3",
            description="Choose a specific Z-index to export", min=1),

        scripts.String(
            "Choose_T_Section", grouping="6",
            description="Default T is last viewed T for each image, OR choose"
            " T below.", values=tChoices, default=defaultToption),

        scripts.Int(
            "OR_specify_T_index", grouping="6.1",
            description="Choose a specific T-index to export", min=1),

        scripts.Int(
            "OR_specify_T_start_AND...", grouping="6.2",
            description="Choose a specific T-index to export", min=1),

        scripts.Int(
            "...specify_T_end", grouping="6.3",
            description="Choose a specific T-index to export", min=1),

        scripts.String(
            "Zoom", grouping="7", values=zoomPercents,
            description="Zoom (jpeg, png or tiff) before saving with"
            " ANTIALIAS interpolation", default="100%"),

        scripts.String(
            "Format", grouping="8",
            description="Format to save image", values=formats,
            default='JPEG'),

        scripts.String(
            "Folder_Name", grouping="9",
            description="Name of folder (and zip file) to store images",
            default='Batch_Image_Export'),

        version="4.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        startTime = datetime.now()
        scriptParams = {}

        conn = BlitzGateway(client_obj=client)

        # process the list of args above.
        for key in client.getInputKeys():
            if client.getInput(key):
                scriptParams[key] = client.getInput(key, unwrap=True)
        log(scriptParams)

        # call the main script - returns a file annotation wrapper
        fileAnnotation, message = batchImageExport(conn, scriptParams)

        stopTime = datetime.now()
        log("Duration: %s" % str(stopTime-startTime))

        # return this fileAnnotation to the client.
        client.setOutput("Message", rstring(message))
        if fileAnnotation is not None:
                client.setOutput("File_Annotation",
                                 robject(fileAnnotation._obj))

    finally:
        client.closeSession()

if __name__ == "__main__":
    runScript()
