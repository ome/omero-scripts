#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 components/tools/OmeroPy/scripts/omero/util_scripts/Min_Max.py

-----------------------------------------------------------------------------
  Copyright (C) 2015 University of Dundee. All rights reserved.

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
"""

from omero.gateway import BlitzGateway
from omero.model import StatsInfoI
from omero.rtypes import rdouble, rlong, rstring
from omero.util.tiles import TileLoop, TileLoopIteration

import omero.scripts as scripts
import omero.util.script_utils as script_utils

from collections import defaultdict

from numpy import amin, amax, iinfo
from numpy import average as avg


def calcStatsInfo(conn, imageId):
    """
    Process a single image here: creating a new StatsInfo object
    if necessary.

    @param imageId:             Original image
    """

    oldImage = conn.getObject("Image", imageId)
    if oldImage is None:
        raise Exception("Image not found for ID:" % imageId)

    sizeX = oldImage.getSizeX()
    sizeY = oldImage.getSizeY()
    sizeZ = oldImage.getSizeZ()
    sizeC = oldImage.getSizeC()
    sizeT = oldImage.getSizeT()
    tileW = min(256, sizeX)
    tileH = min(256, sizeY)

    zctMap = defaultdict(list)

    class Loop(TileLoop):

        def createData(self):
            return self

        def close(self):
            pass

    class Iteration(TileLoopIteration):

        def run(self, data, z, c, t, x, y,
                tileWidth, tileHeight, tileCount):
            zctMap[c].append(
                (z, c, t, (x, y, tileWidth, tileHeight)))

    Loop().forEachTile(
        sizeX, sizeY,
        sizeZ, sizeC, sizeT,
        tileW, tileH, Iteration())

    def channelGen():
        pixels = oldImage.getPrimaryPixels()
        rv = dict()
        dt = pixels.getTile(0, 0, 0, (0, 0, 16, 16)).dtype
        tile_min = iinfo(dt).max  # Everything is less
        tile_max = iinfo(dt).min  # Everything is more
        for c, zctTileList in zctMap.items():
            for tileInfo in zctTileList:
                tile = pixels.getTile(*tileInfo)
                tile_min = min(tile_min, amin(tile))
                tile_max = max(tile_max, amax(tile))
            rv[c] = (tile_min, tile_max)
        yield rv

    statsInfos = dict()
    for x in channelGen():
        statsInfos.update(x)
    return statsInfos


def processImages(conn, scriptParams):
    """
    Process the script params to make a list of channel_offsets, then iterate
    through the images creating a new image from each with the specified
    channel offsets
    """

    message = ""
    images, logMessage = script_utils.getObjects(conn, scriptParams)
    message += logMessage
    if not images:
        raise Exception("No images found")
    imageIds = sorted(set([i.getId() for i in images]))

    globalmin = defaultdict(list)
    globalmax = defaultdict(list)

    statsInfos = dict()
    for iId in imageIds:
        statsInfo = calcStatsInfo(conn, iId)
        statsInfos[iId] = statsInfo
        if scriptParams["DryRun"]:
            print "Image:%s" % iId
        for c, si in sorted(statsInfo.items()):
            c_min, c_max = si
            globalmin[c].append(c_min)
            globalmax[c].append(c_max)
            if scriptParams["DryRun"]:
                print "  c=%s, min=%s, max=%s" % (c, c_min, c_max)

    if scriptParams["DryRun"]:
        for c in globalmin:
            print "="*30
            print "Channel %s" % c
            c_min = globalmin[c]
            c_max = globalmax[c]
            print "Max window: min=%s, max=%s" % (min(c_min), max(c_max))
            print "Min window: min=%s, max=%s" % (max(c_min), min(c_max))
            print "Avg window: min=%s, max=%s" % (avg(c_min), avg(c_max))
            print "="*30
    else:
        method = scriptParams["Method"]
        for iId in imageIds:
            img = conn.getObject("Image", iId)
            for c, ch in enumerate(img.getChannels(noRE=True)):
                si = ch.getStatsInfo()
                if si is None:
                    si = StatsInfoI()
                    action = "creating"
                else:
                    si = si._obj
                    action = "updating"

                if method == "no":
                    si.globalMin = rdouble(statsInfos[iId][c][0])
                    si.globalMax = rdouble(statsInfos[iId][c][1])
                elif method == "outer":
                    si.globalMin = rdouble(min(globalmin[c]))
                    si.globalMax = rdouble(max(globalmax[c]))
                elif method == "inner":
                    si.globalMin = rdouble(max(globalmin[c]))
                    si.globalMax = rdouble(min(globalmax[c]))
                elif method == "average":
                    si.globalMin = rdouble(avg(globalmin[c]))
                    si.globalMax = rdouble(avg(globalmax[c]))

                print "Image:%s(c=%s) - %s StatsInfo(%s, %s)" % (
                    iId, c, action, si.globalMin.val, si.globalMax.val)
                ch._obj.statsInfo = si
                ch.save()

    count = sum(map(len, statsInfos.values()))
    message += "%s stats info object(s) processed" % count
    return message


def runAsScript():
    dataTypes = [rstring('Image')]
    client = scripts.client(
        'MinMax.py',
        """Create or reset StatsInfo objects for all channels

See http://help.openmicroscopy.org/utility-scripts.html""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Pick Images by 'Image' ID or by the ID of their "
            "Dataset'", values=dataTypes, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs to "
            "process.").ofType(rlong(0)),

        scripts.Bool(
            "DryRun", optional=True, grouping="3",
            description="Whether to print or set values",
            default=True),

        scripts.String(
            "Method", optional=True, grouping="4",
            description="Whether and if so how to combine values",
            default="no",
            values=("no", "outer", "inner", "average")),

        version="5.1.3",
        authors=["Josh Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        scriptParams = client.getInputs(unwrap=True)
        conn = BlitzGateway(client_obj=client)
        message = processImages(conn, scriptParams)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()

if __name__ == "__main__":
    runAsScript()
