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

This script takes a number of images and displays regions defined by their
ROIs as zoomed panels beside the images.

@author  William Moore &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@author  Jean-Marie Burel &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:j.burel@dundee.ac.uk">j.burel@dundee.ac.uk</a>
@author Donald MacDonald &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:donald@lifesci.dundee.ac.uk">donald@lifesci.dundee.ac.uk</a>
@since 3.0

"""

import omero
import omero.scripts as scripts
import omero.util.image_utils as image_utils
import omero.util.figureUtil as figUtil
import omero.util.script_utils as script_utils
from omero.gateway import BlitzGateway
from omero.rtypes import rlong, robject, rstring, wrap, unwrap
import os
from omero.constants.namespaces import NSCREATED
from omero.constants.projection import ProjectionType
import io
from datetime import date

try:
    from PIL import Image, ImageDraw  # see ticket:2597
except ImportError:
    import Image
    import ImageDraw  # see ticket:2597


COLOURS = script_utils.COLOURS    # name:(rgba) map
OVERLAY_COLOURS = dict(COLOURS, **script_utils.EXTRA_COLOURS)

log_strings = []


def log(text):
    """
    Adds the text to a list of logs. Compiled into figure legend at the end.
    """
    log_strings.append(text)


def get_roi_split_view(re, pixels, z_start, z_end, split_indexes,
                       channel_names, merged_names, colour_channels,
                       merged_indexes, merged_colours, roi_x, roi_y,
                       roi_width, roi_height, roi_zoom, t_index, spacer,
                       algorithm, stepping, fontsize, show_top_labels):
    """
    This takes a ROI rectangle from an image and makes a split view canvas of
    the region in the ROI, zoomed by a defined factor.

    @param    re        The OMERO rendering engine.
    """

    if algorithm is None:    # omero::constants::projection::ProjectionType
        algorithm = ProjectionType.MAXIMUMINTENSITY
    mode = "RGB"
    white = (255, 255, 255)

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
    log("  Image dimensions (pixels): x: %d  y: %d" % (size_x, size_y))

    log(" Projecting ROIs...")
    pro_start = z_start
    pro_end = z_end
    # make sure we're within Z range for projection.
    if pro_end >= size_z:
        pro_end = size_z - 1
        if pro_start > size_z:
            pro_start = 0
        log(" WARNING: Current image has fewer Z-sections than the primary"
            " image projection.")
    if pro_start < 0:
        pro_start = 0
    log("  Projecting z range: %d - %d   (max Z is %d)"
        % (pro_start+1, pro_end+1, size_z))
    # set up rendering engine with the pixels
    pixels_id = pixels.getId().getValue()
    re.lookupPixels(pixels_id)
    if not re.lookupRenderingDef(pixels_id):
        re.resetDefaults()
    if not re.lookupRenderingDef(pixels_id):
        raise "Failed to lookup Rendering Def"
    re.load()

    # if we are missing some merged colours, get them from rendering engine.
    for index in merged_indexes:
        if index not in merged_colours:
            color = tuple(re.getRGBA(index))
            merged_colours[index] = color

    # now get each channel in greyscale (or colour)
    # a list of renderedImages (data as Strings) for the split-view row
    rendered_images = []
    panel_width = 0
    channel_mismatch = False
    # first, turn off all channels in pixels
    for i in range(size_c):
        re.setActive(i, False)

    # for each channel in the splitview...
    box = (roi_x, roi_y, roi_x+roi_width, roi_y+roi_height)
    for index in split_indexes:
        if index >= size_c:
            # can't turn channel on - simply render black square!
            channel_mismatch = True
        else:
            re.setActive(index, True)   # turn channel on
            if colour_channels:
                # if split channels are coloured...
                if index in merged_colours:
                    # and this channel is in the combined image
                    rgba = tuple(merged_colours[index])
                    re.setRGBA(index, *rgba)        # set coloured
                else:
                    re.setRGBA(index, 255, 255, 255, 255)
            else:
                # if not colourChannels - channels are white
                re.setRGBA(index, 255, 255, 255, 255)
            info = (channel_names[index], re.getChannelWindowStart(index),
                    re.getChannelWindowEnd(index))
            log("  Render channel: %s  start: %d  end: %d" % info)
            if pro_start == pro_end:
                # if it's a single plane, we can render a region (region not
                # supported with projection)
                plane_def = omero.romio.PlaneDef()
                plane_def.z = int(pro_start)
                plane_def.t = int(t_index)
                region_def = omero.romio.RegionDef()
                region_def.x = roi_x
                region_def.y = roi_y
                region_def.width = roi_width
                region_def.height = roi_height
                plane_def.region = region_def
                r_plane = re.renderCompressed(plane_def)
                roi_image = Image.open(io.BytesIO(r_plane))
            else:
                projection = re.renderProjectedCompressed(
                    algorithm, t_index, stepping, pro_start, pro_end)
                full_image = Image.open(io.BytesIO(projection))
                roi_image = full_image.crop(box)
                roi_image.load()
                # hoping that when we zoom, don't zoom fullImage
            if roi_zoom != 1:
                new_size = (int(roi_width*roi_zoom), int(roi_height*roi_zoom))
                roi_image = roi_image.resize(new_size, Image.ANTIALIAS)
            rendered_images.append(roi_image)
            panel_width = roi_image.size[0]
            re.setActive(index, False)  # turn the channel off again!

    # turn on channels in mergedIndexes.
    for i in merged_indexes:
        if i >= size_c:
            channel_mismatch = True
        else:
            re.setActive(i, True)
            if i in merged_colours:
                rgba = merged_colours[i]
                re.setRGBA(i, *rgba)

    # get the combined image, using the existing rendering settings
    channels_string = ", ".join([str(i) for i in merged_indexes])
    log("  Rendering merged channels: %s" % channels_string)
    if pro_start != pro_end:
        merged = re.renderProjectedCompressed(
            algorithm, t_index, stepping, pro_start, pro_end)
    else:
        plane_def = omero.romio.PlaneDef()
        plane_def.z = pro_start
        plane_def.t = t_index
        merged = re.renderCompressed(plane_def)
    full_merged_image = Image.open(io.BytesIO(merged))
    roi_merged_image = full_merged_image.crop(box)
    # make sure this is not just a lazy copy of the full image
    roi_merged_image.load()

    if roi_zoom != 1:
        new_size = (int(roi_width*roi_zoom), int(roi_height*roi_zoom))
        roi_merged_image = roi_merged_image.resize(new_size, Image.ANTIALIAS)

    if channel_mismatch:
        log(" WARNING channel mismatch: The current image has fewer channels"
            " than the primary image.")

    if panel_width == 0:  # e.g. No split-view panels
        panel_width = roi_merged_image.size[0]

    # now assemble the roi split-view canvas
    font = image_utils.get_font(fontsize)
    text_height = font.getsize("Textq")[1]
    top_spacer = 0
    if show_top_labels:
        if merged_names:
            top_spacer = (text_height * len(merged_indexes)) + spacer
        else:
            top_spacer = text_height + spacer
    image_count = len(rendered_images) + 1     # extra image for merged image
    # no spaces around panels
    canvas_width = int(((panel_width + spacer) * image_count) - spacer)
    canvas_height = int(roi_merged_image.size[1] + top_spacer)

    size = (canvas_width, canvas_height)
    # create a canvas of appropriate width, height
    canvas = Image.new(mode, size, white)

    px = 0
    text_y = top_spacer - text_height - spacer // 2
    panel_y = int(top_spacer)
    # paste the split images in, with channel labels
    draw = ImageDraw.Draw(canvas)
    for i, index in enumerate(split_indexes):
        label = channel_names.get(index, index)
        indent = (panel_width - (font.getsize(label)[0])) // 2
        # text is coloured if channel is not coloured AND in the merged image
        rgb = (0, 0, 0)
        if index in merged_colours:
            if not colour_channels:
                rgb = tuple(merged_colours[index])
                if rgb == (255, 255, 255, 255):
                    # if white (unreadable), needs to be black!
                    rgb = (0, 0, 0)
        if show_top_labels:
            draw.text((px+indent, text_y), label, font=font, fill=rgb)
        if i < len(rendered_images):
            image_utils.paste_image(rendered_images[i], canvas, px, panel_y)
        px = int(px + panel_width + spacer)
    # and the merged image
    if show_top_labels:
        if (merged_names):
            for index in merged_indexes:
                if index in merged_colours:
                    rgb = tuple(merged_colours[index])
                    if rgb == (255, 255, 255, 255):
                        rgb = (0, 0, 0)
                else:
                    rgb = (0, 0, 0)
                if index in channel_names:
                    name = channel_names[index]
                else:
                    name = str(index)
                comb_text_width = font.getsize(name)[0]
                inset = int((panel_width - comb_text_width) / 2)
                draw.text((px + inset, text_y), name, font=font, fill=rgb)
                text_y = text_y - text_height
        else:
            comb_text_width = font.getsize("Merged")[0]
            inset = int((panel_width - comb_text_width) / 2)
            draw.text((px + inset, text_y), "Merged", font=font,
                      fill=(0, 0, 0))
    image_utils.paste_image(roi_merged_image, canvas, px, panel_y)

    # return the roi splitview canvas, as well as the full merged image
    return (canvas, full_merged_image, panel_y)


def draw_rectangle(image, roi_x, roi_y, roi_x2, roi_y2, colour, stroke=1):
    roi_draw = ImageDraw.Draw(image)
    for s in range(stroke):
        roi_box = (roi_x, roi_y, roi_x2, roi_y2)
        roi_draw.rectangle(roi_box, outline=colour)
        roi_x += 1
        roi_y += 1
        roi_x2 -= 1
        roi_y2 -= 1


def get_rectangle(roi_service, image_id, roi_label):
    """
    Returns (x, y, width, height, zMin, zMax, tMin, tMax) of the first
    rectange in the image that has @roi_label as text
    """

    result = roi_service.findByImage(image_id, None)

    roi_text = roi_label.lower()
    roi_count = 0
    rect_count = 0
    found_labelled_roi = False

    for roi in result.rois:
        roi_count += 1
        # go through all the shapes of the ROI
        for shape in roi.copyShapes():
            if type(shape) == omero.model.RectangleI:
                the_t = unwrap(shape.getTheT())
                the_z = unwrap(shape.getTheZ())
                t = 0
                z = 0
                if the_t is not None:
                    t = the_t
                if the_z is not None:
                    z = the_z
                x = shape.getX().getValue()
                y = shape.getY().getValue()
                tv = shape.getTextValue()
                if tv is not None:
                    text = tv.getValue()
                else:
                    text = ""

                # get ranges for whole ROI
                if rect_count == 0:
                    z_min = z
                    z_max = z_min
                    t_min = t
                    t_max = t_min
                    width = shape.getWidth().getValue()
                    height = shape.getHeight().getValue()
                else:
                    z_min = min(z_min, z)
                    z_max = max(z_max, z)
                    t_min = min(t_min, t)
                    t_max = max(t_max, t)
                rect_count += 1
                if text is not None and text.lower() == roi_text:
                    found_labelled_roi = True
        if found_labelled_roi:
            return (int(x), int(y), int(width), int(height), int(z_min),
                    int(z_max), int(t_min), int(t_max))
        else:
            rect_count = 0    # try another ROI

    # if we got here without finding an ROI that matched, simply return any
    # ROI we have (last one)
    if roi_count > 0:
        return (int(x), int(y), int(width), int(height), int(z_min),
                int(z_max), int(t_min), int(t_max))


def get_split_view(conn, image_ids, pixel_ids, split_indexes, channel_names,
                   merged_names, colour_channels, merged_indexes,
                   merged_colours, width, height, image_labels, spacer,
                   algorithm, stepping, scalebar, overlay_colour, roi_zoom,
                   roi_label):

    """
    This method makes a figure of a number of images, arranged in rows with
    each row being the split-view of a single image. The channels are arranged
    left to right, with the combined image added on the right.
    The combined image is rendered according to current settings on the
    server, but it's channels will be turned on/off according to
    @mergedIndexes.

    The figure is returned as a PIL 'Image'

    @ session           session for server access
    @ pixel_ids         a list of the Ids for the pixels we want to display
    @ split_indexes     a list of the channel indexes to display. Same
                        channels for each image/row
    @ channel_names     the Map of index:names for all channels
    @ colour_channels   the colour to make each column/ channel
    @ merged_indexes    list or set of channels in the merged image
    @ merged_colours    index: colour dictionary of channels in the merged
                        image
    @ width             the size in pixels to show each panel
    @ height            the size in pixels to show each panel
    @ spacer            the gap between images and around the figure. Doubled
                        between rows.
    """

    roi_service = conn.getRoiService()
    re = conn.createRenderingEngine()
    query_service = conn.getQueryService()    # only needed for movie

    # establish dimensions and roiZoom for the primary image
    # getTheseValues from the server
    rect = get_rectangle(roi_service, image_ids[0], roi_label)
    if rect is None:
        raise Exception("No ROI found for the first image.")
    roi_x, roi_y, roi_width, roi_height, y_min, y_max, t_min, t_max = rect

    roi_outline = ((max(width, height)) // 200) + 1

    if roi_zoom is None:
        # get the pixels for priamry image.
        pixels = query_service.get("Pixels", pixel_ids[0])
        size_y = pixels.getSizeY().getValue()

        roi_zoom = float(height) / float(roi_height)
        log("ROI zoom set by primary image is %F X" % roi_zoom)
    else:
        log("ROI zoom: %F X" % roi_zoom)

    text_gap = spacer // 3
    fontsize = 12
    if width > 500:
        fontsize = 48
    elif width > 400:
        fontsize = 36
    elif width > 300:
        fontsize = 24
    elif width > 200:
        fontsize = 16
    font = image_utils.get_font(fontsize)
    text_height = font.getsize("Textq")[1]
    max_count = 0
    for row in image_labels:
        max_count = max(max_count, len(row))
    left_text_width = (text_height + text_gap) * max_count + spacer

    max_split_panel_width = 0
    total_canvas_height = 0
    merged_images = []
    roi_split_panes = []
    top_spacers = []         # space for labels above each row

    show_labels_above_every_row = False
    invalid_images = []      # note any image row indexes that don't have ROIs.

    for row, pixels_id in enumerate(pixel_ids):
        log("Rendering row %d" % (row))

        if show_labels_above_every_row:
            show_top_labels = True
        else:
            show_top_labels = (row == 0)  # only show top labels for first row

        # need to get the roi dimensions from the server
        image_id = image_ids[row]
        roi = get_rectangle(roi_service, image_id, roi_label)
        if roi is None:
            log("No Rectangle ROI found for this image")
            invalid_images.append(row)
            continue

        roi_x, roi_y, roi_width, roi_height, z_min, z_max, t_start, t_end = roi

        pixels = query_service.get("Pixels", pixels_id)
        size_x = pixels.getSizeX().getValue()
        size_y = pixels.getSizeY().getValue()

        z_start = z_min
        z_end = z_max

        # work out if any additional zoom is needed (if the full-sized image
        # is different size from primary image)
        full_size = (size_x, size_y)
        image_zoom = image_utils.get_zoom_factor(full_size, width, height)
        if image_zoom != 1.0:
            log("  Scaling down the full-size image by a factor of %F"
                % image_zoom)

        log("  ROI location (top-left) x: %d  y: %d  and size width:"
            " %d  height: %d" % (roi_x, roi_y, roi_width, roi_height))
        log("  ROI time: %d - %d   zRange: %d - %d"
            % (t_start+1, t_end+1, z_start+1, z_end+1))
        # get the split pane and full merged image
        roi_split_pane, full_merged_image, top_spacer = get_roi_split_view(
            re, pixels, z_start, z_end, split_indexes, channel_names,
            merged_names, colour_channels, merged_indexes, merged_colours,
            roi_x, roi_y, roi_width, roi_height, roi_zoom, t_start, spacer,
            algorithm, stepping, fontsize, show_top_labels)

        # and now zoom the full-sized merged image, add scalebar
        merged_image = image_utils.resize_image(full_merged_image, width,
                                                height)
        if scalebar:
            x_indent = spacer
            y_indent = x_indent
            # and the scale bar will be half size
            sbar = float(scalebar) / image_zoom
            status, log_msg = figUtil.addScalebar(
                sbar, x_indent, y_indent, merged_image, pixels, overlay_colour)
            log(log_msg)

        # draw ROI onto mergedImage...
        # recalculate roi if the image has been zoomed
        x = roi_x // image_zoom
        y = roi_y // image_zoom
        roi_x2 = (roi_x + roi_width) // image_zoom
        roi_y2 = (roi_y + roi_height) // image_zoom
        draw_rectangle(
            merged_image, x, y, roi_x2, roi_y2, overlay_colour, roi_outline)

        # note the maxWidth of zoomed panels and total height for row
        max_split_panel_width = max(max_split_panel_width,
                                    roi_split_pane.size[0])
        total_canvas_height += spacer + max(height+top_spacer,
                                            roi_split_pane.size[1])

        merged_images.append(merged_image)
        roi_split_panes.append(roi_split_pane)
        top_spacers.append(top_spacer)

    # remove the labels for the invalid images (without ROIs)
    invalid_images.reverse()
    for row in invalid_images:
        del image_labels[row]

    # make a figure to combine all split-view rows
    # each row has 1/2 spacer above and below the panels. Need extra 1/2
    # spacer top and bottom
    canvas_width = left_text_width + width + 2 * spacer + max_split_panel_width
    figure_size = (int(canvas_width), int(total_canvas_height + spacer))
    figure_canvas = Image.new("RGB", figure_size, (255, 255, 255))

    row_y = spacer
    for row, image in enumerate(merged_images):
        label_canvas = figUtil.getVerticalLabels(image_labels[row], font,
                                                 text_gap)
        v_offset = (image.size[1] - label_canvas.size[1]) // 2
        image_utils.paste_image(label_canvas, figure_canvas, int(spacer // 2),
                                int(row_y + top_spacers[row] + v_offset))
        image_utils.paste_image(image, figure_canvas, int(left_text_width),
                                int(row_y + top_spacers[row]))
        x = left_text_width + width + spacer
        image_utils.paste_image(roi_split_panes[row], figure_canvas,
                                int(x), int(row_y))
        row_y = row_y + max(image.size[1] + top_spacers[row],
                            roi_split_panes[row].size[1]) + spacer

    return figure_canvas


def roi_figure(conn, command_args):
    """
    This processes the script parameters, adding defaults if needed.
    Then calls a method to make the figure, and finally uploads and attaches
    this to the primary image.

    @param: session         The OMERO session
    @param: command_args    Map of String:Object parameters for the script.
                            Objects are not rtypes, since getValue() was
                            called when the map was processed below.
                            But, list and map objects may contain rtypes (need
                            to call getValue())

    @return:                the id of the originalFileLink child. (ID object,
                            not value)
    """

    log("ROI figure created by OMERO on %s" % date.today())
    log("")

    message = ""  # message to be returned to the client
    pixel_ids = []
    image_ids = []
    image_labels = []

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

    # Check for rectangular ROIs and filter images list
    images = [image for image in images if image.getROICount("Rectangle") > 0]
    if not images:
        message += "No rectangle ROI found."
        return None, message

    # Attach figure to the first image
    omero_image = images[0]

    # process the list of images. If image_ids is not set, script can't run.
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

    width = size_x
    if "Width" in command_args:
        w = command_args["Width"]
        try:
            width = int(w)
        except ValueError:
            log("Invalid width: %s Using default value: %d" % (str(w), size_x))

    height = size_y
    if "Height" in command_args:
        h = command_args["Height"]
        try:
            height = int(h)
        except ValueError:
            log("Invalid height: %s Using default value" % (str(h), size_y))

    log("Image dimensions for all panels (pixels): width: %d  height: %d"
        % (width, height))

    merged_indexes = []    # the channels in the combined image,
    merged_colours = {}
    if "Merged_Colours" in command_args:
        c_colour_map = command_args["Merged_Colours"]
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
    # make sure we have some merged channels
    if len(merged_indexes) == 0:
        merged_indexes = list(range(size_c))
    merged_indexes.reverse()

    merged_names = False
    if "Merged_Names" in command_args:
        merged_names = command_args["Merged_Names"]

    # Make channel-names map. If argument wasn't specified, name by index
    channel_names = {}
    if "Channel_Names" in command_args:
        c_name_map = command_args["Channel_Names"]
        for c in range(size_c):
            if str(c) in c_name_map:
                channel_names[c] = c_name_map[str(c)]
            else:
                channel_names[c] = str(c)
    else:
        for c in range(size_c):
            channel_names[c] = str(c)

    # Make split-indexes list. If no "Split_Indexes", show none:
    # http://www.openmicroscopy.org/community/viewtopic.php?f=4&t=940
    split_indexes = []
    if "Split_Indexes" in command_args:
        for index in command_args["Split_Indexes"]:
            split_indexes.append(index)

    colour_channels = True
    key = "Split_Panels_Grey"
    if key in command_args and command_args[key]:
        colour_channels = False

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
    if "Overlay_Colour" in command_args:
        r, g, b, a = OVERLAY_COLOURS[command_args["Overlay_Colour"]]
        overlay_colour = (r, g, b)

    roi_zoom = None
    if "ROI_Zoom" in command_args:
        roi_zoom = float(command_args["ROI_Zoom"])
        if roi_zoom == 0:
            roi_zoom = None

    roi_label = "FigureROI"
    if "ROI_Label" in command_args:
        roi_label = command_args["ROI_Label"]

    spacer = (width/50) + 2

    fig = get_split_view(
        conn, image_ids, pixel_ids, split_indexes, channel_names, merged_names,
        colour_channels, merged_indexes, merged_colours, width, height,
        image_labels, spacer, algorithm, stepping, scalebar, overlay_colour,
        roi_zoom, roi_label)

    if fig is None:
        log_message = "No figure produced"
        log("\n"+log_message)
        message += log_message
        return None, message

    log("")
    fig_legend = "\n".join(log_strings)

    format = command_args["Format"]

    figure_name = "roi_figure"
    if "Figure_Name" in command_args:
        figure_name = command_args["Figure_Name"]
        figure_name = os.path.basename(figure_name)
    output = "localfile"
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

    # Use util method to upload the figure 'output' to the server, attaching
    # it to the omeroImage, adding the
    # figLegend as the fileAnnotation description.
    # Returns the id of the originalFileLink child. (ID object, not value)
    namespace = NSCREATED + "/omero/figure_scripts/ROI_Split_Figure"
    file_annotation, fa_message = script_utils.create_link_file_annotation(
        conn, output, omero_image, output="ROI Split figure",
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
    roi_label = """Specify an ROI to pick by specifying its shape label. \
