#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
-----------------------------------------------------------------------------
  Copyright (C) 2006-2014 University of Dundee. All rights reserved.


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

import omero.scripts as scripts
import omero.util.image_utils as image_utils
import omero.util.figureUtil as figUtil
import omero.util.script_utils as script_utils
from omero.gateway import BlitzGateway
from omero.rtypes import rlong, rint, rstring, robject, wrap, unwrap
from omero.constants.namespaces import NSCREATED
import omero.model
from omero.constants.projection import ProjectionType
import os
import io
from datetime import date

try:
    from PIL import Image, ImageDraw  # see ticket:2597
except ImportError:
    import Image
    import ImageDraw  # see ticket:2597


COLOURS = script_utils.COLOURS
OVERLAY_COLOURS = dict(COLOURS, **script_utils.EXTRA_COLOURS)

log_strings = []


def log(text):
    """
    Adds the text to a list of logs. Compiled into figure legend at the end.
    """
    log_strings.append(text)


def get_time_indexes(time_points, max_frames):
    """
    If we want to display a number of timepoints (e.g. 11), without exceeding
    max_frames (e.g. 5), need to pick a selection of t-indexes e.g. 0, 2, 4, 7,
    10
    This method returns the list of indexes. NB - Not used at present - but
    might be needed.
    """
    frames = min(max_frames, time_points)
    interval_count = frames-1
    smallest_interval = (time_points-1)//interval_count
    # make a list of intervals, making the last intervals bigger if needed
    intervals = [smallest_interval] * interval_count
    extra = (time_points-1) % interval_count
    for e in range(extra):
        last_index = -(e+1)
        intervals[last_index] += 1
    # convert the list of intervals into indexes.
    indexes = []
    time = 0
    indexes.append(time)
    for i in range(frames-1):
        time += intervals[i]
        indexes.append(time)
    return indexes


