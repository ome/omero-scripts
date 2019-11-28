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

Script produces a figure of a movie, showing panels of different frames.
Saves the figure as a jpg or png attached to the first image in the figure.

@author  William Moore &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@author  Jean-Marie Burel &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:j.burel@dundee.ac.uk">j.burel@dundee.ac.uk</a>
@author Donald MacDonald &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:donald@lifesci.dundee.ac.uk">donald@lifesci.dundee.ac.uk</a>
@since 3.0

"""

import omero.scripts as scripts
import omero.util.image_utils as image_utils
import omero.util.figureUtil as figUtil
import omero.util.script_utils as script_utils
from omero.gateway import BlitzGateway
import omero
from omero.rtypes import rint, rlong, rstring, robject, wrap
import os
import io
from omero.constants.namespaces import NSCREATED
from omero.constants.projection import ProjectionType
from datetime import date
import math

try:
    from PIL import Image, ImageDraw  # see ticket:2597
except ImportError:
    import Image
    import ImageDraw  # see ticket:2597

COLOURS = script_utils.COLOURS    # name:(rgba) map
OVERLAY_COLOURS = dict(COLOURS, **script_utils.EXTRA_COLOURS)

log_lines = []    # make a log / legend of the figure


def log(text):
    log_lines.append(text)


def createmovie_figure(conn, pixel_ids, t_indexes, z_start, z_end, width,
                       height, spacer, algorithm, stepping, scalebar,
                       overlay_colour, time_units, image_labels,
                       max_col_count):
    """
    Makes the complete Movie figure: A canvas showing an image per row with
    multiple columns showing frames from each image/movie. Labels obove each
    frame to show the time-stamp of that frame in the specified units and
    labels on the left name each image.

    @param conn             The OMERO session
    @param pixel_ids        A list of the Pixel IDs for the images in the
                            figure
    @param t_indexes        A list of tIndexes to display frames from
    @param z_start          Projection Z-start
    @param z_end            Projection Z-end
    @param width            Maximum width of panels
    @param height           Max height of panels
    @param spacer           Space between panels
    @param algorithm        Projection algorithm e.g. "MAXIMUMINTENSITY"
    @param stepping         Projecttion z-step
    @param scalebar         A number of microns for scale-bar
    @param overlay_colour   Color of the scale bar as tuple (255,255,255)
    @param time_units       A string such as "SECS"
    @param image_labels     A list of lists, corresponding to pixelIds, for
                            labelling each image with one or more strings.
    """

    mode = "RGB"
    white = (255, 255, 255)

    # create a rendering engine
    re = conn.createRenderingEngine()
    query_service = conn.getQueryService()

    row_panels = []
    total_height = 0
    total_width = 0
    max_image_width = 0
    physical_size_x = 0

    for row, pixels_id in enumerate(pixel_ids):
        log("Rendering row %d" % (row))

        pixels = query_service.get("Pixels", pixels_id)
        size_x = pixels.getSizeX().getValue()
        size_y = pixels.getSizeY().getValue()
        size_z = pixels.getSizeZ().getValue()
        size_t = pixels.getSizeT().getValue()

        if pixels.getPhysicalSizeX():
            physical_x = pixels.getPhysicalSizeX().getValue()
            units_x = pixels.getPhysicalSizeX().getSymbol()
        else:
            physical_x = 0
            units_x = ""
        if pixels.getPhysicalSizeY():
            physical_y = pixels.getPhysicalSizeY().getValue()
            units_y = pixels.getPhysicalSizeY().getSymbol()
        else:
            physical_y = 0
            units_y = ""
        log("  Pixel size: x: %s %s  y: %s %s"
            % (str(physical_x), units_x, str(physical_y), units_y))
        if row == 0:    # set values for primary image
            physical_size_x = physical_x
            physical_size_y = physical_y
        else:            # compare primary image with current one
            if physical_size_x != physical_x or physical_size_y != physical_y:
                log(" WARNING: Images have different pixel lengths. Scales"
                    " are not comparable.")

        log("  Image dimensions (pixels): x: %d  y: %d" % (size_x, size_y))
        max_image_width = max(max_image_width, size_x)

        # set up rendering engine with the pixels
        re.lookupPixels(pixels_id)
        if not re.lookupRenderingDef(pixels_id):
            re.resetDefaults()
        if not re.lookupRenderingDef(pixels_id):
            raise "Failed to lookup Rendering Def"
        re.load()

        pro_start = z_start
        pro_end = z_end
        # make sure we're within Z range for projection.
        if pro_end >= size_z:
            pro_end = size_z - 1
            if pro_start > size_z:
                pro_start = 0
            log(" WARNING: Current image has fewer Z-sections than the"
                " primary image.")

        # if we have an invalid z-range (start or end less than 0), show
        # default Z only
        if pro_start < 0 or pro_end < 0:
            pro_start = re.getDefaultZ()
            pro_end = pro_start
            log("  Display Z-section: %d" % (pro_end+1))
        else:
            log("  Projecting z range: %d - %d   (max Z is %d)"
                % (pro_start+1, pro_end+1, size_z))

        # now get each channel in greyscale (or colour)
        # a list of renderedImages (data as Strings) for the split-view row
        rendered_images = []

        for time in t_indexes:
            if time >= size_t:
                log(" WARNING: This image does not have Time frame: %d. "
                    "(max is %d)" % (time+1, size_t))
            else:
                if pro_start != pro_end:
                    rendered_img = re.renderProjectedCompressed(
                        algorithm, time, stepping, pro_start, pro_end)
                else:
                    plane_def = omero.romio.PlaneDef()
                    plane_def.z = pro_start
                    plane_def.t = time
                    rendered_img = re.renderCompressed(plane_def)
                # create images and resize, add to list
                image = Image.open(io.BytesIO(rendered_img))
                resized_image = image_utils.resize_image(image, width, height)
                rendered_images.append(resized_image)

        # make a canvas for the row of splitview images...
        # (will add time labels above each row)
        col_count = min(max_col_count, len(rendered_images))
        row_count = int(math.ceil(len(rendered_images) / col_count))
        font = image_utils.get_font(width // 12)
        font_height = font.getsize("Textq")[1]
        canvas_width = ((width + spacer) * col_count) + spacer
        canvas_height = row_count * (spacer // 2 + font_height +
                                     spacer + height)
        size = (canvas_width, canvas_height)
        # create a canvas of appropriate width, height
        canvas = Image.new(mode, size, white)

        # add text labels
        query_service = conn.getQueryService()
        text_x = spacer
        text_y = spacer // 4
        col_index = 0
        time_labels = figUtil.getTimeLabels(
            query_service, pixels_id, t_indexes, size_t, time_units)
        for t, t_index in enumerate(t_indexes):
            if t_index >= size_t:
                continue
            time = time_labels[t]
            text_w = font.getsize(time)[0]
            inset = (width - text_w) // 2
            textdraw = ImageDraw.Draw(canvas)
            textdraw.text((text_x+inset, text_y), time, font=font,
                          fill=(0, 0, 0))
            text_x += width + spacer
            col_index += 1
            if col_index >= max_col_count:
                col_index = 0
                text_x = spacer
                text_y += (spacer // 2 + font_height + spacer + height)

        # add scale bar to last frame...
        if scalebar:
            scaled_image = rendered_images[-1]
            x_indent = spacer
            y_indent = x_indent
            # if we've scaled to half size, zoom = 2
            zoom = image_utils.get_zoom_factor(scaled_image.size, width,
                                               height)
            # and the scale bar will be half size
            sbar = float(scalebar) / zoom
            status, log_msg = figUtil.addScalebar(
                sbar, x_indent, y_indent, scaled_image, pixels, overlay_colour)
            log(log_msg)

        px = spacer
        py = spacer + font_height
        col_index = 0
        # paste the images in
        for i, img in enumerate(rendered_images):
            image_utils.paste_image(img, canvas, px, py)
            px = px + width + spacer
            col_index += 1
            if col_index >= max_col_count:
                col_index = 0
                px = spacer
                py += (spacer // 2 + font_height + spacer + height)

        # Add labels to the left of the panel
        canvas = add_left_labels(canvas, image_labels, row, width, spacer)

        # most should be same width anyway
        total_width = max(total_width, canvas.size[0])
        # add together the heights of each row
        total_height = total_height + canvas.size[1]

        row_panels.append(canvas)

    # make a figure to combine all split-view rows
    # each row has 1/2 spacer above and below the panels. Need extra 1/2
    # spacer top and bottom
    figure_size = (total_width, total_height+spacer)
    figure_canvas = Image.new(mode, figure_size, white)

    row_y = spacer // 2
    for row in row_panels:
        image_utils.paste_image(row, figure_canvas, 0, row_y)
        row_y = row_y + row.size[1]

    return figure_canvas


def add_left_labels(panel_canvas, image_labels, row_index, width, spacer):
    """
    Takes a canvas of panels and adds one or more labels to the left,
    with the text aligned vertically.
    NB: We are passed the set of labels for ALL image panels (as well as the
    index of the current image panel) so that we know what is the max label
    count and can give all panels the same margin on the left.

    @param panelCanvas:     PIL image - add labels to the left of this
    @param imageLabels:     A series of label lists, one per image. We only
                            add labels from one list
    @param rowIndex:        The index of the label list we're going to use
                            from imageLabels
    @param width:           Simply used for finding a suitable font size
    @param spacer:          Space between panels
    """

    # add lables to row...
    mode = "RGB"
    white = (255, 255, 255)
    font = image_utils.get_font(width/12)
    text_height = font.getsize("Sampleq")[1]
    text_gap = spacer / 2

    # find max number of labels
    max_count = 0
    for row in image_labels:
        max_count = max(max_count, len(row))
    left_text_height = int((text_height + text_gap) * max_count)
    # make the canvas as wide as the panels height
    left_text_width = panel_canvas.size[1]
    size = (left_text_width, left_text_height)
    text_canvas = Image.new(mode, size, white)
    textdraw = ImageDraw.Draw(text_canvas)

    labels = image_labels[row_index]
    py = left_text_height - text_gap  # start at bottom
    for l, label in enumerate(labels):
        py = py - text_height    # find the top of this row
        w = textdraw.textsize(label, font=font)[0]
        inset = int((left_text_width - w) / 2)
        textdraw.text((inset, py), label, font=font, fill=(0, 0, 0))
        py = py - text_gap    # add space between rows

    # make a canvas big-enough to add text to the images.
    canvas_width = left_text_height + panel_canvas.size[0]
    # TextHeight will be width once rotated
    canvas_height = panel_canvas.size[1]
    size = (canvas_width, canvas_height)
    # create a canvas of appropriate width, height
    canvas = Image.new(mode, size, white)

    # add the panels to the canvas
    paste_x = left_text_height
    paste_y = 0
    image_utils.paste_image(panel_canvas, canvas, paste_x, paste_y)

    # add text to rows
    # want it to be vertical. Rotate and paste the text canvas from above
    if image_labels:
        text_v = text_canvas.rotate(90, expand=True)
        image_utils.paste_image(text_v, canvas, spacer // 2, 0)

    return canvas


def movie_figure(conn, command_args):
    """
    Makes the figure using the parameters in @command_args, attaches the figure
    to the parent Project/Dataset, and returns the file-annotation ID

    @param session      The OMERO session
    @param command_args Map of parameters for the script
    @ returns           Returns the id of the originalFileLink child. (ID
                        object, not value)
    """

    log("Movie figure created by OMERO on %s" % date.today())
    log("")

    time_labels = {"SECS_MILLIS": "seconds",
                   "SECS": "seconds",
                   "MINS": "minutes",
                   "HOURS": "hours",
                   "MINS_SECS": "mins:secs",
                   "HOURS_MINS": "hours:mins"}
    time_units = "SECS"
    if "Time_Units" in command_args:
        time_units = command_args["Time_Units"]
        # convert from UI name to time_labels key
        time_units = time_units.replace(" ", "_")
    if time_units not in time_labels.keys():
        time_units = "SECS"
    log("Time units are in %s" % time_labels[time_units])

    pixel_ids = []
    image_ids = []
    image_labels = []
    message = ""  # message to be returned to the client

    # function for getting image labels.
    def get_image_names(full_name, tags_list, pd_list):
        name = full_name.split("/")[-1]
        return [name]

    # default function for getting labels is getName (or use datasets / tags)
    if "Image_Labels" in command_args:
        if command_args["Image_Labels"] == "Datasets":
            def get_datasets(name, tags_list, pd_list):
                return [dataset for project, dataset in pd_list]
            get_labels = get_datasets
        elif command_args["Image_Labels"] == "Tags":
            def get_tags(name, tags_list, pd_list):
                return tags_list
            get_labels = get_tags
        else:
            get_labels = get_image_names
    else:
        get_labels = get_image_names

    # Get the images
    images, log_message = script_utils.get_objects(conn, command_args)
    message += log_message
    if not images:
        return None, message

    # Attach figure to the first image
    omero_image = images[0]

    # process the list of images
    log("Image details:")
    for image in images:
        image_ids.append(image.getId())
        pixel_ids.append(image.getPrimaryPixels().getId())

    # a map of imageId : list of (project, dataset) names.
    pd_map = figUtil.getDatasetsProjectsFromImages(
        conn.getQueryService(), image_ids)
    tag_map = figUtil.getTagsFromImages(conn.getMetadataService(), image_ids)
    # Build a legend entry for each image
    for image in images:
        name = image.getName()
        iid = image.getId()
        image_date = image.getAcquisitionDate()
        tags_list = tag_map[iid]
        pd_list = pd_map[iid]

        tags = ", ".join(tags_list)
        pd_string = ", ".join(["%s/%s" % pd for pd in pd_list])
        log(" Image: %s  ID: %d" % (name, iid))
        if image_date:
            log("  Date: %s" % image_date)
        else:
            log("  Date: not set")
        log("  Tags: %s" % tags)
        log("  Project/Datasets: %s" % pd_string)

        image_labels.append(get_labels(name, tags_list, pd_list))

    # use the first image to define dimensions, channel colours etc.
    size_x = omero_image.getSizeX()
    size_y = omero_image.getSizeY()
    size_z = omero_image.getSizeZ()
    size_t = omero_image.getSizeT()

    t_indexes = []
    if "T_Indexes" in command_args:
        for t in command_args["T_Indexes"]:
            t_indexes.append(t)
    if len(t_indexes) == 0:      # if no t-indexes given, use all t-indices
        t_indexes = range(size_t)

    z_start = -1
    z_end = -1
    if "Z_Start" in command_args:
        z_start = command_args["Z_Start"]
    if "Z_End" in command_args:
        z_end = command_args["Z_End"]

    width = size_x
    if "Width" in command_args:
        width = command_args["Width"]

    height = size_y
    if "Height" in command_args:
        height = command_args["Height"]

    spacer = (width // 25) + 2

    algorithm = ProjectionType.MAXIMUMINTENSITY
    if "Algorithm" in command_args:
        a = command_args["Algorithm"]
        if (a == "Mean Intensity"):
            algorithm = ProjectionType.MEANINTENSITY

    stepping = 1
    if "Stepping" in command_args:
        s = command_args["Stepping"]
        if (0 < s < size_z):
            stepping = s

    scalebar = None
    if "Scalebar" in command_args:
        sb = command_args["Scalebar"]
        try:
            scalebar = int(sb)
            if scalebar <= 0:
                scalebar = None
            else:
                log("Scalebar is %d microns" % scalebar)
        except ValueError:
            log("Invalid value for scalebar: %s" % str(sb))
            scalebar = None

    overlay_colour = (255, 255, 255)
    if "Scalebar_Colour" in command_args:
        r, g, b, a = OVERLAY_COLOURS[command_args["Scalebar_Colour"]]
        overlay_colour = (r, g, b)

    max_col_count = 10
    if "Max_Columns" in command_args:
        max_col_count = command_args["Max_Columns"]

    figure = createmovie_figure(
        conn, pixel_ids, t_indexes, z_start, z_end, width, height, spacer,
        algorithm, stepping, scalebar, overlay_colour, time_units,
        image_labels, max_col_count)

    log("")
    fig_legend = "\n".join(log_lines)

    # print(figLegend)    # bug fixing only
    format = command_args["Format"]

    figure_name = "movie_figure"
    if "Figure_Name" in command_args:
        figure_name = str(command_args["Figure_Name"])
        figure_name = os.path.basename(figure_name)
    output = "localfile"
    if format == 'PNG':
        output = output + ".png"
        figure_name = figure_name + ".png"
        figure.save(output, "PNG")
        mimetype = "image/png"
    elif format == 'TIFF':
        output = output + ".tiff"
        figure_name = figure_name + ".tiff"
        figure.save(output, "TIFF")
        mimetype = "image/tiff"
    else:
        output = output + ".jpg"
        figure_name = figure_name + ".jpg"
        figure.save(output)
        mimetype = "image/jpeg"

    namespace = NSCREATED + "/omero/figure_scripts/Movie_Figure"
    file_annotation, fa_message = script_utils.create_link_file_annotation(
        conn, output, omero_image, output="Movie figure", mimetype=mimetype,
        namespace=namespace, description=fig_legend,
        orig_file_path_and_name=figure_name)
    message += fa_message

    return file_annotation, message


def run_script():
    """
    The main entry point of the script. Gets the parameters from the scripting
    service, makes the figure and returns the output to the client.
    """

    data_types = [rstring('Image')]
    labels = [rstring('Image Name'), rstring('Datasets'), rstring('Tags')]
    algorithms = [rstring('Maximum Intensity'), rstring('Mean Intensity')]
    tunits = [rstring("SECS"), rstring("MINS"), rstring("HOURS"),
              rstring("MINS SECS"), rstring("HOURS MINS")]
    formats = [rstring('JPEG'), rstring('PNG'), rstring('TIFF')]
    ckeys = list(COLOURS.keys())
    ckeys.sort()
    o_colours = wrap(list(OVERLAY_COLOURS.keys()))

    client = scripts.client(
        'Movie_Figure.py',
        """Export a figure of a movie, showing a row of frames for each \
