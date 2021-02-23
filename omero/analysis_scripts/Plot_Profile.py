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

This script processes Images which have Line or PolyLine ROIs,
saving the intensity of chosen channels to Excel (csv) files.

@author Will Moore
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@since 3.0
"""

from omero.gateway import BlitzGateway
import omero
from omero.rtypes import rstring, rlong, robject, unwrap
import omero.scripts as scripts
import omero.util.script_utils as script_utils
import omero.util.roi_handling_utils as roi_utils
from numpy import hstack, average
import logging

logger = logging.getLogger('plot_profile')


def process_polylines(conn, script_params, image, polylines, line_width, fout):
    """
    Output data from one or more polylines on an image. Attach csv to image.

    @param polylines list of theT:T, theZ:Z, points: list of (x,y)}
    """
    pixels = image.getPrimaryPixels()
    the_cs = script_params['Channels']

    for pl in polylines:
        the_t = pl['theT']
        the_z = pl['theZ']
        roi_id = pl['id']
        points = pl['points']
        for the_c in the_cs:
            ldata = []
            for l in range(len(points)-1):
                x1, y1 = points[l]
                x2, y2 = points[l+1]
                if round(x1 - x2) == 0 and round(y1 - y2) == 0:
                    continue
                ld = roi_utils.get_line_data(
                    pixels, x1, y1, x2, y2, line_width,
                    the_z, the_c, the_t)
                ldata.append(ld)
            line_data = hstack(ldata)

            if script_params['Sum_or_Average'] == 'Sum':
                output_data = line_data.sum(axis=0)
            else:
                output_data = average(line_data, axis=0)

            line_header = script_params['Sum_or_Average'] == \
                'Average, with raw data' and 'Average,' or ""

            # Image_ID, ROI_ID, Z, T, C, Line data
            fout.write('%s,%s,%s,%s,%s,%s' % (image.getId(), roi_id, the_z+1,
                       the_t+1, the_c+1, line_header))
            fout.write(','.join([str(d) for d in output_data]))
            fout.write('\n')

            # Optionally output raw data for each row of raw line data
            if script_params['Sum_or_Average'] == 'Average, with raw data':
                for r in range(line_width):
                    fout.write('%s,%s,%s,%s,%s,%s,' % (image.getId(), roi_id,
                               the_z+1, the_t+1, the_c+1, r))
                    fout.write(','.join([str(d) for d in line_data[r]]))
                    fout.write('\n')


def process_lines(conn, script_params, image, lines, line_width, fout):
    """
    Creates a new kymograph Image from one or more lines.
    If one line, use this for every time point.
    If multiple lines, use the first one for length and all the remaining ones
    for x1,y1 and direction, making all subsequent lines the same length as
    the first.
    """

    pixels = image.getPrimaryPixels()
    the_cs = script_params['Channels']

    for l in lines:
        the_t = l['theT']
        the_z = l['theZ']
        roi_id = l['id']
        if round(l['x1'] - l['x2']) == 0 and round(l['y1'] - l['y2']) == 0:
            continue
        for the_c in the_cs:
            line_data = []
            line_data = roi_utils.get_line_data(pixels, l['x1'], l['y1'],
                                                l['x2'], l['y2'], line_width,
                                                the_z, the_c, the_t)

            if script_params['Sum_or_Average'] == 'Sum':
                output_data = line_data.sum(axis=0)
            else:
                output_data = average(line_data, axis=0)

            line_header = script_params['Sum_or_Average'] == \
                'Average, with raw data' and 'Average,' or ""

            # Image_ID, ROI_ID, Z, T, C, Line data
            fout.write('%s,%s,%s,%s,%s,%s' % (image.getId(), roi_id, the_z+1,
                       the_t+1, the_c+1, line_header))
            fout.write(','.join([str(d) for d in output_data]))
            fout.write('\n')

            # Optionally output raw data for each row of raw line data
            if script_params['Sum_or_Average'] == 'Average, with raw data':
                for r in range(line_width):
                    fout.write('%s,%s,%s,%s,%s,%s,' % (image.getId(), roi_id,
                               the_z+1, the_t+1, the_c+1, r))
                    fout.write(','.join([str(d) for d in line_data[r]]))
                    fout.write('\n')


def process_images(conn, script_params):

    line_width = script_params['Line_Width']
    file_anns = []
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

        c_names = []
        colors = []
        for ch in image.getChannels():
            c_names.append(ch.getLabel())
            colors.append(ch.getColor().getRGB())

        size_c = image.getSizeC()

        if 'Channels' in script_params:
            script_params['Channels'] = [i-1 for i in
                                         script_params['Channels']]
        else:
            script_params['Channels'] = range(size_c)

        roi_service = conn.getRoiService()
        result = roi_service.findByImage(image.getId(), None)

        lines = []
        polylines = []

        for roi in result.rois:
            roi_id = roi.getId().getValue()
            for s in roi.copyShapes():
                the_t = unwrap(s.getTheT())
                the_z = unwrap(s.getTheZ())
                z = 0
                t = 0
                if the_t is not None:
                    t = the_t
                if the_z is not None:
                    z = the_z
                # TODO: Add some filter of shapes e.g. text? / 'lines' only
                # etc.
                if type(s) == omero.model.LineI:
                    x1 = s.getX1().getValue()
                    x2 = s.getX2().getValue()
                    y1 = s.getY1().getValue()
                    y2 = s.getY2().getValue()
                    lines.append({'id': roi_id, 'theT': t, 'theZ': z,
                                  'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})

                elif type(s) == omero.model.PolylineI:
                    v = s.getPoints().getValue()
                    points = roi_utils.points_string_to_xy_list(v)
                    polylines.append({'id': roi_id, 'theT': t, 'theZ': z,
                                      'points': points})

        if len(lines) == 0 and len(polylines) == 0:
            continue

        # prepare column headers, including line-id if we are going to output
        # raw data.
        line_id = script_params['Sum_or_Average'] == 'Average, with raw data' \
            and 'Line, ' or ""
        col_header = 'Image_ID, ROI_ID, Z, T, C, %sLine data %s of Line" \
            " Width %s\n' % (line_id, script_params['Sum_or_Average'],
                             script_params['Line_Width'])

        # prepare a csv file to write our data to...
        file_name = "Plot_Profile_%s.csv" % image.getId()
        with open(file_name, 'w') as f:
            f.write(col_header)
            if len(lines) > 0:
                process_lines(conn, script_params, image, lines, line_width, f)
            if len(polylines) > 0:
                process_polylines(
                    conn, script_params, image, polylines, line_width, f)

        file_ann, fa_message = script_utils.create_link_file_annotation(
            conn, file_name, image, output="Line Plot csv (Excel) file",
            mimetype="text/csv", description=None)
        if file_ann:
            file_anns.append(file_ann)

    if not file_anns:
        fa_message = "No Analysis files created. See 'Info' or 'Error' for"\
            " more details"
    elif len(file_anns) > 1:
        fa_message = "Created %s csv (Excel) files" % len(file_anns)
    message += fa_message

    return file_anns, message


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """
    data_types = [rstring('Image')]
    sum_avg_options = [rstring('Average'),
                       rstring('Sum'),
                       rstring('Average, with raw data')]

    client = scripts.client(
        'Plot_Profile.py',
        """This script processes Images, which have Line or PolyLine ROIs \
and outputs the data as CSV files, for plotting in e.g. Excel.""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images (only Image supported).",
            values=data_types, default="Image"),

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
            default='Average', values=sum_avg_options),

        scripts.List(
            "Channels", grouping="4",
            description="Optional list of Channels to process e.g. 1, 2. Use"
            " ALL Channels by default.").ofType(omero.rtypes.rint(0)),

        version="4.3.3",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        script_params = client.getInputs(unwrap=True)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        file_anns, message = process_images(conn, script_params)

        if file_anns:
            if len(file_anns) == 1:
                client.setOutput("Line_Data", robject(file_anns[0]._obj))
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
