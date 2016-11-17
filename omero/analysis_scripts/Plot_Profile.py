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

This script processes Images which have Line or PolyLine ROIs,
saving the intensity of chosen channels to Excel (csv) files.

@author Will Moore
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 4.3.3
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.3.3
"""

from omero.gateway import BlitzGateway
import omero
from omero.rtypes import rstring, rlong, robject
import omero.scripts as scripts
import omero.util.script_utils as scriptUtil
from numpy import math, zeros, hstack, vstack, average
import logging

logger = logging.getLogger('plot_profile')


def getLineData(pixels, x1, y1, x2, y2, lineW=2, theZ=0, theC=0, theT=0):
    """
    Grabs pixel data covering the specified line, and rotates it horizontally
    so that x1,y1 is to the left,
    Returning a numpy 2d array. Used by Kymograph.py script.
    Uses PIL to handle rotating and interpolating the data. Converts to numpy
    to PIL and back (may change dtype.)

    @param pixels:          PixelsWrapper object
    @param x1, y1, x2, y2:  Coordinates of line
    @param lineW:           Width of the line we want
    @param theZ:            Z index within pixels
    @param theC:            Channel index
    @param theT:            Time index
    """

    from numpy import asarray, int32

    sizeX = pixels.getSizeX()
    sizeY = pixels.getSizeY()

    lineX = x2-x1
    lineY = 1 if y2-y1 == 0 else y2-y1

    rads = math.atan(float(lineX) / lineY)

    # How much extra Height do we need, top and bottom?
    extraH = abs(math.sin(rads) * lineW)
    bottom = int(max(y1, y2) + extraH/2)
    top = int(min(y1, y2) - extraH/2)

    # How much extra width do we need, left and right?
    extraW = abs(math.cos(rads) * lineW)
    left = int(min(x1, x2) - extraW)
    right = int(max(x1, x2) + extraW)

    # What's the larger area we need? - Are we outside the image?
    pad_left, pad_right, pad_top, pad_bottom = 0, 0, 0, 0
    if left < 0:
        pad_left = abs(left)
        left = 0
    x = left
    if top < 0:
        pad_top = abs(top)
        top = 0
    y = top
    if right > sizeX:
        pad_right = right - sizeX
        right = sizeX
    w = int(right - left)
    if bottom > sizeY:
        pad_bottom = bottom - sizeY
        bottom = sizeY
    h = int(bottom - top)
    tile = (x, y, w, h)

    # get the Tile
    plane = pixels.getTile(theZ, theC, theT, tile)

    # pad if we wanted a bigger region
    if pad_left > 0:
        data_h, data_w = plane.shape
        pad_data = zeros((data_h, pad_left), dtype=plane.dtype)
        plane = hstack((pad_data, plane))
    if pad_right > 0:
        data_h, data_w = plane.shape
        pad_data = zeros((data_h, pad_right), dtype=plane.dtype)
        plane = hstack((plane, pad_data))
    if pad_top > 0:
        data_h, data_w = plane.shape
        pad_data = zeros((pad_top, data_w), dtype=plane.dtype)
        plane = vstack((pad_data, plane))
    if pad_bottom > 0:
        data_h, data_w = plane.shape
        pad_data = zeros((pad_bottom, data_w), dtype=plane.dtype)
        plane = vstack((plane, pad_data))

    pil = scriptUtil.numpy_to_image(plane, (plane.min(), plane.max()), int32)
    # pil.show()

    # Now need to rotate so that x1,y1 is horizontally to the left of x2,y2
    toRotate = 90 - math.degrees(rads)

    if x1 > x2:
        toRotate += 180
    # filter=Image.BICUBIC see
    # http://www.ncbi.nlm.nih.gov/pmc/articles/PMC2172449/
    rotated = pil.rotate(toRotate, expand=True)
    # rotated.show()

    # finally we need to crop to the length of the line
    length = int(math.sqrt(math.pow(lineX, 2) + math.pow(lineY, 2)))
    rotW, rotH = rotated.size
    cropX = (rotW - length)/2
    cropX2 = cropX + length
    cropY = (rotH - lineW)/2
    cropY2 = cropY + lineW
    cropped = rotated.crop((cropX, cropY, cropX2, cropY2))
    # cropped.show()
    return asarray(cropped)


def pointsStringToXYlist(string):
    """
    Method for converting the string returned from
    omero.model.ShapeI.getPoints()
    into list of (x,y) points.
    E.g: "points[309,427, 366,503, 190,491] points1[309,427, 366,503, 190,491]
    points2[309,427, 366,503, 190,491]"
    """
    pointLists = string.strip().split("points")
    if len(pointLists) < 2:
        logger.error("Unrecognised ROI shape 'points' string: %s" % string)
        return ""
    firstList = pointLists[1]
    xyList = []
    for xy in firstList.strip(" []").split(", "):
        x, y = xy.split(",")
        xyList.append((int(x.strip()), int(y.strip())))
    return xyList


def processPolyLines(conn, scriptParams, image, polylines, lineWidth, fout):
    """
    Output data from one or more polylines on an image. Attach csv to image.

    @param polylines:       list of theT:T, theZ:Z, points: list of (x,y)}
    """
    pixels = image.getPrimaryPixels()
    theCs = scriptParams['Channels']

    for pl in polylines:
        theT = pl['theT']
        theZ = pl['theZ']
        roiId = pl['id']
        points = pl['points']
        for theC in theCs:
            lData = []
            for l in range(len(points)-1):
                x1, y1 = points[l]
                x2, y2 = points[l+1]
                ld = getLineData(
                    pixels, x1, y1, x2, y2, lineWidth,
                    theZ, theC, theT)
                lData.append(ld)
            lineData = hstack(lData)

            print 'Image_ID, ROI_ID, Z, T, C, PolylineData.shape:" \
                " %s, %s, %s, %s, %s, %s' \
                % (image.getId(), roiId, theZ+1, theT+1, theC+1,
                   str(lineData.shape))

            if scriptParams['Sum_or_Average'] == 'Sum':
                outputData = lineData.sum(axis=0)
            else:
                outputData = average(lineData, axis=0)

            lineHeader = scriptParams['Sum_or_Average'] == \
                'Average, with raw data' and 'Average,' or ""

            # Image_ID, ROI_ID, Z, T, C, Line data
            fout.write('%s,%s,%s,%s,%s,%s' % (image.getId(), roiId, theZ+1,
                       theT+1, theC+1, lineHeader))
            fout.write(','.join([str(d) for d in outputData]))
            fout.write('\n')

            # Optionally output raw data for each row of raw line data
            if scriptParams['Sum_or_Average'] == 'Average, with raw data':
                for r in range(lineWidth):
                    fout.write('%s,%s,%s,%s,%s,%s,' % (image.getId(), roiId,
                               theZ+1, theT+1, theC+1, r))
                    fout.write(','.join([str(d) for d in lineData[r]]))
                    fout.write('\n')


def processLines(conn, scriptParams, image, lines, lineWidth, fout):
    """
    Creates a new kymograph Image from one or more lines.
    If one line, use this for every time point.
    If multiple lines, use the first one for length and all the remaining ones
    for x1,y1 and direction, making all subsequent lines the same length as
    the first.
    """

    pixels = image.getPrimaryPixels()
    theCs = scriptParams['Channels']

    for l in lines:
        theT = l['theT']
        theZ = l['theZ']
        roiId = l['id']
        for theC in theCs:
            lineData = []
            lineData = getLineData(pixels, l['x1'],
                                   l['y1'], l['x2'], l['y2'], lineWidth,
                                   theZ, theC, theT)

            print 'Image_ID, ROI_ID, Z, T, C, LineData.shape:" \
                " %s, %s, %s, %s, %s, %s' \
                % (image.getId(), roiId, theZ+1,
                   theT+1, theC+1, str(lineData.shape))

            if scriptParams['Sum_or_Average'] == 'Sum':
                outputData = lineData.sum(axis=0)
            else:
                outputData = average(lineData, axis=0)

            lineHeader = scriptParams['Sum_or_Average'] == \
                'Average, with raw data' and 'Average,' or ""

            # Image_ID, ROI_ID, Z, T, C, Line data
            fout.write('%s,%s,%s,%s,%s,%s' % (image.getId(), roiId, theZ+1,
                       theT+1, theC+1, lineHeader))
            fout.write(','.join([str(d) for d in outputData]))
            fout.write('\n')

            # Optionally output raw data for each row of raw line data
            if scriptParams['Sum_or_Average'] == 'Average, with raw data':
                for r in range(lineWidth):
                    fout.write('%s,%s,%s,%s,%s,%s,' % (image.getId(), roiId,
                               theZ+1, theT+1, theC+1, r))
                    fout.write(','.join([str(d) for d in lineData[r]]))
                    fout.write('\n')


def processImages(conn, scriptParams):

    lineWidth = scriptParams['Line_Width']
    fileAnns = []
    message = ""

    # Get the images
    images, logMessage = scriptUtil.getObjects(conn, scriptParams)
    message += logMessage
    if not images:
        return None, message

    # Check for line and polyline ROIs and filter images list
    images = [image for image in images if
              image.getROICount(["Polyline", "Line"]) > 0]
    if not images:
        message += "No ROI containing line or polyline was found."
        return None, message

    for image in images:

        cNames = []
        colors = []
        for ch in image.getChannels():
            cNames.append(ch.getLabel())
            colors.append(ch.getColor().getRGB())

        sizeC = image.getSizeC()

        if 'Channels' in scriptParams:
            scriptParams['Channels'] = [i-1 for i in scriptParams['Channels']]
            # Convert user input from 1-based to 0-based
            for i in scriptParams['Channels']:
                print i, type(i)
        else:
            scriptParams['Channels'] = range(sizeC)

        # channelMinMax = []
        # for c in image.getChannels():
        #     minC = c.getWindowMin()
        #     maxC = c.getWindowMax()
        #     channelMinMax.append((minC, maxC))

        roiService = conn.getRoiService()
        result = roiService.findByImage(image.getId(), None)

        lines = []
        polylines = []

        for roi in result.rois:
            roiId = roi.getId().getValue()
            for s in roi.copyShapes():
                theZ = s.getTheZ() and s.getTheZ().getValue() or 0
                theT = s.getTheT() and s.getTheT().getValue() or 0
                # TODO: Add some filter of shapes. E.g. text? / 'lines' only
                # etc.
                if type(s) == omero.model.LineI:
                    x1 = s.getX1().getValue()
                    x2 = s.getX2().getValue()
                    y1 = s.getY1().getValue()
                    y2 = s.getY2().getValue()
                    lines.append({'id': roiId, 'theT': theT, 'theZ': theZ,
                                  'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})

                elif type(s) == omero.model.PolylineI:
                    points = pointsStringToXYlist(s.getPoints().getValue())
                    polylines.append({'id': roiId, 'theT': theT, 'theZ': theZ,
                                      'points': points})

        if len(lines) == 0 and len(polylines) == 0:
            print "Image: %s had no lines or polylines" % image.getId()
            continue

        # prepare column headers, including line-id if we are going to output
        # raw data.
        lineId = scriptParams['Sum_or_Average'] == 'Average, with raw data' \
            and 'Line, ' or ""
        colHeader = 'Image_ID, ROI_ID, Z, T, C, %sLine data %s of Line" \
            " Width %s\n' % (lineId, scriptParams['Sum_or_Average'],
                             scriptParams['Line_Width'])
        print 'colHeader', colHeader

        # prepare a csv file to write our data to...
        fileName = "Plot_Profile_%s.csv" % image.getId()
        try:
            f = open(fileName, 'w')
            f.write(colHeader)
            if len(lines) > 0:
                processLines(conn, scriptParams, image, lines, lineWidth, f)
            if len(polylines) > 0:
                processPolyLines(
                    conn, scriptParams, image, polylines, lineWidth, f)
        finally:
            f.close()

        fileAnn, faMessage = scriptUtil.createLinkFileAnnotation(
            conn, fileName, image, output="Line Plot csv (Excel) file",
            mimetype="text/csv", desc=None)
        if fileAnn:
            fileAnns.append(fileAnn)

    if not fileAnns:
        faMessage = "No Analysis files created. See 'Info' or 'Error' for"\
            " more details"
    elif len(fileAnns) > 1:
        faMessage = "Created %s csv (Excel) files" % len(fileAnns)
    message += faMessage

    return fileAnns, message


if __name__ == "__main__":

    dataTypes = [rstring('Image')]
    sumAvgOptions = [rstring('Average'),
                     rstring('Sum'),
                     rstring('Average, with raw data')]

    client = scripts.client(
        'Plot_Profile.py',
        """This script processes Images, which have Line or PolyLine ROIs \
and outputs the data as CSV files, for plotting in e.g. Excel.""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images (only Image supported).",
            values=dataTypes, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Image IDs to process.").ofType(rlong(0)),

        scripts.Int(
            "Line_Width", optional=False, grouping="3", default=1,
            description="Width in pixels of each line plot.", min=1),

        scripts.String(
            "Sum_or_Average", optional=False, grouping="3.1",
            description="Output the Sum or Average (mean) of Line Profile."
            " Option to include ALL line data with Average.",
            default='Average', values=sumAvgOptions),

        scripts.List(
            "Channels", grouping="4",
            description="Optional list of Channels to process. E.g 1, 2. Use"
            " ALL Channels by default.").ofType(omero.rtypes.rint(0)),

        version="4.3.3",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        scriptParams = client.getInputs(unwrap=True)
        print scriptParams

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        fileAnns, message = processImages(conn, scriptParams)

        if fileAnns:
            if len(fileAnns) == 1:
                client.setOutput("Line_Data", robject(fileAnns[0]._obj))
        client.setOutput("Message", rstring(message))

    finally:
        conn.close()
