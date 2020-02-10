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

This script takes a number of images an makes a split view figure, one
image per row, displayed as a split view with merged image.

@author  Jean-Marie Burel &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:j.burel@dundee.ac.uk">j.burel@dundee.ac.uk</a>
@author Donald MacDonald &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:donald@lifesci.dundee.ac.uk">donald@lifesci.dundee.ac.uk</a>
@since 3.0

"""

import omero.scripts as scripts
import omero.util.figureUtil as figUtil
import omero.util.image_utils as image_utils
import omero.util.script_utils as script_utils
import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rint, rlong, rstring, robject, wrap
from omero.constants.namespaces import NSCREATED
from omero.constants.projection import ProjectionType
import os
import io
from datetime import date

try:
    from PIL import Image, ImageDraw  # see ticket:2597
except ImportError:
    import Image
    import ImageDraw  # see ticket:2597

COLOURS = script_utils.COLOURS    # name:(rgba) map
OVERLAY_COLOURS = dict(COLOURS, **script_utils.EXTRA_COLOURS)


# keep track of log strings.
log_strings = []


def log(text):
    """
    Adds the text to a list of logs. Compiled into figure legend at the end.
    """
    log_strings.append(text)


def get_split_view(conn, pixel_ids, z_start, z_end, split_indexes,
                   channel_names, colour_channels, merged_indexes,
                   merged_colours, width=None, height=None, spacer=12,
                   algorithm=None, stepping=1, scalebar=None,
                   overlay_colour=(255, 255, 255)):
    """
    This method makes a figure of a number of images, arranged in rows with
    each row being the split-view of a single image. The channels are arranged
    left to right, with the combined image added on the right.
    The combined image is rendered according to current settings on the
    server, but it's channels will be turned on/off according to
    @merged_indexes.
    No text labels are added to the image at this stage.

    The figure is returned as a PIL 'Image'

    @ conn              session for server access
    @ pixel_ids         a list of the Ids for the pixels we want to display
    @ z_start           the start of Z-range for projection
    @ z_end             the end of Z-range for projection
    @ split_indexes     a list of the channel indexes to display. Same
                        channels for each image/row
    @ channel_names     the Map of index:names to go above the columns for
                        each split channel
    @ colour_channels   the colour to make each column/ channel
    @ merged_indexes    list or set of channels in the merged image
    @ merged_colours    index: colour dictionary of channels in the merged
                        image
    @ width             the size in pixels to show each panel
    @ height            the size in pixels to show each panel
    @ spacer            the gap between images and around the figure. Doubled
                        between rows.
    """

    if algorithm is None:    # omero::constants::projection::ProjectionType
        algorithm = ProjectionType.MAXIMUMINTENSITY
    timepoint = 0
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

    log("Split View Rendering Log...")

    if z_start > -1 and z_end > -1:
        al_string = str(algorithm).replace("INTENSITY",
                                           " Intensity").capitalize()
        log("All images projected using '%s' projection with step size: "
            "%d  start: %d  end: %d"
            % (al_string, stepping, z_start+1, z_end+1))
    else:
        log("Images show last-viewed Z-section")

    for row, pixels_id in enumerate(pixel_ids):
        log("Rendering row %d" % (row+1))

        pixels = query_service.get("Pixels", pixels_id)
        size_x = pixels.getSizeX().getValue()
        size_y = pixels.getSizeY().getValue()
        size_z = pixels.getSizeZ().getValue()
        size_c = pixels.getSizeC().getValue()

        if pixels.getPhysicalSizeX():
            physical_x = pixels.getPhysicalSizeX().getValue()
        else:
            physical_x = 0
        if pixels.getPhysicalSizeY():
            physical_y = pixels.getPhysicalSizeY().getValue()
        else:
            physical_y = 0
        log("  Pixel size (um): x: %.3f  y: %.3f" % (physical_x, physical_y))
        if row == 0:    # set values for primary image
            physical_size_x = physical_x
            physical_size_y = physical_y
        else:  # compare primary image with current one
            if physical_size_x != physical_x or physical_size_y != physical_y:
                log(" WARNING: Images have different pixel lengths."
                    " Scales are not comparable.")

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

        # turn on channels in merged_indexes
        for i in range(size_c):
            re.setActive(i, False)      # Turn all off first
        log("Turning on merged_indexes: %s ..." % merged_indexes)
        for i in merged_indexes:
            if i >= size_c:
                channel_mismatch = True
            else:
                re.setActive(i, True)
                if i in merged_colours:
                    re.setRGBA(i, *merged_colours[i])

        # get the combined image, using the existing rendering settings
        channels_string = ", ".join([channel_names[i] for i in merged_indexes])
        log("  Rendering merged channels: %s" % channels_string)
        if pro_start != pro_end:
            overlay = re.renderProjectedCompressed(
                algorithm, timepoint, stepping, pro_start, pro_end)
        else:
            plane_def = omero.romio.PlaneDef()
            plane_def.z = pro_start
            plane_def.t = timepoint
            overlay = re.renderCompressed(plane_def)

        # now get each channel in greyscale (or colour)
        # a list of renderedImages (data as Strings) for the split-view row
        rendered_images = []
        i = 0
        channel_mismatch = False
        # first, turn off all channels in pixels
        for i in range(size_c):
            re.setActive(i, False)

        # for each channel in the splitview...
        for index in split_indexes:
            if index >= size_c:
                # can't turn channel on - simply render black square!
                channel_mismatch = True
                rendered_images.append(None)
            else:
                re.setActive(index, True)  # turn channel on
                if colour_channels:  # if split channels are coloured...
                    if index in merged_indexes:
                        # and this channel is in the combined image
                        if index in merged_colours:
                            rgba = tuple(merged_colours[index])
                            re.setRGBA(index, *rgba)        # set coloured
                        else:
                            merged_colours[index] = re.getRGBA(index)
                    else:
                        # otherwise set white (max alpha)
                        re.setRGBA(index, 255, 255, 255, 255)
                else:
                    # if not colour_channels - channels are white
                    re.setRGBA(index, 255, 255, 255, 255)
                info = (index, re.getChannelWindowStart(index),
                        re.getChannelWindowEnd(index))
                log("  Render channel: %s  start: %d  end: %d" % info)
                if pro_start != pro_end:
                    rendered_img = re.renderProjectedCompressed(
                        algorithm, timepoint, stepping, pro_start, pro_end)
                else:
                    plane_def = omero.romio.PlaneDef()
                    plane_def.z = pro_start
                    plane_def.t = timepoint
                    rendered_img = re.renderCompressed(plane_def)
                rendered_images.append(rendered_img)
            if index < size_c:
                re.setActive(index, False)  # turn the channel off again!

        if channel_mismatch:
            log(" WARNING channel mismatch: The current image has fewer"
                " channels than the primary image.")

        # make a canvas for the row of splitview images...
        # extra image for combined image
        image_count = len(rendered_images) + 1
        canvas_width = ((width + spacer) * image_count) + spacer
        canvas_height = spacer + height
        size = (canvas_width, canvas_height)
        # create a canvas of appropriate width, height
        canvas = Image.new(mode, size, white)

        px = spacer
        py = spacer//2
        col = 0
        # paste the images in
        for img in rendered_images:
            if img is None:
                im = Image.new(mode, (size_x, size_y), (0, 0, 0))
            else:
                im = Image.open(io.BytesIO(img))
            i = image_utils.resize_image(im, width, height)
            image_utils.paste_image(i, canvas, px, py)
            px = px + width + spacer
            col = col + 1

        # add combined image, after resizing and adding scale bar
        i = Image.open(io.BytesIO(overlay))
        scaled_image = image_utils.resize_image(i, width, height)
        if scalebar:
            x_indent = spacer
            y_indent = x_indent
            # if we've scaled to half size, zoom = 2
            zoom = image_utils.get_zoom_factor(i.size, width, height)
            # and the scale bar will be half size
            sbar = float(scalebar) / zoom
            status, log_msg = figUtil.addScalebar(
                sbar, x_indent, y_indent, scaled_image, pixels, overlay_colour)
            log(log_msg)

        image_utils.paste_image(scaled_image, canvas, px, py)

        # most should be same width anyway
        total_width = max(total_width, canvas_width)
        # add together the heights of each row
        total_height = total_height + canvas_height
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


def make_split_view_figure(conn, pixel_ids, z_start, z_end, split_indexes,
                           channel_names, colour_channels, merged_indexes,
                           merged_colours, merged_names, width, height,
                           image_labels=None, algorithm=None, stepping=1,
                           scalebar=None, overlay_colour=(255, 255, 255)):

    """
    This method makes a figure of a number of images, arranged in rows with
    each row being the split-view of a single image. The channels are arranged
    left to right, with the combined image added on the right.
    The combined image is rendered according to current settings on the
    server, but it's channels will be turned on/off according to
    @merged_indexes.
    The colour of each channel turned white if colour_channels is false or the
    channel is not in the merged image.
    Otherwise channel is changed to merged_colours[i]
    Text is added at the top of the figure, to display channel names above
    each column, and the combined image may have it's various channels named
    in coloured text. The optional image_labels is a list of string lists for
    naming the images at the left of the figure (Each image may have 0 or
    multiple labels).

    The figure is returned as a PIL 'Image'

    @ conn              session for server access
    @ pixel_ids         a list of the Ids for the pixels we want to display
    @ z_start           the start of Z-range for projection
    @ z_end             the end of Z-range for projection
    @ split_indexes     a list of the channel indexes to display. Same
                        channels for each image/row
    @ channel_names     map of index:name to go above the columns for each
                        split channel
    @ colour_channels   true if split channels are
    @ merged_indexes    list (or set) of channels in the merged image
    @ merged_colours    index: colour map of channels in the merged image
    @ merged_names      if true, label with merged panel with channel names
                        (otherwise, label "Merged")
    @ width             the width of primary image (all images zoomed to this
                        height)
    @ height            the height of primary image
    @ image_labels      optional list of string lists.
    @ algorithm         for projection MAXIMUMINTENSITY or MEANINTENSITY
    @ stepping          projection increment
    """

    fontsize = 12
    if width > 500:
        fontsize = 48
    elif width > 400:
        fontsize = 36
    elif width > 300:
        fontsize = 24
    elif width > 200:
        fontsize = 16

    spacer = (width // 25) + 2
    text_gap = 3        # gap between text and image panels
    left_text_width = 0
    text_height = 0

    # get the rendered splitview, with images surrounded on all sides by
    # spacer
    sv = get_split_view(
        conn, pixel_ids, z_start, z_end, split_indexes, channel_names,
        colour_channels, merged_indexes, merged_colours, width, height, spacer,
        algorithm, stepping, scalebar, overlay_colour)

    font = image_utils.get_font(fontsize)
    mode = "RGB"
    white = (255, 255, 255)
    text_height = font.getsize("Textq")[1]

    # if adding text to the left, write the text on horizontal canvas, then
    # rotate to vertical (below)
    if image_labels:
        # find max number of labels
        max_count = 0
        for row in image_labels:
            max_count = max(max_count, len(row))
        left_text_width = (text_height + text_gap) * max_count
        # make the canvas as wide as the panels height
        size = (sv.size[1], left_text_width)
        text_canvas = Image.new(mode, size, white)
        textdraw = ImageDraw.Draw(text_canvas)
        px = spacer
        image_labels.reverse()
        for row in image_labels:
            py = left_text_width - text_gap  # start at bottom
            for l, label in enumerate(row):
                py = py - text_height    # find the top of this row
                w = textdraw.textsize(label, font=font)[0]
                inset = int((height - w) // 2)
                textdraw.text((px+inset, py), label, font=font,
                              fill=(0, 0, 0))
                py = py - text_gap    # add space between rows
            px = px + spacer + height         # spacer between each row

    top_text_height = text_height + text_gap
    if (merged_names):
        top_text_height = ((text_height) * len(merged_indexes))
    # make a canvas big-enough to add text to the images.
    canvas_width = left_text_width + sv.size[0]
    canvas_height = top_text_height + sv.size[1]
    size = (canvas_width, canvas_height)
    # create a canvas of appropriate width, height
    canvas = Image.new(mode, size, white)

    # add the split-view panel
    paste_x = left_text_width
    paste_y = top_text_height
    image_utils.paste_image(sv, canvas, paste_x, paste_y)

    draw = ImageDraw.Draw(canvas)

    # add text to rows
    # want it to be vertical. Rotate and paste the text canvas from above
    if image_labels:
        text_v = text_canvas.rotate(90, expand=True)
        image_utils.paste_image(text_v, canvas, spacer, top_text_height)

    # add text to columns
    px = spacer + left_text_width
    # edges of panels - rowHeight
    py = top_text_height + spacer - (text_height + text_gap)
    for index in split_indexes:
        # calculate the position of the text, centered above the image
        w = font.getsize(channel_names[index])[0]
        inset = int((width - w) // 2)
        # text is coloured if channel is grey AND in the merged image
        rgba = (0, 0, 0, 255)
        if index in merged_indexes:
            if (not colour_channels) and (index in merged_colours):
                rgba = tuple(merged_colours[index])
                if rgba == (255, 255, 255, 255):  # if white (unreadable)
                    rgba = (0, 0, 0, 255)  # needs to be black!
        draw.text((px+inset, py), channel_names[index], font=font, fill=rgba)
        px = px + width + spacer

    # add text for combined image
    if (merged_names):
        merged_indexes.reverse()
        for index in merged_indexes:
            rgba = (0, 0, 0, 255)
            if index in merged_colours:
                rgba = tuple(merged_colours[index])
                log("%s %s %s" % (index, channel_names[index], rgba))
                if rgba == (255, 255, 255, 255):  # if white (unreadable)
                    rgba = (0, 0, 0, 255)  # needs to be black!
            name = channel_names[index]
            comb_text_width = font.getsize(name)[0]
            inset = int((width - comb_text_width) // 2)
            draw.text((px + inset, py), name, font=font, fill=rgba)
            py = py - text_height
    else:
        comb_text_width = font.getsize("Merged")[0]
        inset = int((width - comb_text_width) // 2)
        px = px + inset
        draw.text((px, py), "Merged", font=font, fill=(0, 0, 0))

    return canvas


def split_view_figure(conn, script_params):
    """
    Processes the arguments, populating defaults if necessary. Prints the
    details to log (fig-legend).
    Even handles missing arguments that are not optional (from when this ran
    from commandline with everything optional)
    then calls make_split_view_figure() to make the figure, attaches it to the
    Image as an 'originalFile' annotation, with fig-legend as the description.

    @return: the id of the originalFileLink child. (ID object, not value)
    """

    log("Split-View figure created by OMERO on %s" % date.today())
    log("")

    message = ""  # message to be returned to the client
    image_ids = []
    pixel_ids = []
    image_labels = []

    # function for getting image labels.
    def get_image_names(full_name, tags_list, pd_list):
        name = full_name.split("/")[-1]
        return [name]

    # default function for getting labels is getName (or use datasets / tags)
    if script_params["Image_Labels"] == "Datasets":
        def get_datasets(name, tags_list, pd_list):
            return [dataset for project, dataset in pd_list]
        get_labels = get_datasets
    elif script_params["Image_Labels"] == "Tags":
        def get_tags(name, tags_list, pd_list):
            return [t for t in tags_list]
        get_labels = get_tags
    else:
        get_labels = get_image_names

    # Get the images
    images, log_message = script_utils.get_objects(conn, script_params)
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
    pd_map = figUtil.getDatasetsProjectsFromImages(conn.getQueryService(),
                                                   image_ids)
    tag_map = figUtil.getTagsFromImages(conn.getMetadataService(), image_ids)
    # Build a legend entry for each image
    for image in images:
        name = image.getName()
        image_date = image.getAcquisitionDate()
        iid = image.getId()
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
    size_c = omero_image.getSizeC()

    # set image dimensions
    z_start = -1
    z_end = -1
    if "Z_Start" in script_params:
        z_start = script_params["Z_Start"]
    if "Z_End" in script_params:
        z_end = script_params["Z_End"]

    width = "Width" in script_params and script_params["Width"] or size_x
    height = "Height" in script_params and script_params["Height"] or size_y

    log("Image dimensions for all panels (pixels): width: %d  height: %d"
        % (width, height))

    # Make split-indexes list. If argument wasn't specified, include them all.
    split_indexes = []
    if "Split_Indexes" in script_params:
        split_indexes = script_params["Split_Indexes"]
    else:
        split_indexes = range(size_c)

    # Make channel-names map. If argument wasn't specified, name by index
    channel_names = {}
    for c in range(size_c):
        channel_names[c] = str(c)
    if "Channel_Names" in script_params:
        c_name_map = script_params["Channel_Names"]
        for c in c_name_map:
            index = int(c)
            channel_names[index] = c_name_map[c]

    merged_indexes = []  # the channels in the combined image,
    merged_colours = {}
    if "Merged_Colours" in script_params:
        c_colour_map = script_params["Merged_Colours"]
        for c in c_colour_map:
            rgb = c_colour_map[c]
            try:
                rgb = int(rgb)
                c_index = int(c)
            except ValueError:
                continue
            rgba = image_utils.int_to_rgba(rgb)
            merged_colours[c_index] = rgba
            merged_indexes.append(c_index)
        merged_indexes.sort()
    else:
        merged_indexes = list(range(size_c))

    colour_channels = not script_params["Split_Panels_Grey"]

    algorithm = ProjectionType.MAXIMUMINTENSITY
    if "Mean Intensity" == script_params["Algorithm"]:
        algorithm = ProjectionType.MEANINTENSITY

    stepping = min(script_params["Stepping"], size_z)

    scalebar = None
    if "Scalebar" in script_params:
        scalebar = script_params["Scalebar"]
        log("Scalebar is %d microns" % scalebar)

    r, g, b, a = OVERLAY_COLOURS[script_params["Overlay_Colour"]]
    overlay_colour = (r, g, b)

    merged_names = script_params["Merged_Names"]

    fig = make_split_view_figure(
        conn, pixel_ids, z_start, z_end, split_indexes, channel_names,
        colour_channels, merged_indexes, merged_colours, merged_names, width,
        height, image_labels, algorithm, stepping, scalebar, overlay_colour)

    fig_legend = "\n".join(log_strings)

    figure_name = script_params["Figure_Name"]
    figure_name = os.path.basename(figure_name)
    output = "localfile"
    format = script_params["Format"]
    if format == 'PNG':
        output = output + ".png"
        figure_name = figure_name + ".png"
        fig.save(output, "PNG")
        mimetype = "image/png"
    elif format == 'TIFF':
        output = output + ".tiff"
        figure_name = figure_name + ".tiff"
        fig.save(output, "TIFF")
        mimetype = "image/tiff"
    else:
        output = output + ".jpg"
        figure_name = figure_name + ".jpg"
        fig.save(output)
        mimetype = "image/jpeg"

    # Upload the figure 'output' to the server, creating a file annotation and
    # attaching it to the omero_image, adding the
    # fig_legend as the fileAnnotation description.
    namespace = NSCREATED + "/omero/figure_scripts/Split_View_Figure"
    file_annotation, fa_message = script_utils.create_link_file_annotation(
        conn, output, omero_image, output="Split view figure",
        mimetype=mimetype, namespace=namespace, description=fig_legend,
        orig_file_path_and_name=figure_name)
    message += fa_message

    return file_annotation, message


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    data_types = [rstring('Image')]
    labels = [rstring('Image Name'), rstring('Datasets'), rstring('Tags')]
    algorithms = [rstring('Maximum Intensity'), rstring('Mean Intensity')]
    formats = [rstring('JPEG'), rstring('PNG'), rstring('TIFF')]
    ckeys = list(COLOURS.keys())
    ckeys.sort()
    o_colours = wrap(list(OVERLAY_COLOURS.keys()))

    client = scripts.client(
        'Split_View_Figure.py',
        """Create a figure of split-view images.
