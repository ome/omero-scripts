"""
 scripts/analysis_utils.py 

-----------------------------------------------------------------------------
  Copyright (C) 2012 University of Dundee. All rights reserved.


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

Utility functions for analysis scripts

@author Will Moore
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 4.3
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.3
"""

import math
try:
    from PIL import Image
except ImportError:
    import Image


def numpyToImage(plane):
    """
    Converts the numpy plane to a PIL Image, converting data type if necessary.
    """

    from numpy import int32, zeros

    if plane.dtype.name not in ('uint8', 'int8'):
        convArray = zeros(plane.shape, dtype=int32)     # int32 is handled by PIL (not uint32 etc). TODO: support floats
        convArray += plane
        return Image.fromarray(convArray)
    return Image.fromarray(plane)


def getLineData(pixels, x1,y1,x2,y2, lineW=2, theZ=0, theC=0, theT=0):
    """
    Grabs pixel data covering the specified line, and rotates it horizontally so that x1,y1 is to the left,
    Returning a numpy 2d array. Used by Kymograph.py script.
    Uses PIL to handle rotating and interpolating the data. Converts to numpy to PIL and back (may change dtype.)
    
    @param pixels:          PixelsWrapper object
    @param x1, y1, x2, y2:  Coordinates of line
    @param lineW:           Width of the line we want
    @param theZ:            Z index within pixels
    @param theC:            Channel index
    @param theT:            Time index
    """
    
    from numpy import asarray

    sizeX = pixels.getSizeX()
    sizeY = pixels.getSizeY()

    centreX = (x1+x2)/2
    centreY = (y1+y2)/2
    lineX = x2-x1
    lineY = y2-y1

    rads = math.atan(float(lineX)/lineY)

    # How much extra Height do we need, top and bottom?
    extraH = abs(math.sin(rads) * lineW)
    bottom = int(max(y1,y2) + extraH/2)
    top = int(min(y1,y2) - extraH/2)

    # How much extra width do we need, left and right?
    extraW = abs(math.cos(rads) * lineW)
    left = int(min(x1,x2) - extraW)
    right = int(max(x1,x2) + extraW)

    # What's the larger area we need? - Are we outside the image?
    pad_left, pad_right, pad_top, pad_bottom = 0,0,0,0
    if left < 0:
        pad_left = abs(left)
        left = 0
    x = left
    if top < 0:
        pad_top = abs(top)
        top = 0
    y = top
    if right > sizeX:
        pad_right = right-sizeX
        right = sizeX
    w = int(right - left)
    if bottom > sizeY:
        pad_bottom = bottom-sizeY
        bottom = sizeY
    h = int(bottom - top)
    tile = (x, y, w, h)
    
    # get the Tile
    plane = pixels.getTile(theZ, theC, theT, tile)
    
    # pad if we wanted a bigger region
    if pad_left > 0:
        data_h, data_w = plane.shape
        pad_data = zeros( (data_h, pad_left), dtype=plane.dtype)
        plane = hstack( (pad_data, plane) )
    if pad_right > 0:
        data_h, data_w = plane.shape
        pad_data = zeros( (data_h, pad_right), dtype=plane.dtype)
        plane = hstack( (plane, pad_data) )
    if pad_top > 0:
        data_h, data_w = plane.shape
        pad_data = zeros( (pad_top, data_w), dtype=plane.dtype)
        plane = vstack( (pad_data, plane) )
    if pad_bottom > 0:
        data_h, data_w = plane.shape
        pad_data = zeros( (pad_bottom, data_w), dtype=plane.dtype)
        plane = vstack( (plane, pad_data) )
    
        
    pil = numpyToImage(plane)
    #pil.show()

    # Now need to rotate so that x1,y1 is horizontally to the left of x2,y2
    toRotate = 90 - math.degrees(rads)

    if x1 > x2:
        toRotate += 180
    rotated = pil.rotate(toRotate, expand=True)  # filter=Image.BICUBIC see http://www.ncbi.nlm.nih.gov/pmc/articles/PMC2172449/
    #rotated.show()

    # finally we need to crop to the length of the line
    length = int(math.sqrt(math.pow(lineX, 2) + math.pow(lineY, 2)))
    rotW, rotH = rotated.size
    cropX = (rotW - length)/2
    cropX2 = cropX + length
    cropY = (rotH - lineW)/2
    cropY2 = cropY + lineW
    cropped = rotated.crop( (cropX, cropY, cropX2, cropY2))
    #cropped.show()
    return asarray(cropped)