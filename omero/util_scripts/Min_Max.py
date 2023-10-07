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
from omero.util.text import TableBuilder
from omero.util.tiles import TileLoop, TileLoopIteration

import omero.scripts as scripts
import omero.util.script_utils as script_utils

from collections import defaultdict
from random import shuffle

from numpy import amin, amax, iinfo
from numpy import average as avg


def calcStatsInfo(conn, imageId, choice, debug=False):
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

    only_default = (choice == "default")

    class Iteration(TileLoopIteration):

        def run(self, data, z, c, t, x, y,
                tileWidth, tileHeight, tileCount):

            if only_default:
                if t != 0 or z != int(sizeZ/2):
                    return
            zctMap[c].append(
                (z, c, t, (x, y, tileWidth, tileHeight)))

    Loop().forEachTile(
        sizeX, sizeY,
        sizeZ, sizeC, sizeT,
        tileW, tileH, Iteration())

    if choice == "random":
        for c in zctMap:
            copy = list(zctMap[c])
            if len(copy) >= 100:
                copy = copy[0:100]
            shuffle(copy)
            zctMap[c] = copy

    def channelGen():
        byte_count = 0
        tile_count = 0
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
                byte_count += tile.nbytes
                tile_count += 1
            rv[c] = (tile_min, tile_max)
        yield rv, byte_count, tile_count

    statsInfos = dict()
    for x, byte_count, tile_count in channelGen():
        statsInfos.update(x)

    if debug:
        print "Loaded %s tile(s) (%s bytes)" % (tile_count, byte_count)
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

    choice = scriptParams["Choice"]
    debug = bool(scriptParams.get("Debug", False))
    globalmin = defaultdict(list)
    globalmax = defaultdict(list)

    tb = TableBuilder("Context", "Channel", "Min", "Max")
    statsInfos = dict()
    for iId in imageIds:
        statsInfo = calcStatsInfo(conn, iId, choice, debug)
        statsInfos[iId] = statsInfo
        for c, si in sorted(statsInfo.items()):
            c_min, c_max = si
            globalmin[c].append(c_min)
            globalmax[c].append(c_max)
            tb.row("Image:%s" % iId, c, c_min, c_max)

    tb.row("", "", "", "")
    for c in globalmin:
        c_min = globalmin[c]
        c_max = globalmax[c]
        tb.row("Total: outer  ", c, min(c_min), max(c_max))
        tb.row("Total: inner  ", c, max(c_min), min(c_max))
        tb.row("Total: average", c, int(avg(c_min)), int(avg(c_max)))

    if scriptParams["DryRun"]:
        print str(tb.build())
    else:
        combine = scriptParams["Combine"]
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

                if combine == "no":
                    si.globalMin = rdouble(statsInfos[iId][c][0])
                    si.globalMax = rdouble(statsInfos[iId][c][1])
                elif combine == "outer":
                    si.globalMin = rdouble(min(globalmin[c]))
                    si.globalMax = rdouble(max(globalmax[c]))
                elif combine == "inner":
                    si.globalMin = rdouble(max(globalmin[c]))
                    si.globalMax = rdouble(min(globalmax[c]))
                elif combine == "average":
                    si.globalMin = rdouble(avg(globalmin[c]))
                    si.globalMax = rdouble(avg(globalmax[c]))
                else:
                    raise Exception("unknown combine: %s" % combine)

                if debug:
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
            "Choice", optional=True, grouping="4",
            description="How to choose which planes will be chosen",
            default="default",
            values=("default", "random", "all")),

        scripts.String(
            "Combine", optional=True, grouping="5",
            description="Whether and if so how to combine values",
            default="no",
            values=("no", "outer", "inner", "average")),

        scripts.Bool(
            "Debug", optional=True, grouping="6",
            description="Whether to print debug statements",
            default=False),

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