def get_roi_movie_view(re, query_service, pixels, time_shape_map,
                       merged_indexes, merged_colours, roi_width,
                       roi_height, roi_zoom, spacer=12,
                       algorithm=None, stepping=1, font_size=24,
                       max_columns=None, show_roi_duration=False):

    """
    This takes a ROI rectangle from an image and makes a movie canvas of the
    region in the ROI, zoomed by a defined factor.
    """

    mode = "RGB"
    white = (255, 255, 255)

    size_x = pixels.getSizeX().getValue()
    size_y = pixels.getSizeY().getValue()
    size_z = pixels.getSizeZ().getValue()
    size_c = pixels.getSizeC().getValue()
    size_t = pixels.getSizeT().getValue()

    if pixels.getPhysicalSizeX():
        physical_x = pixels.getPhysicalSizeX().getValue()
    else:
        physical_x = 0
    if pixels.getPhysicalSizeY():
        physical_y = pixels.getPhysicalSizeY().getValue()
    else:
        physical_y = 0
    log("  Pixel size (um): x: %s  y: %s" % (str(physical_x), str(physical_y)))
    log("  Image dimensions (pixels): x: %d  y: %d" % (size_x, size_y))
    log(" Projecting Movie Frame ROIs...")

    # set up rendering engine with the pixels
    pixels_id = pixels.getId().getValue()
    re.lookupPixels(pixels_id)
    if not re.lookupRenderingDef(pixels_id):
        re.resetDefaults()
    if not re.lookupRenderingDef(pixels_id):
        raise "Failed to lookup Rendering Def"
    re.load()

    # now get each channel in greyscale (or colour)
    # a list of renderedImages (data as Strings) for the split-view row
    rendered_images = []
    panel_width = 0
    channel_mismatch = False
    # first, turn off all channels in pixels
    for i in range(size_c):
        re.setActive(i, False)

    # turn on channels in mergedIndexes.
    for i in merged_indexes:
        if i >= size_c or i < 0:
            channel_mismatch = True
        else:
            re.setActive(i, True)
            if i in merged_colours:
                rgba = merged_colours[i]
                re.setRGBA(i, *rgba)

    # get the combined image, using the existing rendering settings
    channels_string = ", ".join([str(i) for i in merged_indexes])
    log("  Rendering Movie channels: %s" % channels_string)

    time_indexes = list(time_shape_map.keys())
    time_indexes.sort()

    if show_roi_duration:
        log(" Timepoints shown are ROI duration, not from start of movie")
    time_labels = figUtil.getTimeLabels(query_service, pixels_id,
                                        time_indexes, size_t, None,
                                        show_roi_duration)
    # The last value of the list will be the Units used to display time

    full_first_frame = None
    for t, timepoint in enumerate(time_indexes):
        roi_x, roi_y, pro_start, pro_end = time_shape_map[timepoint]
        box = (roi_x, roi_y, int(roi_x+roi_width), int(roi_y+roi_height))
        log("  Time-index: %d Time-label: %s  Projecting z range: %d - %d "
            "(max Z is %d) of region x: %s y: %s"
            % (timepoint+1, time_labels[t], pro_start+1, pro_end+1, size_z,
               roi_x, roi_y))

        merged = re.renderProjectedCompressed(
            algorithm, timepoint, stepping, pro_start, pro_end)
        full_merged_image = Image.open(io.BytesIO(merged))
        if full_first_frame is None:
            full_first_frame = full_merged_image
        roi_merged_image = full_merged_image.crop(box)
        # make sure this is not just a lazy copy of the full image
        roi_merged_image.load()
        if roi_zoom != 1:
            new_size = (int(roi_width*roi_zoom), int(roi_height*roi_zoom))
            roi_merged_image = roi_merged_image.resize(new_size)
        panel_width = roi_merged_image.size[0]
        rendered_images.append(roi_merged_image)

    if channel_mismatch:
        log(" WARNING channel mismatch: The current image has fewer channels"
            " than the primary image.")

    # now assemble the roi split-view canvas, with space above for text
    col_count = len(rendered_images)
    row_count = 1
    if max_columns:
        row_count = col_count // max_columns
        if (col_count % max_columns) > 0:
            row_count += 1
        col_count = max_columns
    font = image_utils.get_font(font_size)
    text_height = font.getsize("Textq")[1]
    # no spaces around panels
    canvas_width = ((panel_width + spacer) * col_count) - spacer
    row_height = rendered_images[0].size[1] + spacer + text_height
    canvas_height = row_height * row_count
    size = (canvas_width, canvas_height)
    # create a canvas of appropriate width, height
    canvas = Image.new(mode, size, white)

    px = 0
    text_y = spacer // 2
    panel_y = text_height + spacer
    # paste the images in, with time labels
    draw = ImageDraw.Draw(canvas)

    col = 0
    for i, img in enumerate(rendered_images):
        label = time_labels[i]
        indent = (panel_width - (font.getsize(label)[0])) // 2
        draw.text((px+indent, text_y), label, font=font, fill=(0, 0, 0))
        image_utils.paste_image(img, canvas, px, panel_y)
        if col == (col_count - 1):
            col = 0
            px = 0
            text_y += row_height
            panel_y += row_height
        else:
            col += 1
            px = px + panel_width + spacer

    # return the roi splitview canvas, as well as the full merged image
    return (canvas, full_first_frame, text_height + spacer)


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
    Returns (x, y, width, height, timeShapeMap) of the all rectanges in the
    first ROI of the image where timeShapeMap is a map of tIndex:
    (x,y,zMin,zMax)
    x, y, Width and Height are from the first rectangle (assumed that all are
    same size!)
    """

    result = roi_service.findByImage(image_id, None)

    roi_text = roi_label.lower()
    roi_count = 0
    rect_count = 0
    found_labelled_roi = False

    for roi in result.rois:
        rectangles = [shape for shape in roi.copyShapes()
                      if isinstance(shape, omero.model.RectangleI)]
        if len(rectangles) == 0:
            continue

        time_shape_map = {}  # map of tIndex: (x,y,zMin,zMax) for a single roi
        for shape in rectangles:
            the_t = unwrap(shape.getTheT())
            the_z = unwrap(shape.getTheZ())
            t = 0
            z = 0
            if the_t is not None:
                t = the_t
            if the_z is not None:
                z = the_z
            x = int(shape.getX().getValue())
            y = int(shape.getY().getValue())
            text = shape.getTextValue() and shape.getTextValue().getValue() \
                or None

            # build a map of tIndex: (x,y,zMin,zMax)
            if t in time_shape_map:
                xx, yy, min_z, max_z = time_shape_map[t]
                tz_min = min(min_z, z)
                tz_max = max(max_z, z)
                time_shape_map[t] = (x, y, tz_min, tz_max)
            else:
                time_shape_map[t] = (x, y, z, z)

            # get ranges for whole ROI
            if rect_count == 0:
                width = shape.getWidth().getValue()
                height = shape.getHeight().getValue()
                x1 = x
                y1 = y
            rect_count += 1
            if text is not None and text.lower() == roi_text:
                found_labelled_roi = True
        # will return after the first ROI that matches text
        if found_labelled_roi:
            return (int(x1), int(y1), int(width), int(height), time_shape_map)
        else:
            if rect_count > 0:
                roi_count += 1
            rect_count = 0    # try another ROI

    # if we got here without finding an ROI that matched, simply return any
    # ROI we have (last one)
    if roi_count > 0:
        return (int(x1), int(y1), int(width), int(height), time_shape_map)


def get_split_view(conn, image_ids, pixel_ids, merged_indexes, merged_colours,
                   width, height, image_labels, spacer, algorithm, stepping,
                   scalebar, overlay_colour, roi_zoom, max_columns,
                   show_roi_duration, roi_label):
    """
    This method makes a figure of a number of images, arranged in rows with
    each row being the split-view of a single image. The channels are arranged
    left to right, with the combined image added on the right.
    The combined image is rendered according to current settings on the
    server, but it's channels will be turned on/off according to
    @mergedIndexes.

    The figure is returned as a PIL 'Image'

    @ session           session for server access
    @ pixelIds          a list of the Ids for the pixels we want to display
    @ mergedIndexes     list or set of channels in the merged image
    @ mergedColours     index: colour dictionary of channels in the merged
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
    for iid in image_ids:
        rect = get_rectangle(roi_service, iid, roi_label)
        if rect is not None:
            break

    if rect is None:
        log("Found no images with rectangle ROIs")
        return
    x, y, roi_width, roi_height, time_shape_map = rect

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
    font_size = 12
    if width > 500:
        font_size = 48
    elif width > 400:
        font_size = 36
    elif width > 300:
        font_size = 24
    elif width > 200:
        font_size = 16
    font = image_utils.get_font(font_size)
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

    for row, pixels_id in enumerate(pixel_ids):
        log("Rendering row %d" % (row))

        # need to get the roi dimensions from the server
        image_id = image_ids[row]
        roi = get_rectangle(roi_service, image_id, roi_label)
        if roi is None:
            log("No Rectangle ROI found for this image")
            del image_labels[row]    # remove the corresponding labels
            continue
        roi_x, roi_y, roi_width, roi_height, time_shape_map = roi

        pixels = query_service.get("Pixels", pixels_id)
        size_x = pixels.getSizeX().getValue()
        size_y = pixels.getSizeY().getValue()

        # work out if any additional zoom is needed (if the full-sized image
        # is different size from primary image)
        full_size = (size_x, size_y)
        image_zoom = image_utils.get_zoom_factor(full_size, width, height)
        if image_zoom != 1.0:
            log("  Scaling down the full-size image by a factor of %F"
                % image_zoom)

        log("  ROI location (top-left of first frame) x: %d  y: %d  and size"
            " width: %d  height: %d" % (roi_x, roi_y, roi_width, roi_height))
        # get the split pane and full merged image
        roi_split_pane, full_merged_image, top_spacer = get_roi_movie_view(
            re, query_service, pixels, time_shape_map, merged_indexes,
            merged_colours, roi_width, roi_height, roi_zoom, spacer, algorithm,
            stepping, font_size, max_columns, show_roi_duration)

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

    # make a figure to combine all split-view rows
    # each row has 1/2 spacer above and below the panels. Need extra 1/2
    # spacer top and bottom
    canvas_width = left_text_width + width + 2 * spacer + max_split_panel_width
    figure_size = (canvas_width, total_canvas_height + spacer)
    figure_canvas = Image.new("RGB", figure_size, (255, 255, 255))

    row_y = spacer
    for row, image in enumerate(merged_images):
        label_canvas = figUtil.getVerticalLabels(image_labels[row], font,
                                                 text_gap)
        v_offset = (image.size[1] - label_canvas.size[1]) // 2
        image_utils.paste_image(label_canvas, figure_canvas, spacer // 2,
                                row_y+top_spacers[row] + v_offset)
        image_utils.paste_image(
            image, figure_canvas, left_text_width, row_y + top_spacers[row])
        x = left_text_width + width + spacer
        image_utils.paste_image(roi_split_panes[row], figure_canvas, x, row_y)
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

    # the channels in the combined image,
    if "Merged_Channels" in command_args:
        # convert to 0-based
        merged_indexes = [c-1 for c in command_args["Merged_Channels"]]
    else:
        merged_indexes = list(range(size_c))  # show all
    merged_indexes.reverse()

    #  if no colours added, use existing rendering settings.
    merged_colours = {}
    # Actually, nicer to always use existing rendering settings.
    # if "Merged_Colours" in commandArgs:
    #     for i, c in enumerate(commandArgs["Merged_Colours"]):
    #         if c in COLOURS:
    #             mergedColours[i] = COLOURS[c]

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
        if command_args["Scalebar_Colour"] in OVERLAY_COLOURS:
            r, g, b, a = OVERLAY_COLOURS[command_args["Scalebar_Colour"]]
            overlay_colour = (r, g, b)

    roi_zoom = None
    if "Roi_Zoom" in command_args:
        roi_zoom = float(command_args["Roi_Zoom"])
        if roi_zoom == 0:
            roi_zoom = None

    max_columns = None
    if "Max_Columns" in command_args:
        max_columns = command_args["Max_Columns"]

    show_roi_duration = False
    if "Show_ROI_Duration" in command_args:
        show_roi_duration = command_args["Show_ROI_Duration"]

    roi_label = "FigureROI"
    if "Roi_Selection_Label" in command_args:
        roi_label = command_args["Roi_Selection_Label"]

    spacer = (width // 50) + 2

    fig = get_split_view(
        conn, image_ids, pixel_ids, merged_indexes, merged_colours, width,
        height, image_labels, spacer, algorithm, stepping, scalebar,
        overlay_colour, roi_zoom, max_columns, show_roi_duration, roi_label)

    if fig is None:
        log_message = "No figure produced"
        log("\n"+log_message)
        message += log_message
        return None, message
    fig_legend = "\n".join(log_strings)

    format = command_args["Format"]

    figure_name = "movieROIFigure"
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
    namespace = NSCREATED + "/omero/figure_scripts/Movie_ROI_Figure"
    file_annotation, fa_message = script_utils.create_link_file_annotation(
        conn, output, omero_image, output="Movie ROI figure",
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
        'Movie_ROI_Figure.py',
        """Create a figure of movie frames from ROI region of image.""",

        scripts.String(
            "Data_Type", optional=False, grouping="01",
            description="The data you want to work with.", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="02",
            description="List of Image IDs").ofType(rlong(0)),

        scripts.List(
            "Merged_Channels", grouping="03",
            description="A list of channel indexes to display, starting at 1"
            " e.g. 1, 2, 3").ofType(rint(0)),

        scripts.Float(
            "Roi_Zoom", grouping="04", default=1,
            description="How much to zoom the ROI e.g. x 2. If 0 then ROI"
            " panel will zoom to same size as main image"),

        scripts.Int(
            "Max_Columns", grouping="04.1", default=10,
            description="The maximum number of columns in the figure, for"
            " ROI-movie frames.", min=1),

        scripts.Bool(
            "Resize_Images", grouping="05", default=True,
            description="Images are shown full-size by default, but can be"
            " resized below"),

        scripts.Int(
            "Width", grouping="05.1",
            description="Max width of each image panel in pixels", min=1),

        scripts.Int(
            "Height", grouping="05.2",
            description="The max height of each image panel in pixels",
            min=1),

        scripts.String(
            "Image_Labels", grouping="06",
            description="Label images with the Image Name or Datasets or"
            " Tags", values=labels),

        scripts.Bool(
            "Show_ROI_Duration", grouping="06.1",
            description="If true, times shown as duration from first "
            "timepoint of the ROI, otherwise use movie timestamp."),

        scripts.Int(
            "Scalebar", grouping="07",
            description="Scale bar size in microns. Only shown if image has"
            " pixel-size info.", min=1),

        scripts.String(
            "Scalebar_Colour", grouping="07.1",
            description="The color of the scale bar and ROI outline.",
            default='White', values=o_colours),

        scripts.String(
            "Roi_Selection_Label", grouping="08", description=roi_label),

        scripts.String(
            "Algorithm", grouping="09",
            description="Algorithm for projection, if ROI spans several Z"
            " sections.", values=algorithms),

        scripts.String(
            "Figure_Name", grouping="10",
            description="File name of the figure to save.",
            default='movieroi_figure'),

        scripts.String(
            "Format", grouping="10.1",
            description="Format to save figure.", values=formats,
            default='JPEG'),

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
