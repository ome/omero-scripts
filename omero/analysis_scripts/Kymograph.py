#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

-----------------------------------------------------------------------------
  Copyright (C) 2006-2017 University of Dundee. All rights reserved.


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

This script processes Images, which have Line or PolyLine ROIs to create
kymographs.
Kymographs are created in the form of new OMERO Images, single Z and T, same
sizeC as input.


@author Will Moore
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 4.3.3
@since 3.0
"""

from omero.gateway import BlitzGateway
import omero
import omero.util.script_utils as script_utils
import omero.util.roi_handling_utils as roi_utils
from omero.rtypes import rlong, rstring, robject, unwrap
import omero.scripts as scripts
from numpy import zeros, hstack, vstack
import logging

logger = logging.getLogger('kymograph')


def points_string_to_xy_list(string):
    """
    Method for converting the string returned from
    omero.model.ShapeI.getPoints() into list of (x,y) points
    e.g. "points[309,427, 366,503, 190,491]"
    """
    point_lists = string.strip().split("points")
    if len(point_lists) < 2:
        if len(point_lists) == 1 and point_lists[0]:
            xys = point_lists[0].split()
            xy_list = [tuple(map(float, xy.split(','))) for xy in xys]
            return xy_list
        raise ValueError("Unrecognised ROI shape 'points' string: %s" % string)

    first_list = point_lists[1]
    xy_list = []
    for xy in first_list.strip(" []").split(", "):
        x, y = xy.split(",")
        xy_list.append((int(x.strip()), int(y.strip())))
    return xy_list


def polyline_kymograph(conn, script_params, image, polylines, line_width,
                       dataset):
    """
    Creates a new kymograph Image from one or more polylines.

    @param polylines:       map of theT: {theZ:theZ, points: list of (x,y)}
    """
    pixels = image.getPrimaryPixels()
    size_c = image.getSizeC()
    size_t = image.getSizeT()

    use_all_times = "Use_All_Timepoints" in script_params and \
        script_params['Use_All_Timepoints'] is True
    if len(polylines) == 1:
        use_all_times = True

    # for now, assume we're using ALL timepoints
    # need the first shape
    first_shape = None
    for t in range(size_t):
        if t in polylines:
            first_shape = polylines[t]
            break

    def plane_gen():
        """ Final image is single Z and T. Each plane is rows of T-slices """
        for the_c in range(size_c):
            shape = first_shape
            t_rows = []
            for the_t in range(size_t):
                # update shape if specified for this timepoint
                if the_t in polylines:
                    shape = polylines[the_t]
                elif not use_all_times:
                    continue
                line_data = []
                points = shape['points']
                the_z = shape['theZ']
                for l in range(len(points)-1):
                    x1, y1 = points[l]
                    x2, y2 = points[l+1]
                    ld = roi_utils.get_line_data(pixels, x1, y1, x2, y2,
                                                 line_width, the_z, the_c,
                                                 the_t)
                    line_data.append(ld)
                row_data = hstack(line_data)
                t_rows.append(row_data)

            # have to handle any mismatch in line lengths by padding shorter
            # rows
            longest = max([row_array.shape[1] for row_array in t_rows])
            for t in range(len(t_rows)):
                t_row = t_rows[t]
                row_height, row_length = t_row.shape
                if row_length < longest:
                    padding = longest - row_length
                    pad_data = zeros((row_height, padding), dtype=t_row.dtype)
                    t_rows[t] = hstack([t_row, pad_data])
            c_data = vstack(t_rows)
            yield c_data

    name = "%s_kymograph" % image.getName()
    desc = "Kymograph generated from Image ID: %s, polyline: %s" \
        % (image.getId(), first_shape['points'])
    desc += "\nwith each timepoint being %s vertical pixels" % line_width
    return conn.createImageFromNumpySeq(
        plane_gen(), name, 1, size_c, 1, description=desc,
        dataset=dataset)


def lines_kymograph(conn, script_params, image, lines, line_width, dataset):
    """
    Creates a new kymograph Image from one or more lines.
    If one line, use this for every time point.
    If multiple lines, use the first one for length and all the remaining ones
    for x1,y1 and direction, making all subsequent lines the same length as
    the first.
    """

    pixels = image.getPrimaryPixels()
    size_c = image.getSizeC()
    size_t = image.getSizeT()

    use_all_times = "Use_All_Timepoints" in script_params and \
        script_params['Use_All_Timepoints'] is True
    if len(lines) == 1:
        use_all_times = True

    # need the first shape - Going to make all lines this length
    first_line = None
    for t in range(size_t):
        if t in lines:
            first_line = lines[t]
            break

    def plane_gen():
        """ Final image is single Z and T. Each plane is rows of T-slices """
        for the_c in range(size_c):
            shape = first_line
            r_length = None           # set this for first line
            t_rows = []
            for the_t in range(size_t):
                if the_t in lines:
                    shape = lines[the_t]
                elif not use_all_times:
                    continue
                the_z = shape['theZ']
                x1, y1, x2, y2 = shape['x1'], shape['y1'], shape['x2'], \
                    shape['y2']
                row_data = roi_utils.get_line_data(
                    pixels, x1, y1, x2, y2, line_width,
                    the_z, the_c, the_t)
                # if the row is too long, crop - if it's too short, pad
                row_height, row_length = row_data.shape
                if r_length is None:
                    r_length = row_length
                if row_length < r_length:
                    padding = r_length - row_length
                    pad_data = zeros((row_height, padding),
                                     dtype=row_data.dtype)
                    row_data = hstack([row_data, pad_data])
                elif row_length > r_length:
                    row_data = row_data[:, 0:r_length]
                t_rows.append(row_data)
            yield vstack(t_rows)

    name = "%s_kymograph" % image.getName()
    desc = "Kymograph generated from Image ID: %s, line: %s" \
        % (image.getId(), first_line)
    desc += "\nwith each timepoint being %s vertical pixels" % line_width
    return conn.createImageFromNumpySeq(
        plane_gen(), name, 1, size_c, 1, description=desc,
        dataset=dataset)


def process_images(conn, script_params):

    line_width = script_params['Line_Width']
    new_kymographs = []
    message = ""

    # Get the images
    images, log_message = script_utils.get_objects(conn, script_params)
    message += log_message
    if not images:
        return None, message

    # Check for line and polyline ROIs and filter images list
    images = [image for image in images if
              image.getROICount(["Polyline", "Line"]) > 0]
    if not images:
        message += "No ROI containing line or polyline was found."
        return None, message

    for image in images:
        if image.getSizeT() == 1:
            continue
        new_images = []      # kymographs derived from the current image.
        c_names = []
        colors = []
        for ch in image.getChannels():
            c_names.append(ch.getLabel())
            colors.append(ch.getColor().getRGB())

        size_t = image.getSizeT()
        pixels = image.getPrimaryPixels()

        dataset = image.getParent()
        if dataset is not None and not dataset.canLink():
            dataset = None

        roi_service = conn.getRoiService()
        result = roi_service.findByImage(image.getId(), None)

        # kymograph strategy - Using Line and Polyline ROIs:
        # NB: Use ALL time points unless >1 shape AND 'use_all_timepoints' =
        # False
        # If > 1 shape per time-point (per ROI), pick one!
        # 1 - Single line. Use this shape for all time points
        # 2 - Many lines. Use the first one to fix length. Subsequent lines to
        # update start and direction
        # 3 - Single polyline. Use this shape for all time points
        # 4 - Many polylines. Use the first one to fix length.
        for roi in result.rois:
            lines = {}          # map of theT: line
            polylines = {}      # map of theT: polyline
            for s in roi.copyShapes():
                if s is None:
                    continue
                the_t = unwrap(s.getTheT())
                the_z = unwrap(s.getTheZ())
                z = 0
                t = 0
                if the_t is not None:
                    t = the_t
                if the_z is not None:
                    z = the_z
                # TODO: Add some filter of shapes. E.g. text? / 'lines' only
                # etc.
                if type(s) == omero.model.LineI:
                    x1 = s.getX1().getValue()
                    x2 = s.getX2().getValue()
                    y1 = s.getY1().getValue()
                    y2 = s.getY2().getValue()
                    lines[t] = {'theZ': z, 'x1': x1, 'y1': y1, 'x2': x2,
                                'y2': y2}

                elif type(s) == omero.model.PolylineI:
                    v = s.getPoints().getValue()
                    points = points_string_to_xy_list(v)
                    polylines[t] = {'theZ': z, 'points': points}

            if len(lines) > 0:
                new_img = lines_kymograph(
                    conn, script_params, image, lines, line_width, dataset)
                new_images.append(new_img)
                lines = []
            elif len(polylines) > 0:
                new_img = polyline_kymograph(
                    conn, script_params, image, polylines, line_width, dataset)
                new_images.append(new_img)

        # look-up the interval for each time-point
        t_interval = None
        infos = list(pixels.copyPlaneInfo(theC=0, theT=size_t-1, theZ=0))
        if len(infos) > 0 and infos[0].getDeltaT() is not None:
            duration = infos[0].getDeltaT(units="SECOND").getValue()
            if size_t == 1:
                t_interval = duration
            else:
                t_interval = duration/(size_t-1)
        elif pixels.timeIncrement is not None:
            t_interval = pixels.timeIncrement
        elif "Time_Increment" in script_params:
            t_interval = script_params["Time_Increment"]

        pixel_size = None
        if pixels.physicalSizeX is not None:
            pixel_size = pixels.physicalSizeX
        elif "Pixel_Size" in script_params:
            pixel_size = script_params['Pixel_Size']

        # Save channel names and colors for each new image
        for img in new_images:
            for i, c in enumerate(img.getChannels()):
                lc = c.getLogicalChannel()
                lc.setName(c_names[i])
                lc.save()
                r, g, b = colors[i]
                # need to reload channels to avoid optimistic lock on update
                c_obj = conn.getQueryService().get("Channel", c.id)
                c_obj.red = omero.rtypes.rint(r)
                c_obj.green = omero.rtypes.rint(g)
                c_obj.blue = omero.rtypes.rint(b)
                c_obj.alpha = omero.rtypes.rint(255)
                conn.getUpdateService().saveObject(c_obj)
            img.resetRDefs()  # reset based on colors above

            # If we know pixel sizes, set them on the new image
            if pixel_size is not None or t_interval is not None:
                px = conn.getQueryService().get("Pixels", img.getPixelsId())
                microm = getattr(omero.model.enums.UnitsLength, "MICROMETER")
                if pixel_size is not None:
                    pixel_size = omero.model.LengthI(pixel_size, microm)
                    px.setPhysicalSizeX(pixel_size)
                if t_interval is not None:
                    t_per_pixel = t_interval / line_width
                    t_per_pixel = omero.model.LengthI(t_per_pixel, microm)
                    px.setPhysicalSizeY(t_per_pixel)
                conn.getUpdateService().saveObject(px)
        new_kymographs.extend(new_images)

    if not new_kymographs:
        message += "No kymograph created. See 'Error' or 'Info' for details."
    else:
        if not dataset:
            link_message = " but could not be attached"
        else:
            link_message = ""

        if len(new_images) == 1:
            message += "New kymograph created%s: %s." \
                % (link_message, new_images[0].getName())
        elif len(new_images) > 1:
            message += "%s new kymographs created%s." \
                % (len(new_images), link_message)

    return new_kymographs, message


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    data_types = [rstring('Image')]

    client = scripts.client(
        'Kymograph.py',
        """This script processes Images, which have Line or PolyLine ROIs to \
create kymographs.
Kymographs are created in the form of new OMERO Images, with single Z and T, \
same sizeC as input.""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images (only Image supported)",
            values=data_types, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Image IDs to process").ofType(rlong(0)),

        scripts.Int(
            "Line_Width", optional=False, grouping="3", default=4,
            description="Width in pixels of each time slice", min=1),

        scripts.Bool(
            "Use_All_Timepoints", grouping="4", default=True,
            description="Use every timepoint in the kymograph. If False, only"
            " use timepoints with ROI-shapes"),

        scripts.Float(
            "Time_Increment", grouping="5",
            description="If source movie has no time info, specify increment"
            " per time point (seconds)"),

        scripts.Float(
            "Pixel_Size", grouping="6",
            description="If source movie has no Pixel size info, specify"
            " pixel size (microns)"),

        version="4.3.3",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        script_params = client.getInputs(unwrap=True)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        new_images, message = process_images(conn, script_params)

        if new_images:
            if len(new_images) == 1:
                client.setOutput("New_Image", robject(new_images[0]._obj))
            elif len(new_images) > 1:
                # return the first one
                client.setOutput("First_Image", robject(new_images[0]._obj))
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