See http://help.openmicroscopy.org/publish.html#figures""",

        # provide 'Data_Type' and 'IDs' parameters so that Insight
        # auto-populates with currently selected images.
        scripts.String(
            "Data_Type", optional=False, grouping="01",
            description="The data you want to work with.", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="02",
            description="List of Image IDs").ofType(rlong(0)),

        scripts.String(
            "Algorithm", grouping="3",
            description="Algorithm for projection. Only used if a Z-range is"
            " chosen below", values=algorithms, default='Maximum Intensity'),

        scripts.Int(
            "Z_Start", grouping="3.1",
            description="Projection range (if not specified, use defaultZ"
            " only - no projection)", min=0),

        scripts.Int(
            "Z_End", grouping="3.2",
            description="Projection range (if not specified, use defaultZ"
            " only - no projection)", min=0),

        scripts.Map(
            "Channel_Names", grouping="4",
            description="Map of index: channel name for all channels"),

        scripts.List(
            "Split_Indexes", grouping="5",
            description="List of the channels in the split"
            " view").ofType(rint(0)),

        scripts.Bool(
            "Split_Panels_Grey", grouping="6",
            description="If true, all split panels are grayscale",
            default=False),

        scripts.Map(
            "Merged_Colours", grouping="7",
            description="Map of index:int colors for each merged channel"),

        scripts.Bool(
            "Merged_Names", grouping="8",
            description="If true, label the merged panel with channel names."
            " Otherwise label with 'Merged'", default=True),

        scripts.Int(
            "Width", grouping="9",
            description="The max width of each image panel. Default is"
            " first image width", min=1),

        scripts.Int(
            "Height", grouping="91",
            description="The max height of each image panel. Default is"
            " first image height", min=1),

        scripts.String(
            "Image_Labels", grouping="92",
            description="Label images with Image name (default) or datasets"
            " or tags", values=labels, default='Image Name'),

        scripts.Int(
            "Stepping", grouping="93",
            description="The Z increment for projection.", default=1, min=1),

        scripts.Int(
            "Scalebar", grouping="94",
            description="Scale bar size in microns. Only shown if image has"
            " pixel-size info.", min=1),

        scripts.String(
            "Format", grouping="95",
            description="Format to save image", values=formats,
            default='JPEG'),

        scripts.String(
            "Figure_Name", grouping="96",
            description="File name of the figure to save.",
            default='Split_View_Figure'),

        scripts.String(
            "Overlay_Colour", grouping="97",
            description="The color of the scale bar.",
            default='White', values=o_colours),

        version="4.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)

        # call the main script, attaching resulting figure to Image. Returns
        # the FileAnnotationI
        [file_annotation, message] = split_view_figure(conn, script_params)

        # Return message and file annotation (if applicable) to the client
        client.setOutput("Message", rstring(message))
        if file_annotation is not None:
            client.setOutput("File_Annotation", robject(file_annotation._obj))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