chosen image.
NB: OMERO.insight client provides a nicer UI for this script under \
'Publishing Options'
See http://help.openmicroscopy.org/publish.html#movies""",

        # provide 'Data_Type' and 'IDs' parameters so that Insight
        # auto-populates with currently selected images.

        scripts.String(
            "Data_Type", optional=False, grouping="01",
            description="The data you want to work with.", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="02",
            description="List of Image IDs").ofType(rlong(0)),

        scripts.List(
            "T_Indexes", grouping="03",
            description="The time frames to display in the figure for each"
            " image").ofType(rint(0)),

        scripts.String(
            "Image_Labels", grouping="04",
            description="Label images with Image name (default) or datasets"
            " or tags", values=labels),

        scripts.Int(
            "Width", grouping="06",
            description="The max width of each image panel. Default is first"
            " image width", min=1),

        scripts.Int(
            "Height", grouping="07",
            description="The max height of each image panel. Default is first"
            " image height", min=1),

        scripts.Bool("Z_Projection", grouping="08", default=True),

        scripts.Int(
            "Z_Start", grouping="08.1",
            description="Projection range (if not specified, use defaultZ"
            " only - no projection)", min=0),

        scripts.Int(
            "Z_End", grouping="08.2",
            description="Projection range (if not specified or, use defaultZ"
            " only - no projection)", min=0),

        scripts.String(
            "Algorithm", grouping="08.3",
            description="Algorithm for projection.", values=algorithms),

        scripts.Int(
            "Stepping", grouping="08.4",
            description="The Z increment for projection.", default=1, min=1),

        scripts.Bool("Show_Scalebar", grouping="10", default=True),

        scripts.Int(
            "Scalebar", grouping="10.1",
            description="Scale bar size in microns. Only shown if image has"
            " pixel-size info.", min=1),

        scripts.String(
            "Scalebar_Colour", grouping="10.2",
            description="The color of the scale bar.",
            default='White', values=o_colours),

        scripts.String(
            "Format", grouping="11",
            description="Format to save image.", values=formats,
            default='JPEG'),

        scripts.String(
            "Figure_Name", grouping="12",
            description="File name of the figure to save."),

        scripts.String(
            "Time_Units", grouping="13",
            description="The units to use for time display", values=tunits),

        scripts.Int(
            "Max_Columns", grouping="04.1", default=10,
            description="The maximum number of columns in the figure, for"
            " movie frames.", min=1),

        version="4.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        command_args = client.getInputs(unwrap=True)

        # Makes the figure and attaches it to Image. Returns the id of the
        # originalFileLink child. (ID object, not value)
        file_annotation, message = movie_figure(conn, command_args)

        # Return message and file annotation (if applicable) to the client
        client.setOutput("Message", rstring(message))
        if file_annotation:
            client.setOutput("File_Annotation", robject(file_annotation._obj))
    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
