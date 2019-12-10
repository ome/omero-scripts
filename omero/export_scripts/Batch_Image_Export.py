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

This script takes a number of images and saves individual image planes in a
zip file for download.

@author Will Moore
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 4.3
@since 3.0-Beta4.3
"""

import omero.scripts as scripts
from omero.gateway import BlitzGateway
import omero.util.script_utils as script_utils
import omero
from omero.rtypes import rstring, rlong, robject
from omero.constants.namespaces import NSCREATED, NSOMETIFF
import os

import glob
import zipfile
from datetime import datetime

try:
    from PIL import Image  # see ticket:2597
except ImportError:
    import Image

# keep track of log strings.
log_strings = []


def log(text):
    """
    Adds the text to a list of logs. Compiled into text file at the end.
    """
    # Handle unicode
    try:
        text = text.encode('utf8')
    except UnicodeEncodeError:
        pass
    log_strings.append(str(text))


def compress(target, base):
    """
    Creates a ZIP recursively from a given base directory.

    @param target:      Name of the zip file we want to write E.g.
                        "folder.zip"
    @param base:        Name of folder that we want to zip up E.g. "folder"
    """
    zip_file = zipfile.ZipFile(target, 'w')
    try:
        files = os.path.join(base, "*")
        for name in glob.glob(files):
            zip_file.write(name, os.path.basename(name), zipfile.ZIP_DEFLATED)

    finally:
        zip_file.close()


def save_plane(image, format, c_name, z_range, project_z, t=0, channel=None,
               greyscale=False, zoom_percent=None, folder_name=None):
    """
    Renders and saves an image to disk.

    @param image:           The image to render
    @param format:          The format to save as
    @param c_name:          The name to use
    @param z_range:         Tuple of (zIndex,) OR (zStart, zStop) for
                            projection
    @param t:               T index
    @param channel:         Active channel index. If None, use current
                            rendering settings
    @param greyscale:       If true, all visible channels will be
                            greyscale
    @param zoom_percent:    Resize image by this percent if specified
    @param folder_name:     Indicate where to save the plane
    """

    original_name = image.getName()
    log("")
    log("save_plane..")
    log("channel: %s" % c_name)
    log("z: %s" % z_range)
    log("t: %s" % t)

    # if channel == None: use current rendering settings
    if channel is not None:
        image.setActiveChannels([channel+1])    # use 1-based Channel indices
        if greyscale:
            image.setGreyscaleRenderingModel()
        else:
            image.setColorRenderingModel()
    if project_z:
        # imageWrapper only supports projection of full Z range (can't
        # specify)
        image.setProjection('intmax')

    # All Z and T indices in this script are 1-based, but this method uses
    # 0-based.
    plane = image.renderImage(z_range[0]-1, t-1)
    if zoom_percent:
        w, h = plane.size
        fraction = (float(zoom_percent) / 100)
        plane = plane.resize((int(w * fraction), int(h * fraction)),
                             Image.ANTIALIAS)

    if format == "PNG":
        img_name = make_image_name(
            original_name, c_name, z_range, t, "png", folder_name)
        log("Saving image: %s" % img_name)
        plane.save(img_name, "PNG")
    elif format == 'TIFF':
        img_name = make_image_name(
            original_name, c_name, z_range, t, "tiff", folder_name)
        log("Saving image: %s" % img_name)
        plane.save(img_name, 'TIFF')
    else:
        img_name = make_image_name(
            original_name, c_name, z_range, t, "jpg", folder_name)
        log("Saving image: %s" % img_name)
        plane.save(img_name)


def make_image_name(original_name, c_name, z_range, t, extension, folder_name):
    """
    Produces the name for the saved image.
    E.g. imported/myImage.dv -> myImage_DAPI_z13_t01.png
    """
    name = os.path.basename(original_name)
    # name = name.rsplit(".",1)[0]  # remove extension
    if len(z_range) == 2:
        z = "%02d-%02d" % (z_range[0], z_range[1])
    else:
        z = "%02d" % z_range[0]
    img_name = "%s_%s_z%s_t%02d.%s" % (name, c_name, z, t, extension)
    if folder_name is not None:
        img_name = os.path.join(folder_name, img_name)
    # check we don't overwrite existing file
    i = 1
    name = img_name[:-(len(extension)+1)]
    while os.path.exists(img_name):
        img_name = "%s_(%d).%s" % (name, i, extension)
        i += 1
    return img_name


def save_as_ome_tiff(conn, image, folder_name=None):
    """
    Saves the image as an ome.tif in the specified folder
    """

    extension = "ome.tif"
    name = os.path.basename(image.getName())
    img_name = "%s.%s" % (name, extension)
    if folder_name is not None:
        img_name = os.path.join(folder_name, img_name)
    # check we don't overwrite existing file
    i = 1
    path_name = img_name[:-(len(extension)+1)]
    while os.path.exists(img_name):
        img_name = "%s_(%d).%s" % (path_name, i, extension)
        i += 1

    log("  Saving file as: %s" % img_name)
    file_size, block_gen = image.exportOmeTiff(bufsize=65536)
    with open(str(img_name), "wb") as f:
        for piece in block_gen:
            f.write(piece)


def save_planes_for_image(conn, image, size_c, split_cs, merged_cs,
                          channel_names=None, z_range=None, t_range=None,
                          greyscale=False, zoom_percent=None, project_z=False,
                          format="PNG", folder_name=None):
    """
    Saves all the required planes for a single image, either as individual
    planes or projection.

    @param renderingEngine:     Rendering Engine, NOT initialised.
    @param queryService:        OMERO query service
    @param imageId:             Image ID
    @param zRange:              Tuple: (zStart, zStop). If None, use default
                                Zindex
    @param tRange:              Tuple: (tStart, tStop). If None, use default
                                Tindex
    @param greyscale:           If true, all visible channels will be
                                greyscale
    @param zoomPercent:         Resize image by this percent if specified.
    @param projectZ:            If true, project over Z range.
    """

    channels = []
    if merged_cs:
        # render merged first with current rendering settings
        channels.append(None)
    if split_cs:
        for i in range(size_c):
            channels.append(i)

    # set up rendering engine with the pixels
    """
    renderingEngine.lookupPixels(pixelsId)
    if not renderingEngine.lookupRenderingDef(pixelsId):
        renderingEngine.resetDefaults()
    if not renderingEngine.lookupRenderingDef(pixelsId):
        raise "Failed to lookup Rendering Def"
    renderingEngine.load()
    """

    if t_range is None:
        # use 1-based indices throughout script
        t_indexes = [image.getDefaultT()+1]
    else:
        if len(t_range) > 1:
            t_indexes = range(t_range[0], t_range[1])
        else:
            t_indexes = [t_range[0]]

    c_name = 'merged'
    for c in channels:
        if c is not None:
            g_scale = greyscale
            if c < len(channel_names):
                c_name = channel_names[c].replace(" ", "_")
            else:
                c_name = "c%02d" % c
        else:
            # if we're rendering 'merged' image - don't want grey!
            g_scale = False
        for t in t_indexes:
            if z_range is None:
                default_z = image.getDefaultZ()+1
                save_plane(image, format, c_name, (default_z,), project_z, t,
                           c, g_scale, zoom_percent, folder_name)
            elif project_z:
                save_plane(image, format, c_name, z_range, project_z, t, c,
                           g_scale, zoom_percent, folder_name)
            else:
                if len(z_range) > 1:
                    for z in range(z_range[0], z_range[1]):
                        save_plane(image, format, c_name, (z,), project_z, t,
                                   c, g_scale, zoom_percent, folder_name)
                else:
                    save_plane(image, format, c_name, z_range, project_z, t,
                               c, g_scale, zoom_percent, folder_name)


def batch_image_export(conn, script_params):

    # for params with default values, we can get the value directly
    split_cs = script_params["Export_Individual_Channels"]
    merged_cs = script_params["Export_Merged_Image"]
    greyscale = script_params["Individual_Channels_Grey"]
    data_type = script_params["Data_Type"]
    folder_name = script_params["Folder_Name"]
    folder_name = os.path.basename(folder_name)
    format = script_params["Format"]
    project_z = "Choose_Z_Section" in script_params and \
        script_params["Choose_Z_Section"] == 'Max projection'

    if (not split_cs) and (not merged_cs):
        log("Not chosen to save Individual Channels OR Merged Image")
        return

    # check if we have these params
    channel_names = []
    if "Channel_Names" in script_params:
        channel_names = script_params["Channel_Names"]
    zoom_percent = None
    if "Zoom" in script_params and script_params["Zoom"] != "100%":
        zoom_percent = int(script_params["Zoom"][:-1])

    # functions used below for each imaage.
    def get_z_range(size_z, script_params):
        z_range = None
        if "Choose_Z_Section" in script_params:
            z_choice = script_params["Choose_Z_Section"]
            # NB: all Z indices in this script are 1-based
            if z_choice == 'ALL Z planes':
                z_range = (1, size_z+1)
            elif "OR_specify_Z_index" in script_params:
                z_index = script_params["OR_specify_Z_index"]
                z_index = min(z_index, size_z)
                z_range = (z_index,)
            elif "OR_specify_Z_start_AND..." in script_params and \
                    "...specify_Z_end" in script_params:
                start = script_params["OR_specify_Z_start_AND..."]
                start = min(start, size_z)
                end = script_params["...specify_Z_end"]
                end = min(end, size_z)
                # in case user got z_start and z_end mixed up
                z_start = min(start, end)
                z_end = max(start, end)
                if z_start == z_end:
                    z_range = (z_start,)
                else:
                    z_range = (z_start, z_end+1)
        return z_range

    def get_t_range(size_t, script_params):
        t_range = None
        if "Choose_T_Section" in script_params:
            t_choice = script_params["Choose_T_Section"]
            # NB: all T indices in this script are 1-based
            if t_choice == 'ALL T planes':
                t_range = (1, size_t+1)
            elif "OR_specify_T_index" in script_params:
                t_index = script_params["OR_specify_T_index"]
                t_index = min(t_index, size_t)
                t_range = (t_index,)
            elif "OR_specify_T_start_AND..." in script_params and \
                    "...specify_T_end" in script_params:
                start = script_params["OR_specify_T_start_AND..."]
                start = min(start, size_t)
                end = script_params["...specify_T_end"]
                end = min(end, size_t)
                # in case user got t_start and t_end mixed up
                t_start = min(start, end)
                t_end = max(start, end)
                if t_start == t_end:
                    t_range = (t_start,)
                else:
                    t_range = (t_start, t_end+1)
        return t_range

    # Get the images or datasets
    message = ""
    objects, log_message = script_utils.get_objects(conn, script_params)
    message += log_message
    if not objects:
        return None, message

    # Attach figure to the first image
    parent = objects[0]

    if data_type == 'Dataset':
        images = []
        for ds in objects:
            images.extend(list(ds.listChildren()))
        if not images:
            message += "No image found in dataset(s)"
            return None, message
    else:
        images = objects

    log("Processing %s images" % len(images))

    # somewhere to put images
    curr_dir = os.getcwd()
    exp_dir = os.path.join(curr_dir, folder_name)
    try:
        os.mkdir(exp_dir)
    except OSError:
        pass
    # max size (default 12kx12k)
    size = conn.getDownloadAsMaxSizeSetting()
    size = int(size)

    ids = []
    # do the saving to disk

    for img in images:
        log("Processing image: ID %s: %s" % (img.id, img.getName()))
        pixels = img.getPrimaryPixels()
        if (pixels.getId() in ids):
            continue
        ids.append(pixels.getId())

        if format == 'OME-TIFF':
            if img._prepareRE().requiresPixelsPyramid():
                log("  ** Can't export a 'Big' image to OME-TIFF. **")
                if len(images) == 1:
                    return None, "Can't export a 'Big' image to %s." % format
                continue
            else:
                save_as_ome_tiff(conn, img, folder_name)
        else:
            size_x = pixels.getSizeX()
            size_y = pixels.getSizeY()
            if size_x*size_y > size:
                msg = "Can't export image over %s pixels. " \
                      "See 'omero.client.download_as.max_size'" % size
                log("  ** %s. **" % msg)
                if len(images) == 1:
                    return None, msg
                continue
            else:
                log("Exporting image as %s: %s" % (format, img.getName()))

            log("\n----------- Saving planes from image: '%s' ------------"
                % img.getName())
            size_c = img.getSizeC()
            size_z = img.getSizeZ()
            size_t = img.getSizeT()
            z_range = get_z_range(size_z, script_params)
            t_range = get_t_range(size_t, script_params)
            log("Using:")
            if z_range is None:
                log("  Z-index: Last-viewed")
            elif len(z_range) == 1:
                log("  Z-index: %d" % z_range[0])
            else:
                log("  Z-range: %s-%s" % (z_range[0], z_range[1]-1))
            if project_z:
                log("  Z-projection: ON")
            if t_range is None:
                log("  T-index: Last-viewed")
            elif len(t_range) == 1:
                log("  T-index: %d" % t_range[0])
            else:
                log("  T-range: %s-%s" % (t_range[0], t_range[1]-1))
            log("  Format: %s" % format)
            if zoom_percent is None:
                log("  Image Zoom: 100%")
            else:
                log("  Image Zoom: %s" % zoom_percent)
            log("  Greyscale: %s" % greyscale)
            log("Channel Rendering Settings:")
            for ch in img.getChannels():
                log("  %s: %d-%d"
                    % (ch.getLabel(), ch.getWindowStart(), ch.getWindowEnd()))

            try:
                save_planes_for_image(conn, img, size_c, split_cs, merged_cs,
                                      channel_names, z_range, t_range,
                                      greyscale, zoom_percent,
                                      project_z=project_z, format=format,
                                      folder_name=folder_name)
            finally:
                # Make sure we close Rendering Engine
                img._re.close()

        # write log for exported images (not needed for ome-tiff)
        name = 'Batch_Image_Export.txt'
        with open(os.path.join(exp_dir, name), 'w') as log_file:
            for s in log_strings:
                log_file.write(s)
                log_file.write("\n")

    if len(os.listdir(exp_dir)) == 0:
        return None, "No files exported. See 'info' for more details"
    # zip everything up (unless we've only got a single ome-tiff)
    if format == 'OME-TIFF' and len(os.listdir(exp_dir)) == 1:
        ometiff_ids = [t.id for t in parent.listAnnotations(ns=NSOMETIFF)]
        conn.deleteObjects("Annotation", ometiff_ids)
        export_file = os.path.join(folder_name, os.listdir(exp_dir)[0])
        namespace = NSOMETIFF
        output_display_name = "OME-TIFF"
        mimetype = 'image/tiff'
    else:
        export_file = "%s.zip" % folder_name
        compress(export_file, folder_name)
        mimetype = 'application/zip'
        output_display_name = "Batch export zip"
        namespace = NSCREATED + "/omero/export_scripts/Batch_Image_Export"

    file_annotation, ann_message = script_utils.create_link_file_annotation(
        conn, export_file, parent, output=output_display_name,
        namespace=namespace, mimetype=mimetype)
    message += ann_message
    return file_annotation, message


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    data_types = [rstring('Dataset'), rstring('Image')]
    formats = [rstring('JPEG'), rstring('PNG'), rstring('TIFF'),
               rstring('OME-TIFF')]
    default_z_option = 'Default-Z (last-viewed)'
    z_choices = [rstring(default_z_option),
                 rstring('ALL Z planes'),
                 # currently ImageWrapper only allows full Z-stack projection
                 rstring('Max projection'),
                 rstring('Other (see below)')]
    default_t_option = 'Default-T (last-viewed)'
    t_choices = [rstring(default_t_option),
                 rstring('ALL T planes'),
                 rstring('Other (see below)')]
    zoom_percents = omero.rtypes.wrap(["25%", "50%", "100%", "200%",
                                      "300%", "400%"])

    client = scripts.client(
        'Batch_Image_Export.py',
        """Save multiple images as JPEG, PNG, TIFF or OME-TIFF \
        in a zip file available for download as a batch export. \
