#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
-----------------------------------------------------------------------------
  Copyright (C) 2006-2015 University of Dundee. All rights reserved.


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

Make movie takes a number of parameters and creates an movie from the
image with imageId supplied. This movie is uploaded back to the server and
attached to the original Image.

params:
    imageId: this id of the image to create the movie from
    output: The name of the output file, sans the extension
    zStart: The starting z-section to create the movie from
    zEnd:     The final z-section
    tStart:    The starting timepoint to create the movie
    tEnd:    The final timepoint.
    channels: The list of channels to use in the movie(index, from 0)
    splitView: should we show the split view in the movie(not available yet)
    showTime: Show the average time of the aquisition of the channels in the
    frame.
    showPlaneInfo: Show the time and z-section of the current frame.
    fps:    The number of frames per second of the movie
    scalebar: The scale bar size in microns, if <=0 will not show scale bar.
    format:    The format of the movie to be created currently supports
    'video/mpeg', 'video/quicktime'
    overlayColour: The color of the overlays, scale bar, time, as int(RGB)
    fileAnnotation: The fileAnnotation id of the uploaded movie.

@author  Jean-Marie Burel &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:j.burel@dundee.ac.uk">j.burel@dundee.ac.uk</a>
@author Donald MacDonald &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:donald@lifesci.dundee.ac.uk">donald@lifesci.dundee.ac.uk</a>
@version 3.0
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.1

