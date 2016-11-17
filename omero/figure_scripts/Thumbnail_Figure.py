#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 components/tools/OmeroPy/scripts/omero/figure_scripts/Thumbnail_Figure.py

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

This script displays a bunch of thumbnails from OMERO as a jpg or png, saved
back to the server as a FileAnnotation attached to the parent dataset or
project.

@author  William Moore &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@author  Jean-Marie Burel &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:j.burel@dundee.ac.uk">j.burel@dundee.ac.uk</a>
@author Donald MacDonald &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:donald@lifesci.dundee.ac.uk">donald@lifesci.dundee.ac.uk</a>
@version 3.0
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.1

"""
import omero.scripts as scripts
from omero.gateway import BlitzGateway
import omero.util.script_utils as scriptUtil
from omero.rtypes import rlong, rstring, robject
import omero.util.imageUtil as imgUtil
from omero.constants.namespaces import NSCREATED
import os

try:
    from PIL import Image, ImageDraw  # see ticket:2597
except ImportError:
    import Image
    import ImageDraw  # see ticket:2597

WHITE = (255, 255, 255)

logLines = []    # make a log / legend of the figure


def log(text):
    """
    Adds lines of text to the logLines list, so they can be collected into a
    figure legend.
    """
    try:
        text = text.encode('utf8')
    except:
        pass
    print text
    logLines.append(text)


def sortImagesByTag(tagIds, imgTags):

    # prepare list of {'iid': imgId, 'tagKey' : stringToSort }
    # E.g. if tagIds = [5, 3, 9], we map to 'a', 'b', 'c',
    # so an Image with tags 3 & 9 will have 'tagKey': "bc"
    letters = 'abcdefghijklmnopqrstuvwxyz'
    # assume we have less than 26 tags!
    sortedImages = []
    for iid, tagIdList in imgTags.items():
        orderedIndexes = []
        orderedTags = []
        for i, tid in enumerate(tagIds):
            if tid in tagIdList:
                orderedIndexes.append(letters[i])
                orderedTags.append(tid)
        if len(orderedIndexes) > 0:
            tagKey = "".join(orderedIndexes)
        else:
            tagKey = "z"
        sortedImages.append({
            'iid': iid,
            'tagKey': tagKey,
            'tagIds': orderedTags})

    sortedImages.sort(key=lambda x: x['tagKey'])

    # clean up our 'z' sorting hack above.
    for i in sortedImages:
        if i['tagKey'] == "z":
            i['tagKey'] = ""

    return sortedImages


def paintDatasetCanvas(conn, images, title, tagIds=None, showUntagged=False,
                       colCount=10, length=100):
    """
        Paints and returns a canvas of thumbnails from images, laid out in a
        set number of columns.
        Title and date-range of the images is printed above the thumbnails,
        to the left and right, respectively.

        @param conn:        Blitz connection
        @param imageIds:    Image IDs
        @param title:       title to display at top of figure. String
        @param tagIds:      Optional to sort thumbnails by tag. [long]
        @param colCount:    Max number of columns to lay out thumbnails
        @param length:      Length of longest side of thumbnails
    """

    mode = "RGB"
    figCanvas = None
    spacing = length/40 + 2

    thumbnailStore = conn.createThumbnailStore()
    # returns  omero.api.ThumbnailStorePrx
    metadataService = conn.getMetadataService()

    if len(images) == 0:
        return None
    timestampMin = images[0].getDate()   # datetime
    timestampMax = timestampMin

    dsImageIds = []
    imagePixelMap = {}
    imageNames = {}

    # sort the images by name
    images.sort(key=lambda x: (x.getName().lower()))

    for image in images:
        imageId = image.getId()
        pixelId = image.getPrimaryPixels().getId()
        name = image.getName()
        dsImageIds.append(imageId)        # make a list of image-IDs
        imagePixelMap[imageId] = pixelId    # and a map of image-ID: pixel-ID
        imageNames[imageId] = name
        timestampMin = min(timestampMin, image.getDate())
        timestampMax = max(timestampMax, image.getDate())

    # set-up fonts
    fontsize = length/7 + 5
    font = imgUtil.getFont(fontsize)
    textHeight = font.getsize("Textq")[1]
    topSpacer = spacing + textHeight
    leftSpacer = spacing + textHeight

    tagPanes = []
    maxWidth = 0
    totalHeight = topSpacer

    # if we have a list of tags, then sort images by tag
    if tagIds:
        # Cast to int since List can be any type
        tagIds = [int(tagId) for tagId in tagIds]
        log(" Sorting images by tags: %s" % tagIds)
        tagNames = {}
        taggedImages = {}    # a map of tagId: list-of-image-Ids
        imgTags = {}        # a map of imgId: list-of-tagIds
        for tagId in tagIds:
            taggedImages[tagId] = []

        # look for images that have a tag
        types = ["ome.model.annotations.TagAnnotation"]
        annotations = metadataService.loadAnnotations(
            "Image", dsImageIds, types, None, None)
        # filter images by annotation...
        for imageId, tags in annotations.items():
            imgTagIds = []
            for tag in tags:
                tagId = tag.getId().getValue()
                # make a dict of tag-names
                tagNames[tagId] = tag.getTextValue().getValue().decode('utf8')
                print "     Tag:", tagId, tagId in tagIds
                imgTagIds.append(tagId)
            imgTags[imageId] = imgTagIds

        # get a sorted list of {'iid': iid, 'tagKey': tagKey,
        # 'tagIds':orderedTags}
        sortedThumbs = sortImagesByTag(tagIds, imgTags)

        if not showUntagged:
            sortedThumbs = [t for t in sortedThumbs if len(t['tagIds']) > 0]

        # Need to group sets of thumbnails by FIRST tag.
        toptagSets = []
        groupedPixelIds = []
        showSubsetLabels = False
        currentTagStr = None
        for i, img in enumerate(sortedThumbs):
            tagIds = img['tagIds']
            if len(tagIds) == 0:
                tagString = "Not Tagged"
            else:
                tagString = tagNames[tagIds[0]]
            if tagString == currentTagStr or currentTagStr is None:
                # only show subset labels (later) if there are more than 1
                # subset
                if (len(tagIds) > 1):
                    showSubsetLabels = True
                groupedPixelIds.append({
                    'pid': imagePixelMap[img['iid']],
                    'tagIds': tagIds})
            else:
                toptagSets.append({
                    'tagText': currentTagStr,
                    'pixelIds': groupedPixelIds,
                    'showSubsetLabels': showSubsetLabels})
                showSubsetLabels = len(tagIds) > 1
                groupedPixelIds = [{
                    'pid': imagePixelMap[img['iid']],
                    'tagIds': tagIds}]
            currentTagStr = tagString
        toptagSets.append({
            'tagText': currentTagStr,
            'pixelIds': groupedPixelIds,
            'showSubsetLabels': showSubsetLabels})

        # Find the indent we need
        maxTagNameWidth = max([font.getsize(ts['tagText'])[0]
                               for ts in toptagSets])
        if showUntagged:
            maxTagNameWidth = max(maxTagNameWidth,
                                  font.getsize("Not Tagged")[0])

        print "toptagSets", toptagSets

        tagSubPanes = []

        # make a canvas for each tag combination
        def makeTagsetCanvas(tagString, tagsetPixIds, showSubsetLabels):
            log(" Tagset: %s  (contains %d images)"
                % (tagString, len(tagsetPixIds)))
            if not showSubsetLabels:
                tagString = None
            subCanvas = imgUtil.paintThumbnailGrid(
                thumbnailStore, length,
                spacing, tagsetPixIds, colCount, topLabel=tagString)
            tagSubPanes.append(subCanvas)

        for toptagSet in toptagSets:
            tagText = toptagSet['tagText']
            showSubsetLabels = toptagSet['showSubsetLabels']
            imageData = toptagSet['pixelIds']
            # loop through all thumbs under TAG, grouping into subsets.
            tagsetPixIds = []
            currentTagStr = None
            for i, img in enumerate(imageData):
                tag_ids = img['tagIds']
                pid = img['pid']
                tagString = ", ".join([tagNames[tid] for tid in tag_ids])
                if tagString == "":
                    tagString = "Not Tagged"
                # Keep grouping thumbs under similar tag set (if not on the
                # last loop)
                if tagString == currentTagStr or currentTagStr is None:
                    tagsetPixIds.append(pid)
                else:
                    # Process thumbs added so far
                    makeTagsetCanvas(currentTagStr, tagsetPixIds,
                                     showSubsetLabels)
                    # reset for next tagset
                    tagsetPixIds = [pid]
                currentTagStr = tagString

            makeTagsetCanvas(currentTagStr, tagsetPixIds, showSubsetLabels)

            maxWidth = max([c.size[0] for c in tagSubPanes])
            totalHeight = sum([c.size[1] for c in tagSubPanes])

            # paste them into a single canvas for each Tag

            leftSpacer = spacing + maxTagNameWidth + 2*spacing
            # Draw vertical line to right
            size = (leftSpacer + maxWidth, totalHeight)
            tagCanvas = Image.new(mode, size, WHITE)
            pX = leftSpacer
            pY = 0
            for pane in tagSubPanes:
                imgUtil.pasteImage(pane, tagCanvas, pX, pY)
                pY += pane.size[1]
            if tagText is not None:
                draw = ImageDraw.Draw(tagCanvas)
                tt_w, tt_h = font.getsize(tagText)
                h_offset = (totalHeight - tt_h)/2
                draw.text((spacing, h_offset), tagText, font=font,
                          fill=(50, 50, 50))
            # draw vertical line
            draw.line((leftSpacer-spacing, 0, leftSpacer - spacing,
                       totalHeight), fill=(0, 0, 0))
            tagPanes.append(tagCanvas)
            tagSubPanes = []
    else:
        leftSpacer = spacing
        pixelIds = []
        for imageId in dsImageIds:
            log("  Name: %s  ID: %d" % (imageNames[imageId], imageId))
            pixelIds.append(imagePixelMap[imageId])
        figCanvas = imgUtil.paintThumbnailGrid(
            thumbnailStore, length, spacing, pixelIds, colCount)
        tagPanes.append(figCanvas)

    # paste them into a single canvas
    tagsetSpacer = length / 3
    maxWidth = max([c.size[0] for c in tagPanes])
    totalHeight = totalHeight + sum([c.size[1]+tagsetSpacer
                                     for c in tagPanes]) - tagsetSpacer
    size = (maxWidth, totalHeight)
    fullCanvas = Image.new(mode, size, WHITE)
    pX = 0
    pY = topSpacer
    for pane in tagPanes:
        imgUtil.pasteImage(pane, fullCanvas, pX, pY)
        pY += pane.size[1] + tagsetSpacer

    # create dates for the image timestamps. If dates are not the same, show
    # first - last.
    # firstdate = timestampMin
    # lastdate = timestampMax
    # figureDate = str(firstdate)
    # if firstdate != lastdate:
    #     figureDate = "%s - %s" % (firstdate, lastdate)

    draw = ImageDraw.Draw(fullCanvas)
    # dateWidth = draw.textsize(figureDate, font=font)[0]
    # titleWidth = draw.textsize(title, font=font)[0]
    dateY = spacing
    # dateX = fullCanvas.size[0] - spacing - dateWidth
    draw.text((leftSpacer, dateY), title, font=font, fill=(0, 0, 0))  # title
    # Don't show dates: see
    # https://github.com/openmicroscopy/openmicroscopy/pull/1002
    # if (leftSpacer+titleWidth) < dateX:
    # if there's enough space...
    #     draw.text((dateX, dateY), figureDate, font=font, fill=(0,0,0))
    # add date

    return fullCanvas


def makeThumbnailFigure(conn, scriptParams):
    """
    Makes the figure using the parameters in @scriptParams, attaches the
    figure to the parent Project/Dataset, and returns the file-annotation ID

    @ returns       Returns the id of the originalFileLink child. (ID object,
                    not value)
    """

    log("Thumbnail figure created by OMERO")
    log("")

    message = ""

    # Get the objects (images or datasets)
    objects, logMessage = scriptUtil.getObjects(conn, scriptParams)
    message += logMessage
    if not objects:
        return None, message

    # Get parent
    parent = None
    if "Parent_ID" in scriptParams and len(scriptParams["IDs"]) > 1:
        if scriptParams["Data_Type"] == "Image":
            parent = conn.getObject("Dataset", scriptParams["Parent_ID"])
        else:
            parent = conn.getObject("Project", scriptParams["Parent_ID"])

    if parent is None:
        parent = objects[0]  # Attach figure to the first object

    parentClass = parent.OMERO_CLASS
    log("Figure will be linked to %s%s: %s"
        % (parentClass[0].lower(), parentClass[1:], parent.getName()))

    tagIds = []
    if "Tag_IDs" in scriptParams:
        tagIds = scriptParams['Tag_IDs']
    if len(tagIds) == 0:
        tagIds = None

    showUntagged = False
    if (tagIds):
        showUntagged = scriptParams["Show_Untagged_Images"]

    thumbSize = scriptParams["Thumbnail_Size"]
    maxColumns = scriptParams["Max_Columns"]

    figHeight = 0
    figWidth = 0
    dsCanvases = []

    if scriptParams["Data_Type"] == "Dataset":
        for dataset in objects:
            log("Dataset: %s     ID: %d"
                % (dataset.getName(), dataset.getId()))
            images = list(dataset.listChildren())
            title = dataset.getName().decode('utf8')
            dsCanvas = paintDatasetCanvas(
                conn, images, title, tagIds, showUntagged,
                length=thumbSize, colCount=maxColumns)
            if dsCanvas is None:
                continue
            dsCanvases.append(dsCanvas)
            figHeight += dsCanvas.size[1]
            figWidth = max(figWidth, dsCanvas.size[0])
    else:
        imageCanvas = paintDatasetCanvas(
            conn, objects, "", tagIds,
            showUntagged, length=thumbSize, colCount=maxColumns)
        dsCanvases.append(imageCanvas)
        figHeight += imageCanvas.size[1]
        figWidth = max(figWidth, imageCanvas.size[0])

    if len(dsCanvases) == 0:
        message += "No figure created"
        return None, message

    figure = Image.new("RGB", (figWidth, figHeight), WHITE)
    y = 0
    for ds in dsCanvases:
        imgUtil.pasteImage(ds, figure, 0, y)
        y += ds.size[1]

    log("")
    figLegend = "\n".join(logLines)

    format = scriptParams["Format"]
    figureName = scriptParams["Figure_Name"]
    figureName = os.path.basename(figureName)
    output = "localfile"

    if format == 'PNG':
        output = output + ".png"
        figureName = figureName + ".png"
        figure.save(output, "PNG")
        mimetype = "image/png"
    elif format == 'TIFF':
        output = output + ".tiff"
        figureName = figureName + ".tiff"
        figure.save(output, "TIFF")
        mimetype = "image/tiff"
    else:
        output = output + ".jpg"
        figureName = figureName + ".jpg"
        figure.save(output)
        mimetype = "image/jpeg"

    namespace = NSCREATED + "/omero/figure_scripts/Thumbnail_Figure"
    fileAnnotation, faMessage = scriptUtil.createLinkFileAnnotation(
        conn, output, parent, output="Thumbnail figure", mimetype=mimetype,
        ns=namespace, desc=figLegend, origFilePathAndName=figureName)
    message += faMessage

    return fileAnnotation, message


def runAsScript():
    """
    The main entry point of the script. Gets the parameters from the scripting
    service, makes the figure and returns the output to the client.
    def __init__(self, name, optional = False, out = False, description =
    None, type = None, min = None, max = None, values = None)
    """

    formats = [rstring('JPEG'), rstring('PNG'), rstring('TIFF')]
    dataTypes = [rstring('Dataset'), rstring('Image')]

    client = scripts.client(
        'Thumbnail_Figure.py',
        """Export a figure of thumbnails, optionally sorted by tag.
