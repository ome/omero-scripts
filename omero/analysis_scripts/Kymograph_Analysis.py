#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 components/tools/OmeroPy/scripts/omero/analysis_scripts/Kymograph_Analysis.py

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

This script is the second Kymograph script, for analyzing lines drawn on
kymograph images that have been created by the 'Kymograph.py' Script. 


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
from omero.rtypes import *
import omero.scripts as scripts
import omero.util.script_utils as scriptUtil
import math
import os


def pointsStringToXYlist(string):
    """
    Method for converting the string returned from omero.model.ShapeI.getPoints()
    into list of (x,y) points.
    E.g: "points[309,427, 366,503, 190,491] points1[309,427, 366,503, 190,491] points2[309,427, 366,503, 190,491]"
    """
    pointLists = string.strip().split("points")
    if len(pointLists) < 2:
        logger.error("Unrecognised ROI shape 'points' string: %s" % string)
        return ""
    firstList = pointLists[1]
    xyList = []
    for xy in firstList.strip(" []").split(", "):
        x, y = xy.split(",")
        xyList.append( ( int( x.strip() ), int(y.strip() ) ) )
    return xyList


def processImages(conn, scriptParams):

    fileAnns = []
    message =""
    # Get the images
    images, logMessage = scriptUtil.getObjects(conn, scriptParams)
    message += logMessage
    if not images:
        return None, message
    # Check for line and polyline ROIs and filter images list
    images = [image for image in images if image.getROICount(["Polyline","Line"])>0]
    if not images:
        message += "No ROI containing line or polyline was found."
        return None, message

    for image in images:
        print "\nAnalysing Image: %s ID: %s" % (image.getName(), image.getId())
        
        if image.getSizeT() > 1:
            message += "%s ID: %s appears to be a time-lapse Image, not a kymograph." % (image.getName(), image.getId())
            continue
        
        roiService = conn.getRoiService()
        result = roiService.findByImage(image.getId(), None)
        
        secsPerPixelY = image.getPixelSizeY()
        micronsPerPixelX = image.getPixelSizeX()
        if secsPerPixelY and micronsPerPixelX:
            micronsPerSec = micronsPerPixelX / secsPerPixelY
        else: micronsPerSec = None
        
        # for each line or polyline, create a row in csv table: y(t), x, dy(dt), dx, x/t (line), x/t (average)
        colNames = "\nt_start (pixels), x_start (pixels), t_end (pixels), x_end (pixels), dt (pixels), dx (pixels), x/t, average x/t, speed(um/sec)"
        tableData = ""
        for roi in result.rois:
            for s in roi.copyShapes():
                if type(s) == omero.model.LineI:
                    tableData += "\nLine"
                    x1 = s.getX1().getValue()
                    x2 = s.getX2().getValue()
                    y1 = s.getY1().getValue()
                    y2 = s.getY2().getValue()
                    dx = abs(x1-x2)
                    dy = abs(y1-y2)
                    dxPerY = float(dx)/dy
                    tableData += "\n"
                    tableData += ",".join([str(x) for x in (y1, x1, y2, x2, dy, dx, dxPerY, dxPerY, "")])
                    if micronsPerSec:
                        speed = dxPerY * micronsPerSec
                        tableData += "%s" % speed
            
                elif type(s) == omero.model.PolylineI:
                    tableData += "\nPolyline"
                    points = pointsStringToXYlist(s.getPoints().getValue())
                    xStart, yStart = points[0]
                    for i in range(1, len(points)):
                        x1, y1 = points[i-1]
                        x2, y2 = points[i]
                        dx = abs(x1-x2)
                        dy = abs(y1-y2)
                        dxPerY = float(dx)/dy
                        avXperY = abs(float(x2-xStart)/(y2-yStart))
                        tableData += "\n"
                        tableData += ",".join([str(x) for x in (y1, x1, y2, x2, dy, dx, dxPerY, avXperY, "")])
                        if micronsPerSec:
                            speed = dxPerY * micronsPerSec
                            tableData += "%s" % speed

        # write table data to csv...
        if len(tableData) > 0:
            tableString = "secsPerPixelY: %s" % secsPerPixelY
            tableString += '\nmicronsPerPixelX: %s' % micronsPerPixelX
            tableString += "\nmicronsPerSec: %s" % micronsPerSec
            tableString += "\n"
            tableString += colNames 
            tableString += tableData
            print tableString
            csvFileName = 'kymograph_velocities_%s.csv' % image.getId()
            csvFile = open(csvFileName, 'w')
            try:
                csvFile.write(tableString)
            finally:
                csvFile.close()

            fileAnn, faMessage = scriptUtil.createLinkFileAnnotation(conn, csvFileName, image, 
                output="Line Plot csv (Excel) file", mimetype="text/csv", desc=None)
            print fileAnn, faMessage
            if fileAnn:
                fileAnns.append(fileAnn)
        else:
            print "Found NO lines or polylines to analyse for Image"

    if not fileAnns:
        faMessage = "No Analysis files created. See 'Info' or 'Error' for more details"
    elif len(fileAnns) > 1:
        faMessage = "Created %s csv (Excel) files" % len(fileAnns)
    message += faMessage
    return fileAnns, message
                        

if __name__ == "__main__":

    dataTypes = [rstring('Image')]

    client = scripts.client('Kymograph_Analysis.py', """This script analyses Kymograph images, which have Line or PolyLine ROIs that
track moving objects. It generates a table of the speed of movement, saved as an Excell / csv file.""",

    scripts.String("Data_Type", optional=False, grouping="1",
        description="Choose source of images (only Image supported)", values=dataTypes, default="Image"),

    scripts.List("IDs", optional=False, grouping="2",
        description="List of Image IDs to process.").ofType(rlong(0)),

    version = "4.3.3",
    authors = ["William Moore", "OME Team"],
    institutions = ["University of Dundee"],
    contact = "ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        # process the list of args above.
        scriptParams = {}
        for key in client.getInputKeys():
            if client.getInput(key):
                scriptParams[key] = client.getInput(key, unwrap=True)

        print scriptParams

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        fileAnns, message = processImages(conn, scriptParams)
        
        if fileAnns:
            if len(fileAnns) == 1:
                client.setOutput("Line_Data", robject(fileAnns[0]._obj))
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()