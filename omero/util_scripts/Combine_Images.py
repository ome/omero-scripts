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

This script takes a number of images (or Z-stacks) and merges them to create
additional C, T, Z dimensions.

@author  Will Moore &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@version 3.0
<small>
(<b>Internal version:</b> $Revision: $Date: $)
</small>
@since 3.0-Beta4.2

"""

import re
from numpy import zeros

import omero
import omero.scripts as scripts
from omero.gateway import BlitzGateway
import omero.constants
from omero.rtypes import rstring, rlong, robject
import omero.util.script_utils as script_utils

COLOURS = script_utils.COLOURS

DEFAULT_T_REGEX = "_T"
DEFAULT_Z_REGEX = "_Z"
DEFAULT_C_REGEX = "_C"

channel_regexes = {
    DEFAULT_C_REGEX: r'_C(?P<C>.+?)(_|$)',
    "C": r'C(?P<C>\w+?)',
    "_c": r'_c(?P<C>\w+?)',
    "_w": r'_w(?P<C>\w+?)',
    "None (single channel)": False}

z_regexes = {
    DEFAULT_Z_REGEX: r'_Z(?P<Z>\d+)',
    "Z": r'Z(?P<Z>\d+)',
    "_z": r'_z(?P<Z>\d+)',
    "None (single z section)": False}

time_regexes = {
    DEFAULT_T_REGEX: r'_T(?P<T>\d+)',
    "T": r'T(?P<T>\d+)',
    "_t": r'_t(?P<T>\d+)',
    "None (single time point)": False}


def get_plane(raw_pixel_store, pixels, the_z, the_c, the_t):
    """
    This method downloads the specified plane of the OMERO image and returns
    it as a numpy array.

    @param session      The OMERO session
    @param imageId      The ID of the image to download
    @param pixels       The pixels object, with pixelsType
    @param imageName    The name of the image to write. If no path, saved in
                        the current directory.
    """

    # get the plane
    pixels_id = pixels.getId().getValue()
    raw_pixel_store.setPixelsId(pixels_id, True)
    return script_utils.download_plane(
        raw_pixel_store, pixels, the_z, the_c, the_t)


def manually_assign_images(parameter_map, image_ids, source_z):

    size_z = source_z
    size_c = 1
    size_t = 1

    dims = []
    dim_sizes = [1, 1, 1]  # at least 1 in each dimension
    dim_map = {"C": "Size_C", "Z": "Size_Z", "T": "Size_T"}
    dimension_params = ["Dimension_1", "Dimension_2", "Dimension_3"]

    for i, d in enumerate(dimension_params):
        if d in parameter_map and len(parameter_map[d]) > 0:
            # First letter of 'Channel' or 'Time' or 'Z'
            dim = parameter_map[d][0]
            dims.append(dim)
            if dim == "Z" and source_z > 1:
                continue
            size_param = dim_map[dim]
            if size_param in parameter_map:
                dim_sizes[i] = parameter_map[size_param]
            else:
                dim_sizes[i] = len(image_ids) // \
                    (dim_sizes[0] * dim_sizes[1] * dim_sizes[2])

    index = 0

    image_map = {}   # map of (z,c,t) : imageId

    for dim3 in range(dim_sizes[2]):
        for dim2 in range(dim_sizes[1]):
            for dim1 in range(dim_sizes[0]):
                if index >= len(image_ids):
                    break
                z, c, t = (0, 0, 0)
                ddd = (dim1, dim2, dim3)
                # bit of a hack, but this somehow does my head in!!
                for i, d in enumerate(dims):
                    if d == "C":
                        c = ddd[i]
                        size_c = max(size_c, c+1)
                    elif d == "T":
                        t = ddd[i]
                        size_t = max(size_t, t+1)
                    elif d == "Z":
                        z = ddd[i]
                        size_z = max(size_z, z+1)
                # handle Z stacks...
                if source_z > 1:
                    for src_z in range(source_z):
                        image_map[(src_z, c, t)] = (image_ids[index], src_z)
                else:
                    image_map[(z, c, t)] = (image_ids[index], 0)
                index += 1

    return (size_z, size_c, size_t, image_map)


def assign_images_by_regex(parameter_map, image_ids, query_service, source_z,
                           id_name_map=None):

    c = None
    regex_channel = channel_regexes[parameter_map["Channel_Name_Pattern"]]
    if regex_channel:
        c = re.compile(regex_channel)

    t = None
    regex_t = time_regexes[parameter_map["Time_Name_Pattern"]]
    if regex_t:
        t = re.compile(regex_t)

    z = None
    regex_z = z_regexes[parameter_map["Z_Name_Pattern"]]
    if regex_z:
        z = re.compile(regex_z)

    # other parameters we need to determine
    size_z = source_z
    size_t = 1
    z_start = None      # could be 0 or 1 ?
    t_start = None

    image_map = {}  # map of (z,c,t) : imageId
    channels = []

    if id_name_map is None:
        id_name_map = get_image_names(query_service, image_ids)

    # assign each (imageId,zPlane) to combined image (z,c,t) by name.
    for iid in image_ids:
        name = id_name_map[iid]
        if t:
            t_search = t.search(name)
        if c:
            c_search = c.search(name)

        if t is None or t_search is None:
            the_t = 0
        else:
            the_t = int(t_search.group('T'))

        if c is None or c_search is None:
            c_name = "0"
        else:
            c_name = c_search.group('C')
        if c_name in channels:
            the_c = channels.index(c_name)
        else:
            the_c = len(channels)
            channels.append(c_name)

        size_t = max(size_t, the_t+1)
        if t_start is None:
            t_start = the_t
        else:
            t_start = min(t_start, the_t)

        # we have T and C now. Need to check if source images are Z stacks
        if source_z > 1:
            z_start = 0
            for src_z in range(source_z):
                image_map[(src_z, the_c, the_t)] = (iid, src_z)
        else:
            if z:
                z_search = z.search(name)

            if z is None or z_search is None:
                the_z = 0
            else:
                the_z = int(z_search.group('Z'))

            size_z = max(size_z, the_z+1)
            if z_start is None:
                z_start = the_z
            else:
                z_start = min(z_start, the_z)

            # every plane comes from z=0
            image_map[(the_z, the_c, the_t)] = (iid, 0)

    # if indexes were 1-based (or higher), need to shift indexes accordingly.
    if t_start > 0 or z_start > 0:
        size_t = size_t-t_start
        size_z = size_z-z_start
        i_map = {}
        for key, value in image_map.items():
            z, c, t = key
            i_map[(z-z_start, c, t-t_start)] = value
    else:
        i_map = image_map

    c_names = {}
    for c, name in enumerate(channels):
        c_names[c] = name
    return (size_z, c_names, size_t, i_map)


def get_image_names(query_service, image_ids):
    id_string = ",".join([str(i) for i in image_ids])
    query_string = "select i from Image i where i.id in (%s)" % id_string
    images = query_service.findAllByQuery(query_string, None)
    id_map = {}
    for i in images:
        iid = i.getId().getValue()
        name = i.getName().getValue()
        id_map[iid] = name
    return id_map


def pick_pixel_sizes(pixel_sizes):
    """
    Process a list of pixel sizes and pick sizes to set for new image.
    If we have different sizes from different images, return None
    """
    pix_size = None
    for px in pixel_sizes:
        if px is None:
            continue
        if pix_size is None:
            pix_size = px
        else:
            # compare - if different, return None
            if (pix_size.getValue() != px.getValue() or
                    pix_size.getUnit() != px.getUnit()):
                return None
    return pix_size


def make_single_image(services, parameter_map, image_ids, dataset, colour_map):
    """
    This takes the images specified by image_ids, sorts them in to Z,C,T
    dimensions according to parameters in the parameter_map, assembles them
    into a new Image, which is saved in dataset.
    """

    if len(image_ids) == 0:
        return

    rendering_engine = services["renderingEngine"]
    query_service = services["queryService"]
    pixels_service = services["pixelsService"]
    raw_pixel_store = services["rawPixelStore"]
    raw_pixel_store_upload = services["rawPixelStoreUpload"]
    update_service = services["updateService"]
    container_service = services["containerService"]

    # Filter images by name if user has specified filter.
    id_name_map = None
    if "Filter_Names" in parameter_map:
        filter_string = parameter_map["Filter_Names"]
        if len(filter_string) > 0:
            id_name_map = get_image_names(query_service, image_ids)
            image_ids = [i for i in image_ids
                         if id_name_map[i].find(filter_string) > -1]

    image_id = image_ids[0]

    # get pixels, with pixelsType, from the first image
    query_string = "select p from Pixels p join fetch p.image i join "\
        "fetch p.pixelsType pt where i.id='%d'" % image_id
    pixels = query_service.findByQuery(query_string, None)
    # use the pixels type object we got from the first image.
    pixels_type = pixels.getPixelsType()

    # combined image will have same X and Y sizes...
    size_x = pixels.getSizeX().getValue()
    size_y = pixels.getSizeY().getValue()
    # if we have a Z stack, use this in new image (don't combine Z)
    source_z = pixels.getSizeZ().getValue()

    # Now we need to find where our planes are coming from.
    # imageMap is a map of destination:source, defined as (newX, newY,
    # newZ):(imageId, z)
    if "Manually_Define_Dimensions" in parameter_map and \
            parameter_map["Manually_Define_Dimensions"]:
        size_z, size_c, size_t, image_map = manually_assign_images(
            parameter_map, image_ids, source_z)
        c_names = {}
    else:
        size_z, c_names, size_t, image_map = assign_images_by_regex(
            parameter_map, image_ids, query_service, source_z, id_name_map)
        size_c = len(c_names)

    if "Channel_Names" in parameter_map:
        for c, name in enumerate(parameter_map["Channel_Names"]):
            c_names[c] = name

    image_name = "combinedImage"
    description = "created from image Ids: %s" % image_ids

    channel_list = range(size_c)
    iid = pixels_service.createImage(size_x, size_y, size_z, size_t,
                                     channel_list, pixels_type, image_name,
                                     description)
    image = container_service.getImages("Image", [iid.getValue()], None)[0]

    pixels_id = image.getPrimaryPixels().getId().getValue()
    raw_pixel_store_upload.setPixelsId(pixels_id, True)

    pixel_sizes = {'x': [], 'y': []}
    for the_c in range(size_c):
        min_value = 0
        max_value = 0
        for the_z in range(size_z):
            for the_t in range(size_t):
                if (the_z, the_c, the_t) in image_map:
                    image_id, plane_z = image_map[(the_z, the_c, the_t)]
                    query_string = "select p from Pixels p join fetch "\
                        "p.image i join fetch p.pixelsType pt where "\
                        "i.id='%d'" % image_id
                    pixels = query_service.findByQuery(query_string,
                                                       None)
                    plane_2d = get_plane(raw_pixel_store, pixels, plane_z,
                                         0, 0)
                    # Note pixels sizes (may be None)
                    pixel_sizes['x'].append(pixels.getPhysicalSizeX())
                    pixel_sizes['y'].append(pixels.getPhysicalSizeY())
                else:
                    plane_2d = zeros((size_y, size_x))
                script_utils.upload_plane(raw_pixel_store_upload,
                                          plane_2d, the_z, the_c, the_t)
                min_value = min(min_value, plane_2d.min())
                max_value = max(max_value, plane_2d.max())
        pixels_service.setChannelGlobalMinMax(pixels_id, the_c,
                                              float(min_value),
                                              float(max_value))
        rgba = COLOURS["White"]
        if the_c in colour_map:
            rgba = colour_map[the_c]
        script_utils.reset_rendering_settings(rendering_engine, pixels_id,
                                              the_c, min_value, max_value,
                                              rgba)

    # rename new channels
    pixels = rendering_engine.getPixels()
    # has channels loaded - (getting Pixels from image doesn't)
    i = 0
    for c in pixels.iterateChannels():
        # c is an instance of omero.model.ChannelI
        if i >= len(c_names):
            break
        lc = c.getLogicalChannel()  # returns omero.model.LogicalChannelI
        lc.setName(rstring(c_names[i]))
        update_service.saveObject(lc)
        i += 1

    # Set pixel sizes if known
    pix_size_x = pick_pixel_sizes(pixel_sizes['x'])
    pix_size_y = pick_pixel_sizes(pixel_sizes['y'])
    if pix_size_x is not None or pix_size_y is not None:
        # reload to avoid OptimisticLockException
        pixels = services["queryService"].get('Pixels',
                                              pixels.getId().getValue())
        if pix_size_x is not None:
            pixels.setPhysicalSizeX(pix_size_x)
        if pix_size_y is not None:
            pixels.setPhysicalSizeY(pix_size_y)
        services["updateService"].saveObject(pixels)

    # put the image in dataset, if specified.
    if dataset and dataset.canLink():
        link = omero.model.DatasetImageLinkI()
        link.parent = omero.model.DatasetI(dataset.getId(), False)
        link.child = omero.model.ImageI(image.getId().getValue(), False)
        update_service.saveAndReturnObject(link)
    else:
        link = None

    return image, link


def combine_images(conn, parameter_map):

    # get the services we need
    services = {}
    services["containerService"] = conn.getContainerService()
    services["renderingEngine"] = conn.createRenderingEngine()
    services["queryService"] = conn.getQueryService()
    services["pixelsService"] = conn.getPixelsService()
    services["rawPixelStore"] = conn.c.sf.createRawPixelsStore()
    services["rawPixelStoreUpload"] = conn.c.sf.createRawPixelsStore()
    services["updateService"] = conn.getUpdateService()
    services["rawFileStore"] = conn.createRawFileStore()

    query_service = services["queryService"]

    colour_map = {}
    if "Channel_Colours" in parameter_map:
        for c, colour in enumerate(parameter_map["Channel_Colours"]):
            if colour in COLOURS:
                colour_map[c] = COLOURS[colour]

    # Get images or datasets
    message = ""
    objects, log_message = script_utils.get_objects(conn, parameter_map)
    message += log_message
    if not objects:
        return None, message

    # get the images IDs from list (in order) or dataset (sorted by name)
    output_images = []
    links = []

    data_type = parameter_map["Data_Type"]
    if data_type == "Image":
        dataset = None
        objects.sort(key=lambda x: (x.getName()))    # Sort images by name
        image_ids = [image.id for image in objects]
        # get dataset from first image
        query_string = "select i from Image i join fetch i.datasetLinks idl"\
            " join fetch idl.parent where i.id in (%s)" % image_ids[0]
        image = query_service.findByQuery(query_string, None)
        if image:
            for link in image.iterateDatasetLinks():
                ds = link.parent
                dataset = conn.getObject("Dataset", ds.getId().getValue())
                break    # only use 1st dataset
        new_img, link = make_single_image(services, parameter_map, image_ids,
                                          dataset, colour_map)
        if new_img:
            output_images.append(new_img)
        if link:
            links.append(link)
    else:
        for dataset in objects:
            images = list(dataset.listChildren())
            if not images:
                continue
            images.sort(key=lambda x: (x.getName()))
            image_ids = [i.getId() for i in images]
            new_img, link = make_single_image(services, parameter_map,
                                              image_ids, dataset, colour_map)
            if new_img:
                output_images.append(new_img)
            if link:
                links.append(link)

    # try and close any stateful services
    for s in services:
        try:
            s.close()
        except Exception:
            pass

    if output_images:
        if len(output_images) > 1:
            message += "%s new images created" % len(output_images)
        else:
            message += "New image created"
        if not links or not len(links) == len(output_images):
            message += " but could not be attached"
    else:
        message += "No image created"
    message += "."

    return output_images, message


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """
    ckeys = list(COLOURS.keys())
    ckeys.sort()
    c_options = [rstring(col) for col in ckeys]
    data_types = [rstring('Dataset'), rstring('Image')]
    first_dim = [rstring('Time'), rstring('Channel'), rstring('Z')]
    extra_dims = [rstring(''), rstring('Time'), rstring('Channel'),
                  rstring('Z')]
    channel_regs = [rstring(r) for r in channel_regexes.keys()]
    z_regs = [rstring(r) for r in z_regexes.keys()]
    t_regs = [rstring(r) for r in time_regexes.keys()]

    client = scripts.client(
        'Combine_Images.py',
        """Combine several single-plane images (or Z-stacks) into one with \
greater Z, C, T dimensions.
See http://help.openmicroscopy.org/scripts.html""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Use all the images in specified 'Datasets' or choose"
            " individual 'Images'.", values=data_types, default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs to "
            "combine.").ofType(rlong(0)),

        scripts.String(
            "Filter_Names", grouping="2.1",
            description="Filter the images by names that contain this value"),

        scripts.Bool(
            "Auto_Define_Dimensions", grouping="3", default=True,
            description="""Choose new dimensions with respect to the order of"
            " the input images. See URL above."""),

        scripts.String(
            "Channel_Name_Pattern", grouping="3.1", default=DEFAULT_C_REGEX,
            values=channel_regs,
            description="""Auto-pick images by channel in the image name"""),

        scripts.String(
            "Z_Name_Pattern", grouping="3.2",
            default=DEFAULT_Z_REGEX, values=z_regs,
            description="""Auto-pick images by Z-index in the image name"""),

        scripts.String(
            "Time_Name_Pattern", grouping="3.3", default=DEFAULT_T_REGEX,
            values=t_regs,
            description="""Auto-pick images by T-index in the image name"""),

        scripts.Bool(
            "Manually_Define_Dimensions", grouping="4", default=False,
            description="""Choose new dimensions with respect to the order of"
            " the input images. See URL above."""),

        scripts.String(
            "Dimension_1", grouping="4.1",
            description="The first Dimension to change", values=first_dim),

        scripts.String(
            "Dimension_2", grouping="4.2", values=extra_dims, default="",
            description="The second Dimension to change. Only specify this if"
            " combining multiple dimensions."),

        scripts.String(
            "Dimension_3", grouping="4.3", values=extra_dims, default="",
            description="The third Dimension to change. Only specify this if"
            " combining multiple dimensions."),

        scripts.Int(
            "Size_Z", grouping="4.4",
            description="Number of Z planes in new image", min=1),

        scripts.Int(
            "Size_C", grouping="4.5",
            description="Number of channels in new image", min=1),

        scripts.Int(
            "Size_T", grouping="4.6",
            description="Number of time-points in new image", min=1),

        scripts.List(
            "Channel_Colours", grouping="7",
            description="List of Colors for channels.", default="White",
            values=c_options).ofType(rstring("")),

        scripts.List(
            "Channel_Names", grouping="8",
            description="List of Names for channels in the new image."),

        version="4.2.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        parameter_map = client.getInputs(unwrap=True)

        conn = BlitzGateway(client_obj=client)

        # create the combined image
        images, message = combine_images(conn, parameter_map)

        client.setOutput("Message", rstring(message))
        if images:
            if len(images) == 1:
                client.setOutput("Combined_Image", robject(images[0]))
            elif len(images) > 1:
                client.setOutput("First_Image", robject(images[0]))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