See http://help.openmicroscopy.org/publish.html#figures""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.",
            values=dataTypes, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image"
            " IDs").ofType(rlong(0)),

        scripts.List(
            "Tag_IDs", grouping="3",
            description="Group thumbnails by these tags."),

        scripts.Bool(
            "Show_Untagged_Images", grouping="3.1", default=False,
            description="If true (and you're sorting by tagIds) also"
            " show images without the specified tags"),

        scripts.Long(
            "Parent_ID", grouping="4",
            description="Attach figure to this Project (if datasetIds"
            " above) or Dataset if imageIds. If not specifed, attach"
            " figure to first dataset or image."),
        # this will be ignored if only a single ID in list - attach to
        # that object instead.

        scripts.Int(
            "Thumbnail_Size", grouping="5", min=10, max=250, default=100,
            description="The dimension of each thumbnail. Default is 100"),

        scripts.Int(
            "Max_Columns", grouping="5.1", min=1, default=10,
            description="The max number of thumbnail columns. Default is 10"),

        scripts.String(
            "Format", grouping="6",
            description="Format to save image.", values=formats,
            default="JPEG"),

        scripts.String(
            "Figure_Name", grouping="6.1", default='Thumbnail_Figure',
            description="File name of figure to create"),

        version="4.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
        )

    try:
        conn = BlitzGateway(client_obj=client)

        commandArgs = client.getInputs(unwrap=True)
        print commandArgs

        # Makes the figure and attaches it to Project/Dataset. Returns
        # FileAnnotationI object
        fileAnnotation, message = makeThumbnailFigure(conn, commandArgs)

        # Return message and file annotation (if applicable) to the client
        client.setOutput("Message", rstring(message))
        if fileAnnotation is not None:
            client.setOutput("File_Annotation", robject(fileAnnotation._obj))
    finally:
        conn.close()


if __name__ == "__main__":
    runAsScript()