'FigureROI' by default, (not case sensitive). If matching ROI not found, use \
any ROI."""
    formats = [rstring('JPEG'), rstring('PNG'), rstring('TIFF')]
    ckeys = list(COLOURS.keys())
    ckeys.sort()
    o_colours = wrap(list(OVERLAY_COLOURS.keys()))

    client = scripts.client(
        'ROI_Split_Figure.py',
        """Create a figure of an ROI region as separate zoomed split-channel \
panels.
NB: OMERO.insight client provides a nicer UI for this script under \
'Publishing Options'
See http://help.openmicroscopy.org/publish.html#figures""",

        # provide 'Data_Type' and 'IDs' parameters so that Insight
        # auto-populates with currently selected images.
        scripts.String(
            "Data_Type", optional=False, grouping="01",
            description="The data you want to work with.",
            values=data_types, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="02",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        scripts.Map(
            "Channel_Names", grouping="03",
            description="Map of index: channel name for All channels"),

        scripts.Bool(
            "Merged_Names", grouping="04",
            description="If true, label the merged panel with channel names."
            " Otherwise label with 'Merged'"),

        scripts.List(
            "Split_Indexes", grouping="05",
            description="List of the channels in the split view panels"),

        scripts.Bool(
            "Split_Panels_Grey", grouping="06",
            description="If true, all split panels are grayscale"),

        scripts.Map(
            "Merged_Colours", grouping="07",
            description="Map of index:int colors for each merged channel."
            " Otherwise use existing color settings"),

        scripts.Int(
            "Width", grouping="08",
            description="Max width of each image panel", min=1),

        scripts.Int(
            "Height", grouping="09",
            description="The max height of each image panel", min=1),

        scripts.String(
            "Image_Labels", grouping="10",
            description="Label images with the Image's Name or its Datasets"
            " or Tags", values=labels),

        scripts.String(
            "Algorithm", grouping="11",
            description="Algorithm for projection.", values=algorithms),

        scripts.Int(
            "Stepping", grouping="12",
            description="The Z-plane increment for projection. Default is 1",
            min=1),

        scripts.Int(
            "Scalebar", grouping="13",
            description="Scale bar size in microns. Only shown if image has"
            " pixel-size info.", min=1),

        scripts.String(
            "Format", grouping="14",
            description="Format to save image e.g 'PNG'.",
            values=formats, default='JPEG'),

        scripts.String(
            "Figure_Name", grouping="15",
            description="File name of the figure to save."),

        scripts.String(
            "Overlay_Colour", grouping="16",
            description="The color of the scale bar.",
            default='White', values=o_colours),

        scripts.Float(
            "ROI_Zoom", grouping="17",
            description="How much to zoom the ROI e.g. x 2. If 0 then zoom"
            " roi panel to fit", min=0),

        scripts.String("ROI_Label", grouping="18", description=roi_label),

        version="4.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )
    try:
        conn = BlitzGateway(client_obj=client)

        command_args = client.getInputs(unwrap=True)

        # call the main script, attaching resulting figure to Image. Returns
        # the id of the originalFileLink child. (ID object, not value)
        file_annotation, message = roi_figure(conn, command_args)

        # Return message and file annotation (if applicable) to the client
        client.setOutput("Message", rstring(message))
        if file_annotation is not None:
            client.setOutput("File_Annotation", robject(file_annotation._obj))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