See http://help.openmicroscopy.org/export.html#batch""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        scripts.Bool(
            "Export_Individual_Channels", grouping="3",
            description="Save individual channels as separate images",
            default=True),

        scripts.Bool(
            "Individual_Channels_Grey", grouping="3.1",
            description="If true, all individual channel images will be"
            " grayscale", default=False),

        scripts.List(
            "Channel_Names", grouping="3.2",
            description="Names for saving individual channel images"),

        scripts.Bool(
            "Export_Merged_Image", grouping="4",
            description="Save merged image, using current rendering settings",
            default=True),

        scripts.String(
            "Choose_Z_Section", grouping="5",
            description="Default Z is last viewed Z for each image, OR choose"
            " Z below.", values=z_choices, default=default_z_option),

        scripts.Int(
            "OR_specify_Z_index", grouping="5.1",
            description="Choose a specific Z-index to export", min=1),

        scripts.Int(
            "OR_specify_Z_start_AND...", grouping="5.2",
            description="Choose a specific Z-index to export", min=1),

        scripts.Int(
            "...specify_Z_end", grouping="5.3",
            description="Choose a specific Z-index to export", min=1),

        scripts.String(
            "Choose_T_Section", grouping="6",
            description="Default T is last viewed T for each image, OR choose"
            " T below.", values=t_choices, default=default_t_option),

        scripts.Int(
            "OR_specify_T_index", grouping="6.1",
            description="Choose a specific T-index to export", min=1),

        scripts.Int(
            "OR_specify_T_start_AND...", grouping="6.2",
            description="Choose a specific T-index to export", min=1),

        scripts.Int(
            "...specify_T_end", grouping="6.3",
            description="Choose a specific T-index to export", min=1),

        scripts.String(
            "Zoom", grouping="7", values=zoom_percents,
            description="Zoom (jpeg, png or tiff) before saving with"
            " ANTIALIAS interpolation", default="100%"),

        scripts.String(
            "Format", grouping="8",
            description="Format to save image", values=formats,
            default='JPEG'),

        scripts.String(
            "Folder_Name", grouping="9",
            description="Name of folder (and zip file) to store images",
            default='Batch_Image_Export'),

        version="4.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        start_time = datetime.now()
        script_params = {}

        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)
        for key, value in script_params.items():
            log("%s:%s" % (key, value))

        # call the main script - returns a file annotation wrapper
        file_annotation, message = batch_image_export(conn, script_params)

        stop_time = datetime.now()
        log("Duration: %s" % str(stop_time-start_time))

        # return this fileAnnotation to the client.
        client.setOutput("Message", rstring(message))
        if file_annotation is not None:
            client.setOutput("File_Annotation",
                             robject(file_annotation._obj))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