"""

import omero.scripts as scripts
import omero.util.script_utils as script_utils
import omero.util.figureUtil as figureUtil
import omero
import omero.min  # Constants etc.
import os
import sys
import re
import numpy
import omero.util.pixelstypetopython as pixelstypetopython
from struct import unpack
from omero.rtypes import wrap, rstring, rint, rlong, robject
from omero.gateway import BlitzGateway
from omero.constants.namespaces import NSCREATED
from omero.constants.metadata import NSMOVIE

from io import BytesIO
try:
    from types import StringTypes
except ImportError:
    StringTypes = str

try:
    from PIL import Image, ImageDraw  # see ticket:2597
except ImportError:
    import Image
    import ImageDraw  # see ticket:2597

COLOURS = script_utils.COLOURS
COLOURS.update(script_utils.EXTRA_COLOURS)    # name:(rgba) map

MPEG = 'MPEG'
QT = 'Quicktime'
WMV = 'WMV'
MOVIE_NS = NSMOVIE
format_ns_map = {MPEG: MOVIE_NS, QT: MOVIE_NS, WMV: MOVIE_NS}
format_extension_map = {MPEG: "avi", QT: "avi", WMV: "avi"}
format_map = {MPEG: "avi", QT: "avi", WMV: "avi"}
format_mimetypes = {
    MPEG: "video/mpeg",
    QT: "video/quicktime",
    WMV: "video/x-ms-wmv"}
OVERLAYCOLOUR = "#666666"


log_lines = []    # make a log / legend of the figure


def log(text):
    """
    Adds lines of text to the log_lines list, so they can be collected into a
    figure legend.
    """
    log_lines.append(text)


def download_plane(gateway, pixels, pixels_id, x, y, z, c, t):
    """ Retrieves the selected plane """
    raw_plane = gateway.get_plane(pixels_id, z, c, t)
    convert_type = '>' + str(x*y) + pixelstypetopython.toPython(
        pixels.getPixelsType().getValue())
    converted_plane = unpack(convert_type, raw_plane)
    remapped_plane = numpy.array(
        converted_plane, dtype=(pixels.getPixelsType().getValue()))
    remapped_plane.resize(x, y)
    return remapped_plane


def upload_plane(gateway, new_pixels_id, x, y, z, c, t, new_plane):
    """Uploads the specified plane. """
    byte_swapped_plane = new_plane.byteswap()
    converted_plane = byte_swapped_plane.tostring()
    gateway.upload_plane(new_pixels_id, z, c, t, converted_plane)


def mac_osx():
    """ Identifies if the Operating System is Mac or not."""
    if ('darwin' in sys.platform):
        return 1
    else:
        return 0


def build_avi(size_x, size_y, filelist, fps, movie_name, format):
    """ Encodes. """
    program = 'mencoder'
    args = ""
    if (format == WMV):
        args = ' mf://'+filelist + ' -mf w=' + str(size_x) + ':h=' + \
            str(size_y) + ':fps=' + str(fps) + \
            ':type=jpg -ovc lavc -lavcopts vcodec=wmv2 -o %s' % movie_name
    elif (format == QT):
        args = ' mf://'+filelist + ' -mf w=' + str(size_x) + ':h=' + \
            str(size_y) + ':fps='+str(fps) + \
            ':type=png -ovc lavc -lavcopts vcodec=mjpeg:vbitrate=800  -o %s' \
            % movie_name
    else:
        args = ' mf://'+filelist + ' -mf w=' + str(size_x) + ':h=' + \
            str(size_y) + ':fps=' + str(fps) + \
            ':type=jpg -ovc lavc -lavcopts vcodec=mpeg4 -o %s' % movie_name
    log(args)
    os.system(program + args)


def range_from_list(list, index):
    min_value = list[0][index]
    max_value = list[0][index]
    for i in list:
        min_value = min(min_value, i[index])
        max_value = max(max_value, i[index])
    return range(min_value, max_value+1)


def calculate_acquisition_time(conn, pixels_id, c_list, tz_list):
    """ Loads the plane information. """
    query_service = conn.getQueryService()

    t_range = ",".join([str(i) for i in range_from_list(tz_list, 0)])
    z_range = ",".join([str(i) for i in range_from_list(tz_list, 1)])
    c_range = ",".join([str(i) for i in c_list])
    query = "from PlaneInfo as Info where Info.theZ in (%s) and Info.theT" \
        " in (%s) and Info.theC in (%s) and pixels.id='%s'" \
        % (z_range, t_range, c_range, pixels_id)
    info_list = query_service.findAllByQuery(query, None)

    map = {}
    for info in info_list:
        if (info.deltaT is None):
            return None
        key = "z:" + str(info.theZ.getValue()) + "t:" + \
            str(info.theT.getValue())
        if key in map:
            value = map.get(key)
            value = value+info.deltaT.getValue()
            map[key] = value
        else:
            map[key] = info.deltaT.getValue()
    for key in map:
        map[key] = map[key]/len(c_range)
    return map


def add_scalebar(scalebar, image, pixels, command_args):
    """ Adds the scalebar. """
    image_w, image_h = image.size
    draw = ImageDraw.Draw(image)
    if (pixels.getPhysicalSizeX() is None):
        return image
    # FIXME: units ignored for now
    pixel_size_x = pixels.getPhysicalSizeX().getValue()
    if (pixel_size_x <= 0):
        return image
    scale_bar_y = image_h-30
    scale_bar_x = image_w-scalebar/pixel_size_x-20
    scale_bar_text_y = scale_bar_y-15
    scale_bar_x2 = scale_bar_x+scalebar/pixel_size_x
    if (scale_bar_x <= 0 or scale_bar_x2 <= 0 or scale_bar_y <= 0 or
            scale_bar_x2 > image_w):
        return image
    draw.line([(scale_bar_x, scale_bar_y), (scale_bar_x2, scale_bar_y)],
              fill=command_args["Overlay_Colour"])
    draw.text(((scale_bar_x+scale_bar_x2) / 2, scale_bar_text_y),
              str(scalebar), fill=command_args["Overlay_Colour"])
    return image


def add_plane_info(z, t, pixels, image, colour):
    """ Displays the plane information. """
    image_w, image_h = image.size
    draw = ImageDraw.Draw(image)
    text_y = image_h-60
    text_x = 20
    if (text_y <= 0 or text_x > image_w or text_y > image_h):
        return image
    plane_coord = "z:"+str(z+1)+" t:"+str(t+1)
    draw.text((text_x, text_y), plane_coord, fill=colour)
    return image


def add_time_points(time, pixels, image, colour):
    """ Displays the time-points as hrs:mins:secs """
    time = figureUtil.formatTime(time, "HOURS_MINS_SECS")
    image_w, image_h = image.size
    draw = ImageDraw.Draw(image)
    text_y = image_h-45
    text_x = 20
    if (text_y <= 0 or text_x > image_w or text_y > image_h):
        return image
    draw.text((text_x, text_y), str(time), fill=colour)
    return image


def get_rendering_engine(conn, pixels_id, size_c, c_range):
    """ Initializes the rendering engine for the specified pixels set. """
    rendering_engine = conn.createRenderingEngine()
    rendering_engine.lookupPixels(pixels_id)
    if (rendering_engine.lookupRenderingDef(pixels_id) == 0):
        rendering_engine.resetDefaults()
    rendering_engine.lookupRenderingDef(pixels_id)
    rendering_engine.load()
    if len(c_range) == 0:
        for channel in range(size_c):
            rendering_engine.setActive(channel, 1)
    else:
        for channel in range(size_c):
            rendering_engine.setActive(channel, 0)
        for channel in c_range:
            rendering_engine.setActive(channel, 1)
    return rendering_engine


def get_plane(rendering_engine, z, t):
    """ Retrieves the specified XY-plane. """
    plane_def = omero.romio.PlaneDef()
    plane_def.t = t
    plane_def.z = z
    plane_def.x = 0
    plane_def.y = 0
    plane_def.slice = 0
    return rendering_engine.renderAsPackedInt(plane_def)


def in_range(low, high, max):
    """ Determines if the passed values are in the range. """
    if (low < 0 or low > high):
        return 0
    if (high < 0 or high > max):
        return 0
    return 1


def valid_channels(set, size_c):
    """ Determines if the channels are valid """
    if (len(set) == 0):
        return False
    for val in set:
        if isinstance(val, StringTypes):
            val = int(val.split('|')[0].split('$')[0])
        if (val < 0 or val > size_c):
            return False
    return True


def valid_colour_range(colour):
    """ Checks if the passed value is valid. """
    if (colour >= 0 and colour < 0xffffff):
        return 1
    return 0


def build_plane_map_from_ranges(z_range, t_range):
    """ Determines the plane to load. """
    plane_map = []
    for t in t_range:
        for z in z_range:
            plane_map.append([t, z])
    return plane_map


def str_to_range(key):
    split_key = key.split('-')
    if (len(split_key) == 1):
        return range(int(split_key[0]), int(split_key[0])+1)
    return range(int(split_key[0]), int(split_key[1])+1)


def unroll_plane_map(plane_map):
    unrolled_plane_map = []
    for t_set in plane_map:
        z_value = plane_map[t_set]
        for t in str_to_range(t_set):
            for z in str_to_range(z_value.getValue()):
                unrolled_plane_map.append([int(t), int(z)])
    return unrolled_plane_map


def calculate_ranges(size_z, size_t, command_args):
    """ Determines the plane to load. """
    plane_map = {}
    if "Plane_Map" not in command_args:
        z_start = 0
        z_end = size_z-1
        if "Z_Start" in command_args and command_args["Z_Start"] >= 0 and \
                command_args["Z_Start"] < size_z:
            z_start = command_args["Z_Start"]
        if "Z_End" in command_args and command_args["Z_End"] >= 0 and \
                command_args["Z_End"] < size_z and \
                command_args["Z_End"] >= z_start:
            z_end = command_args["Z_End"]+1
        t_start = 0
        t_end = size_t-1
        if "T_Start" in command_args and command_args["T_Start"] >= 0 and \
                command_args["T_Start"] < size_t:
            t_start = command_args["T_Start"]
        if "T_End" in command_args and command_args["T_End"] >= 0 and \
                command_args["T_End"] < size_t and \
                command_args["T_End"] >= t_start:
            t_end = command_args["T_End"]+1
        if (z_end == z_start):
            z_end = z_end+1
        if (t_end == t_start):
            t_end = t_end+1

        z_range = range(z_start, z_end)
        t_range = range(t_start, t_end)
        plane_map = build_plane_map_from_ranges(z_range, t_range)
    else:
        map = command_args["Plane_Map"]
        plane_map = unroll_plane_map(map)
    return plane_map


def reshape_to_fit(image, size_x, size_y, bg=(0, 0, 0)):
    """
    Make the PIL image fit the sizeX and sizeY dimensions by scaling as
    necessary and then padding with background.
    Used for watermark and intro & outro slides.
    """
    image_w, image_h = image.size
    if (image_w, image_h) == (size_x, size_y):
        return image
    # scale
    ratio = min(float(size_x) / image_w, float(size_y) / image_h)
    image = image.resize(map(lambda x: int(x*ratio), image.size),
                         Image.ANTIALIAS)
    # paste
    bg = Image.new("RGBA", (size_x, size_y), (0, 0, 0))     # black bg
    ovlpos = (size_x-image.size[0]) / 2, (size_y-image.size[1]) / 2
    bg.paste(image, ovlpos)
    return bg


def write_intro_end_slides(conn, command_args, orig_file_id, duration, size_x,
                           size_y):
    """
    Uses an original file (jpeg or png) to add frames to the movie.
    Scales and pads to fit size_x, size_y.

    @param orig_file_id:    Original File (png or jpeg) ID
    @param duration:        Duration of intro / end (secs)
    @param size_x:          Width of the exported movie
    @param size_y:          Height of the exported movie
    @return:                List of file names to add to mencoder list
    """

    slide_filenames = []
    fps = command_args["FPS"]
    format = command_args["Format"]

    # get Original File as Image
    slide_file = conn.getObject("OriginalFile", orig_file_id)
    slide_data = b"".join(slide_file.getFileInChunks())
    i = BytesIO(slide_data)
    slide = Image.open(i)
    slide = reshape_to_fit(slide, size_x, size_y)

    # write the file once
    if format == QT:
        filename = 'slide_%s.png' % orig_file_id
        slide.save(filename, "PNG")
    else:
        filename = 'slide_%s.jpg' % orig_file_id
        slide.save(filename, "JPEG")
    # control duration by adding the filename multiple times
    for i in range(duration * fps):
        slide_filenames.append(filename)

    return slide_filenames


def prepare_watermark(conn, command_args, size_x, size_y):
    """
    Read Original File (png or jpeg) to use as watermark,
    scale if needed to fit movie (size_x, size_y) and return

    @return:        PIL Image to use as watermark.
    """

    wm_orig_file = command_args["Watermark"]
    # get Original File as Image
    wm_file = conn.getObject("OriginalFile", wm_orig_file.getId().getValue())
    wm_data = b"".join(wm_file.getFileInChunks())
    i = BytesIO(wm_data)
    wm = Image.open(i)
    wm_w, wm_h = wm.size
    # only resize watermark if too big
    if wm_w > size_x or wm_h > size_y:
        wm = reshape_to_fit(wm, size_x, size_y)
    # wm = wm.convert("L")
    return wm


def paste_watermark(image, watermark):
    """
    Paste the watermark onto the bottom left corner of the image. Return image
    """

    wm_w, wm_h = watermark.size
    w, h = image.size
    wmpos = 0, h - wm_h
    image.paste(watermark, wmpos, watermark)
    return image


def write_movie(command_args, conn):
    """
    Makes the movie.

    @return        Returns the file annotation
    """
    log("Movie created by OMERO")
    log("")

    message = ""

    session = conn.c.sf
    update_service = session.getUpdateService()
    raw_file_store = session.createRawFileStore()

    # Get the images
    images, log_message = script_utils.get_objects(conn, command_args)
    message += log_message
    if not images:
        return None, message
    # Get the first valid image (should be expanded to process the list)
    omero_image = images[0]

    if command_args["RenderingDef_ID"] >= 0:
        rid = command_args["RenderingDef_ID"]
        omero_image._prepareRenderingEngine(rdid=rid)
    pixels = omero_image.getPrimaryPixels()
    pixels_id = pixels.getId()

    size_x = pixels.getSizeX()
    size_y = pixels.getSizeY()
    size_z = pixels.getSizeZ()
    size_c = pixels.getSizeC()
    size_t = pixels.getSizeT()

    if (size_x is None or size_y is None or size_z is None or size_t is None or
            size_c is None):
        return

    if (pixels.getPhysicalSizeX() is None):
        command_args["Scalebar"] = 0

    c_range = range(0, size_c)
    c_windows = None
    c_colours = None
    if "ChannelsExtended" in command_args and \
            valid_channels(command_args["ChannelsExtended"], size_c):
        c_range = []
        c_windows = []
        c_colours = []
        for c in command_args["ChannelsExtended"]:
            m = re.match('^(?P<i>\d+)(\|(?P<ws>\d+)' +
                         '\:(?P<we>\d+))?(\$(?P<c>.+))?$', c)
            if m is not None:
                c_range.append(int(m.group('i'))-1)
                c_windows.append([float(m.group('ws')), float(m.group('we'))])
                c_colours.append(m.group('c'))
    elif "Channels" in command_args and \
            valid_channels(command_args["Channels"], size_c):
        c_range = command_args["Channels"]

    tz_list = calculate_ranges(size_z, size_t, command_args)

    time_map = calculate_acquisition_time(conn, pixels_id, c_range, tz_list)
    if (time_map is None):
        command_args["Show_Time"] = False
    if (time_map is not None):
        if (len(time_map) == 0):
            command_args["Show_Time"] = False

    frame_no = 1
    omero_image.setActiveChannels([x+1 for x in c_range],
                                  c_windows, c_colours)

    overlay_colour = (255, 255, 255)
    if "Overlay_Colour" in command_args:
        r, g, b, a = COLOURS[command_args["Overlay_Colour"]]
        overlay_colour = (r, g, b)

    canvas_colour = tuple(COLOURS[command_args["Canvas_Colour"]][:3])
    mw = command_args["Min_Width"]
    if mw < size_x:
        mw = size_x
    mh = command_args["Min_Height"]
    if mh < size_y:
        mh = size_y
    ovlpos = None
    canvas = None
    if size_x < mw or size_y < mh:
        ovlpos = ((mw-size_x) / 2, (mh-size_y) / 2)
        canvas = Image.new("RGBA", (mw, mh), canvas_colour)

    format = command_args["Format"]
    file_names = []

    # add intro...
    if "Intro_Slide" in command_args and command_args["Intro_Slide"].id:
        intro_duration = command_args["Intro_Duration"]
        intro_file_id = command_args["Intro_Slide"].getId().getValue()
        intro_filenames = write_intro_end_slides(
            conn, command_args, intro_file_id, intro_duration, mw, mh)
        file_names.extend(intro_filenames)

    # prepare watermark
    if "Watermark" in command_args and command_args["Watermark"].id:
        watermark = prepare_watermark(conn, command_args, mw, mh)

    # add movie frames...
    for tz in tz_list:
        t = tz[0]
        z = tz[1]
        image = omero_image.renderImage(z, t)

        if ovlpos is not None:
            image2 = canvas.copy()
            image2.paste(image, ovlpos, image)
            image = image2

        if "Scalebar" in command_args and command_args["Scalebar"]:
            image = add_scalebar(
                command_args["Scalebar"], image, pixels, command_args)
        plane_info = "z:"+str(z)+"t:"+str(t)
        if "Show_Time" in command_args and command_args["Show_Time"]:
            time = time_map[plane_info]
            image = add_time_points(time, pixels, image, overlay_colour)
        if "Show_Plane_Info" in command_args and \
                command_args["Show_Plane_Info"]:
            image = add_plane_info(z, t, pixels, image, overlay_colour)
        if "Watermark" in command_args and command_args["Watermark"].id:
            image = paste_watermark(image, watermark)
        if format == QT:
            filename = str(frame_no) + '.png'
            image.save(filename, "PNG")
        else:
            filename = str(frame_no) + '.jpg'
            image.save(filename, "JPEG")
        file_names.append(filename)
        frame_no += 1

    # add exit frames... "outro"
    # add intro...
    if "Ending_Slide" in command_args and command_args["Ending_Slide"].id:
        end_duration = command_args["Ending_Duration"]
        end_file_id = command_args["Ending_Slide"].id.val
        end_filenames = write_intro_end_slides(
            conn, command_args, end_file_id, end_duration, mw, mh)
        file_names.extend(end_filenames)

    filelist = ",".join(file_names)

    ext = format_map[format]
    movie_name = "Movie"
    if "Movie_Name" in command_args:
        movie_name = command_args["Movie_Name"]
        movie_name = os.path.basename(movie_name)
    if not movie_name.endswith(".%s" % ext):
        movie_name = "%s.%s" % (movie_name, ext)

    # spaces etc in file name cause problems
    movie_name = re.sub("[$&\;|\(\)<>' ]", "", movie_name)
    frames_per_sec = 2
    if "FPS" in command_args:
        frames_per_sec = command_args["FPS"]
    output = "localfile.%s" % ext
    build_avi(mw, mh, filelist, frames_per_sec, output, format)
    mimetype = format_mimetypes[format]
    omero_image._re.close()

    if not os.path.exists(output):
        return None, "Failed to create movie file: %s" % output
    if not command_args["Do_Link"]:
        original_file = script_utils.create_file(
            update_service, output, mimetype, movie_name)
        script_utils.upload_file(raw_file_store, original_file, movie_name)
        return original_file, message

    namespace = NSCREATED + "/omero/export_scripts/Make_Movie"
    file_annotation, ann_message = script_utils.create_link_file_annotation(
        conn, output, omero_image, namespace=namespace,
        mimetype=mimetype, orig_file_path_and_name=movie_name)
    message += ann_message
    return file_annotation._obj, message


def run_script():
    """
    The main entry point of the script. Gets the parameters from the scripting
    service, makes the figure and returns the output to the client.

    def __init__(self, name, optional = False, out = False, description =
                 None, type = None, min = None, max = None, values = None)
    """
    formats = wrap(list(format_map.keys()))    # wrap each key in its rtype
    ckeys = list(COLOURS.keys())
    ckeys.sort()
    c_options = wrap(ckeys)
    data_types = [rstring("Image")]

    client = scripts.client(
        'Make_Movie',
        'MakeMovie creates a movie of the image and attaches it to the'
        ' originating image.',

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose Images via their 'Image' IDs.",
            values=data_types, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="1",
            description="List of Image IDs to process.").ofType(rlong(0)),

        scripts.Long(
            "RenderingDef_ID",
            description="The Rendering Definitions for the Image.",
            default=-1, optional=True, grouping="1"),

        scripts.String(
            "Movie_Name", description="The name of the movie", grouping="2"),

        scripts.Int(
            "Z_Start",
            description="Projection range (if not specified, use defaultZ"
            " only - no projection)", min=0, default=0, grouping="3.1"),

        scripts.Int(
            "Z_End",
            description="Projection range (if not specified or, use defaultZ"
            " only - no projection)", min=0, grouping="3.2"),

        scripts.Int(
            "T_Start",
            description="The first time-point", min=0, default=0,
            grouping="4.1"),

        scripts.Int(
            "T_End",
            description="The last time-point", min=0, grouping="4.2"),

        scripts.List(
            "Channels",
            description="The selected channels",
            grouping="5.1").ofType(rint(0)),

        scripts.List(
            "ChannelsExtended",
            description="The selected channels, with optional range"
            " and color. Takes precedence over Channels.",
            grouping="5.2").ofType(rstring('')),

        scripts.Bool(
            "Show_Time",
            description="If true, display the time.", default=True,
            grouping="6"),

        scripts.Bool(
            "Show_Plane_Info",
            description="If true, display the information about the plane"
            " e.g. Exposure Time.", default=True, grouping="7"),

        scripts.Int(
            "FPS", description="Frames Per Second.", default=2, grouping="8"),

        scripts.Int(
            "Scalebar",
            description="Scale bar size in microns. Only shown if image has"
            " pixel-size info.", min=1, grouping="9"),

        scripts.String(
            "Format", description="Format to save movie", values=formats,
            default=QT, grouping="10"),

        scripts.String(
            "Overlay_Colour",
            description="The color of the scale bar.",
            default='White', values=c_options, grouping="11"),

        scripts.String(
            "Canvas_Colour",
            description="The background color when using minimum size.",
            default='Black', values=c_options),

        scripts.Int(
            "Min_Width",
            description="Minimum width for output movie.", default=-1),

        scripts.Int(
            "Min_Height",
            description="Minimum height for output movie.", default=-1),

        scripts.Map(
            "Plane_Map",
            description="Specify the individual planes (instead of using"
            " T_Start, T_End, Z_Start and Z_End)", grouping="12"),

        scripts.Object(
            "Watermark",
            description="Specify a watermark as an Original File (png or"
            " jpeg)", default=omero.model.OriginalFileI()),

        scripts.Object(
            "Intro_Slide",
            description="Specify an Intro slide as an Original File (png or"
            " jpeg)", default=omero.model.OriginalFileI()),

        scripts.Int(
            "Intro_Duration", default=3,
            description="Duration of Intro in seconds. Default is 3 secs."),

        scripts.Object(
            "Ending_Slide",
            description="Specify a finishing slide as an Original File, "
            "(png or jpeg)", default=omero.model.OriginalFileI()),

        scripts.Int(
            "Ending_Duration", default=3,
            description="Duration of finishing slide in seconds. Default is 3"
            " secs."),

        scripts.Bool(
            "Do_Link",
            description="If true, creates a FileAnnotation with the"
            " OriginalFile holding the movie and links it to the Image.",
            default=True),

        version="4.2.0",
        authors=["Donald MacDonald", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        command_args = client.getInputs(unwrap=True)

        file_annotation, message = write_movie(command_args, conn)

        # return this fileAnnotation to the client.
        client.setOutput("Message", rstring(message))
        if file_annotation is not None:
            client.setOutput("File_Annotation", robject(file_annotation))
    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
