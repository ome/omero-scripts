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

This script displays a bunch of thumbnails from OMERO as a jpg or png, saved
back to the server as a FileAnnotation attached to the parent dataset or
project.

@author  William Moore &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:will@lifesci.dundee.ac.uk">will@lifesci.dundee.ac.uk</a>
@author  Jean-Marie Burel &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:j.burel@dundee.ac.uk">j.burel@dundee.ac.uk</a>
@author Donald MacDonald &nbsp;&nbsp;&nbsp;&nbsp;
<a href="mailto:donald@lifesci.dundee.ac.uk">donald@lifesci.dundee.ac.uk</a>
@since 3.0

"""
from io import BytesIO
import omero.scripts as scripts
from omero.gateway import BlitzGateway
import omero.util.script_utils as script_utils
from omero.rtypes import rint, rlong, rstring, robject
from omero.constants.namespaces import NSCREATED
import os

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import Image
    import ImageDraw  # see ticket:2597
    import ImageFont

from omero.gateway import THISPATH as GATEWAYPATH


WHITE = (255, 255, 255)

log_lines = []    # make a log / legend of the figure


def log(text):
    """
    Adds lines of text to the log_lines list, so they can be collected into a
    figure legend.
    """
    log_lines.append(text)


def paste_image(image, canvas, x, y):
    """
    Pastes the image onto the canvas at the specified coordinates
    Image and canvas are instances of PIL 'Image'

    @param image:       The PIL image to be pasted. Image
    @param canvas:      The PIL image on which to paste. Image
    @param x:           X coordinate (left) to paste
    @param y:           Y coordinate (top) to paste
    """

    x = int(x)
    y = int(y)
    x_right = image.size[0] + x
    y_bottom = image.size[1] + y
    # make a tuple of topLeft-x, topLeft-y, bottomRight-x, bottomRight-y
    pastebox = (x, y, x_right, y_bottom)
    canvas.paste(image, pastebox)


def get_font(fontsize):
    """
    Returns a PIL ImageFont Sans-serif true-type font of the specified size
    or a pre-compiled font of fixed size if the ttf font is not found

    @param fontsize:	The size of the font you want
    @return: 	A PIL Font
    """
    fontsize = int(fontsize)
    font_path = os.path.join(GATEWAYPATH, "pilfonts", "FreeSans.ttf")
    try:
        font = ImageFont.truetype(font_path, fontsize)
    except OSError:
        font = ImageFont.load('%s/pilfonts/B%0.2d.pil' % (GATEWAYPATH, 24))
    return font


def paint_thumbnail_grid(thumbnail_store, length, spacing, pixel_ids,
                         col_count, bg=(255, 255, 255), left_label=None,
                         text_color=(0, 0, 0), fontsize=None, top_label=None):
    """
    Retrieves thumbnails for each pixelId, and places them in a grid,
    with White background.
    Option to add a vertical label to the left of the canvas
    Creates a PIL 'Image' which is returned

    @param thumbnail_store: The omero thumbnail store.
    @param length:          Length of longest thumbnail side, int
    @param spacing:         The spacing between thumbnails and around the
                            edges. int
    @param pixel_ids:       List of pixel IDs. [long]
    @param col_count:       The number of columns. int
    @param bg:              Background colour as (r,g,b).
                            Default is white (255, 255, 255)
    @param left_label:      Optional string to display vertically to the left.
    @param text_color:      The color of the text as (r,g,b).
                            Default is black (0, 0, 0)
    @param fontsize:        Size of the font.
                            Default is calculated based on thumbnail length,
                            int
    @return:                The PIL Image canvas.
    """
    mode = "RGB"
    # work out how many rows and columns are needed for all the images
    img_count = len(pixel_ids)

    row_count = img_count // col_count
    # check that we have enough rows and cols...
    while (col_count * row_count) < img_count:
        row_count += 1

    left_space = top_space = spacing
    min_width = 0

    text_height = 0
    if left_label or top_label:
        # if no images (no rows), need to make at least one row to show label
        if left_label is not None and row_count == 0:
            row_count = 1
        if fontsize is None:
            fontsize = (length // 10) + 5
        font = get_font(fontsize)
        if left_label:
            text_width, text_height = font.getsize(left_label)
            left_space = spacing + text_height + spacing
        if top_label:
            text_width, text_height = font.getsize(top_label)
            top_space = spacing + text_height + spacing
            min_width = left_space + text_width + spacing

    # work out the canvas size needed, and create a white canvas
    cols_needed = min(col_count, img_count)
    v = left_space + cols_needed * (length + spacing)
    canvas_width = int(max(min_width, v))
    canvas_height = int(top_space + row_count * (length + spacing) + spacing)
    mode = "RGB"
    size = (canvas_width, canvas_height)
    canvas = Image.new(mode, size, bg)

    # to write text up the left side, need to write it on horizontal canvas
    # and rotate.
    if left_label:
        label_canvas_width = canvas_height
        label_canvas_height = text_height + spacing
        label_size = (label_canvas_width, label_canvas_height)
        text_canvas = Image.new(mode, label_size, bg)
        draw = ImageDraw.Draw(text_canvas)
        text_width = font.getsize(left_label)[0]
        text_x = (label_canvas_width - text_width) // 2
        draw.text((text_x, spacing), left_label, font=font, fill=text_color)
        vertical_canvas = text_canvas.rotate(90)
        paste_image(vertical_canvas, canvas, 0, 0)
        del draw

    if top_label is not None:
        label_canvas_width = canvas_width
        label_canvas_height = text_height + spacing
        label_size = (label_canvas_width, label_canvas_height)
        text_canvas = Image.new(mode, label_size, bg)
        draw = ImageDraw.Draw(text_canvas)
        draw.text((spacing, spacing), top_label, font=font, fill=text_color)
        paste_image(text_canvas, canvas, left_space, 0)
        del draw

    # loop through the images, getting a thumbnail and placing it on a new row
    # and column
    r = 0
    c = 0
    thumbnail_map = thumbnail_store.getThumbnailByLongestSideSet(rint(length),
                                                                 pixel_ids)
    for pixels_id in pixel_ids:
        if pixels_id in thumbnail_map:
            thumbnail = thumbnail_map[pixels_id]
            # check we have a thumbnail (won't get one if image is invalid)
            if thumbnail:
                # make an "Image" from the string-encoded thumbnail
                thumb_image = Image.open(BytesIO(thumbnail))
                # paste the image onto the canvas at the correct coordinates
                # for the current row and column
                x = c * (length + spacing) + left_space
                y = r * (length + spacing) + top_space
                paste_image(thumb_image, canvas, x, y)

        # increment the column, and if we're at the last column, start a new
        # row
        c = c + 1
        if c == col_count:
            c = 0
            r = r + 1

    return canvas


def sort_images_by_tag(tag_ids, img_tags):

    # prepare list of {'iid': imgId, 'tagKey' : stringToSort }
    # E.g. if tag_ids = [5, 3, 9], we map to 'a', 'b', 'c',
    # so an Image with tags 3 & 9 will have 'tagKey': "bc"
    letters = 'abcdefghijklmnopqrstuvwxyz'
    # assume we have less than 26 tags!
    sorted_images = []
    for iid, tag_id_list in img_tags.items():
        ordered_indexes = []
        ordered_tags = []
        for i, tid in enumerate(tag_ids):
            if tid in tag_id_list:
                ordered_indexes.append(letters[i])
                ordered_tags.append(tid)
        if len(ordered_indexes) > 0:
            tag_key = "".join(ordered_indexes)
        else:
            tag_key = "z"
        sorted_images.append({
            'iid': iid,
            'tagKey': tag_key,
            'tagIds': ordered_tags})

    sorted_images.sort(key=lambda x: x['tagKey'])

    # clean up our 'z' sorting hack above.
    for i in sorted_images:
        if i['tagKey'] == "z":
            i['tagKey'] = ""

    return sorted_images


def paint_dataset_canvas(conn, images, title, tag_ids=None,
                         show_untagged=False, col_count=10, length=100):
    """
        Paints and returns a canvas of thumbnails from images, laid out in a
        set number of columns.
        Title and date-range of the images is printed above the thumbnails,
        to the left and right, respectively.

        @param conn:        Blitz connection
        @param image:       Image IDs
        @param title:       title to display at top of figure. String
        @param tag_ids:     Optional to sort thumbnails by tag. [long]
        @param col_count:    Max number of columns to lay out thumbnails
        @param length:      Length of longest side of thumbnails
    """

    mode = "RGB"
    fig_canvas = None
    spacing = length//40 + 2

    thumbnail_store = conn.createThumbnailStore()
    metadata_service = conn.getMetadataService()

    if len(images) == 0:
        return None
    timestamp_min = images[0].getDate()   # datetime
    timestamp_max = timestamp_min

    ds_image_ids = []
    image_pixel_map = {}
    image_names = {}

    # sort the images by name
    images.sort(key=lambda x: (x.getName().lower()))

    for image in images:
        image_id = image.getId()
        pixel_id = image.getPrimaryPixels().getId()
        name = image.getName()
        ds_image_ids.append(image_id)        # make a list of image-IDs
        # and a map of image-ID: pixel-ID
        image_pixel_map[image_id] = pixel_id
        image_names[image_id] = name
        timestamp_min = min(timestamp_min, image.getDate())
        timestamp_max = max(timestamp_max, image.getDate())

    # set-up fonts
    fontsize = length/7 + 5
    font = get_font(fontsize)
    text_height = font.getsize("Textq")[1]
    top_spacer = spacing + text_height
    left_spacer = spacing + text_height

    tag_panes = []
    max_width = 0
    total_height = top_spacer

    # if we have a list of tags, then sort images by tag
    if tag_ids:
        # Cast to int since List can be any type
        tag_ids = [int(tag_id) for tag_id in tag_ids]
        log(" Sorting images by tags: %s" % tag_ids)
        tag_names = {}
        tagged_images = {}    # a map of tagId: list-of-image-Ids
        img_tags = {}        # a map of imgId: list-of-tagIds
        for tag_id in tag_ids:
            tagged_images[tag_id] = []

        # look for images that have a tag
        types = ["ome.model.annotations.TagAnnotation"]
        annotations = metadata_service.loadAnnotations(
            "Image", ds_image_ids, types, None, None)
        # filter images by annotation...
        for image_id, tags in annotations.items():
            img_tag_ids = []
            for tag in tags:
                tag_id = tag.getId().getValue()
                # make a dict of tag-names
                tag_names[tag_id] = tag.getTextValue().getValue()
                img_tag_ids.append(tag_id)
            img_tags[image_id] = img_tag_ids

        # get a sorted list of {'iid': iid, 'tagKey': tagKey,
        # 'tagIds':orderedTags}
        sorted_thumbs = sort_images_by_tag(tag_ids, img_tags)

        if not show_untagged:
            sorted_thumbs = [t for t in sorted_thumbs if len(t['tagIds']) > 0]

        # Need to group sets of thumbnails by FIRST tag.
        toptag_sets = []
        grouped_pixel_ids = []
        show_subset_labels = False
        current_tag_str = None
        for i, img in enumerate(sorted_thumbs):
            tag_ids = img['tagIds']
            if len(tag_ids) == 0:
                tag_string = "Not Tagged"
            else:
                tag_string = tag_names[tag_ids[0]]
            if tag_string == current_tag_str or current_tag_str is None:
                # only show subset labels (later) if there are more than 1
                # subset
                if (len(tag_ids) > 1):
                    show_subset_labels = True
                grouped_pixel_ids.append({
                    'pid': image_pixel_map[img['iid']],
                    'tagIds': tag_ids})
            else:
                toptag_sets.append({
                    'tagText': current_tag_str,
                    'pixelIds': grouped_pixel_ids,
                    'showSubsetLabels': show_subset_labels})
                show_subset_labels = len(tag_ids) > 1
                grouped_pixel_ids = [{
                    'pid': image_pixel_map[img['iid']],
                    'tagIds': tag_ids}]
            current_tag_str = tag_string
        toptag_sets.append({
            'tagText': current_tag_str,
            'pixelIds': grouped_pixel_ids,
            'showSubsetLabels': show_subset_labels})

        # Find the indent we need
        max_tag_name_width = max([font.getsize(ts['tagText'])[0]
                                 for ts in toptag_sets])
        if show_untagged:
            max_tag_name_width = max(max_tag_name_width,
                                     font.getsize("Not Tagged")[0])

        tag_sub_panes = []

        # make a canvas for each tag combination
        def make_tagset_canvas(tag_string, tagset_pix_ids, show_subset_labels):
            log(" Tagset: %s  (contains %d images)"
                % (tag_string, len(tagset_pix_ids)))
            if not show_subset_labels:
                tag_string = None
            sub_canvas = paint_thumbnail_grid(
                thumbnail_store, length,
                spacing, tagset_pix_ids, col_count, top_label=tag_string)
            tag_sub_panes.append(sub_canvas)

        for toptag_set in toptag_sets:
            tag_text = toptag_set['tagText']
            show_subset_labels = toptag_set['showSubsetLabels']
            image_data = toptag_set['pixelIds']
            # loop through all thumbs under TAG, grouping into subsets.
            tagset_pix_ids = []
            current_tag_str = None
            for i, img in enumerate(image_data):
                tag_ids = img['tagIds']
                pid = img['pid']
                tag_string = ", ".join([tag_names[tid] for tid in tag_ids])
                if tag_string == "":
                    tag_string = "Not Tagged"
                # Keep grouping thumbs under similar tag set (if not on the
                # last loop)
                if tag_string == current_tag_str or current_tag_str is None:
                    tagset_pix_ids.append(pid)
                else:
                    # Process thumbs added so far
                    make_tagset_canvas(current_tag_str, tagset_pix_ids,
                                       show_subset_labels)
                    # reset for next tagset
                    tagset_pix_ids = [pid]
                current_tag_str = tag_string

            make_tagset_canvas(current_tag_str, tagset_pix_ids,
                               show_subset_labels)

            max_width = max([c.size[0] for c in tag_sub_panes])
            total_height = sum([c.size[1] for c in tag_sub_panes])

            # paste them into a single canvas for each Tag

            left_spacer = 3*spacing + max_tag_name_width
            # Draw vertical line to right
            size = (left_spacer + max_width, total_height)
            tag_canvas = Image.new(mode, size, WHITE)
            p_x = left_spacer
            p_y = 0
            for pane in tag_sub_panes:
                paste_image(pane, tag_canvas, p_x, p_y)
                p_y += pane.size[1]
            if tag_text is not None:
                draw = ImageDraw.Draw(tag_canvas)
                tt_w, tt_h = font.getsize(tag_text)
                h_offset = (total_height - tt_h)/2
                draw.text((spacing, h_offset), tag_text, font=font,
                          fill=(50, 50, 50))
            # draw vertical line
            draw.line((left_spacer-spacing, 0, left_spacer - spacing,
                       total_height), fill=(0, 0, 0))
            tag_panes.append(tag_canvas)
            tag_sub_panes = []
    else:
        left_spacer = spacing
        pixel_ids = []
        for image_id in ds_image_ids:
            log("  Name: %s  ID: %d" % (image_names[image_id], image_id))
            pixel_ids.append(image_pixel_map[image_id])
        fig_canvas = paint_thumbnail_grid(
            thumbnail_store, length, spacing, pixel_ids, col_count)
        tag_panes.append(fig_canvas)

    # paste them into a single canvas
    tagset_spacer = length / 3
    max_width = max([c.size[0] for c in tag_panes])
    total_height = total_height + sum([c.size[1]+tagset_spacer
                                      for c in tag_panes]) - tagset_spacer
    size = (int(max_width), int(total_height))
    full_canvas = Image.new(mode, size, WHITE)
    p_x = 0
    p_y = top_spacer
    for pane in tag_panes:
        paste_image(pane, full_canvas, p_x, p_y)
        p_y += pane.size[1] + tagset_spacer

    # create dates for the image timestamps. If dates are not the same, show
    # first - last.
    # firstdate = timestampMin
    # lastdate = timestampMax
    # figureDate = str(firstdate)
    # if firstdate != lastdate:
    #     figureDate = "%s - %s" % (firstdate, lastdate)

    draw = ImageDraw.Draw(full_canvas)
    # dateWidth = draw.textsize(figureDate, font=font)[0]
    # titleWidth = draw.textsize(title, font=font)[0]
    # dateX = fullCanvas.size[0] - spacing - dateWidth
    # title
    draw.text((left_spacer, spacing), title, font=font, fill=(0, 0, 0))
    # Don't show dates: see
    # https://github.com/openmicroscopy/openmicroscopy/pull/1002
    # if (leftSpacer+titleWidth) < dateX:
    # if there's enough space...
    #     draw.text((dateX, dateY), figureDate, font=font, fill=(0,0,0))
    # add date

    return full_canvas


def make_thumbnail_figure(conn, script_params):
    """
    Makes the figure using the parameters in @script_params, attaches the
    figure to the parent Project/Dataset, and returns the file-annotation ID

    @ returns       Returns the id of the originalFileLink child. (ID object,
                    not value)
    """

    log("Thumbnail figure created by OMERO")
    log("")

    message = ""

    # Get the objects (images or datasets)
    objects, log_message = script_utils.get_objects(conn, script_params)
    message += log_message
    if not objects:
        return None, message

    # Get parent
    parent = None
    if "Parent_ID" in script_params and len(script_params["IDs"]) > 1:
        if script_params["Data_Type"] == "Image":
            parent = conn.getObject("Dataset", script_params["Parent_ID"])
        else:
            parent = conn.getObject("Project", script_params["Parent_ID"])

    if parent is None:
        parent = objects[0]  # Attach figure to the first object

    parent_class = parent.OMERO_CLASS
    log("Figure will be linked to %s%s: %s"
        % (parent_class[0].lower(), parent_class[1:], parent.getName()))

    tag_ids = []
    if "Tag_IDs" in script_params:
        tag_ids = script_params['Tag_IDs']
    if len(tag_ids) == 0:
        tag_ids = None

    show_untagged = False
    if (tag_ids):
        show_untagged = script_params["Show_Untagged_Images"]

    thumb_size = script_params["Thumbnail_Size"]
    max_columns = script_params["Max_Columns"]

    fig_height = 0
    fig_width = 0
    ds_canvases = []

    if script_params["Data_Type"] == "Dataset":
        for dataset in objects:
            log("Dataset: %s     ID: %d"
                % (dataset.getName(), dataset.getId()))
            images = list(dataset.listChildren())
            title = dataset.getName()
            try:
                title = title.decode('utf8')
            except AttributeError:
                pass    # python 3
            ds_canvas = paint_dataset_canvas(
                conn, images, title, tag_ids, show_untagged,
                length=thumb_size, col_count=max_columns)
            if ds_canvas is None:
                continue
            ds_canvases.append(ds_canvas)
            fig_height += ds_canvas.size[1]
            fig_width = max(fig_width, ds_canvas.size[0])
    else:
        image_canvas = paint_dataset_canvas(
            conn, objects, "", tag_ids,
            show_untagged, length=thumb_size, col_count=max_columns)
        ds_canvases.append(image_canvas)
        fig_height += image_canvas.size[1]
        fig_width = max(fig_width, image_canvas.size[0])

    if len(ds_canvases) == 0:
        message += "No figure created"
        return None, message

    figure = Image.new("RGB", (fig_width, fig_height), WHITE)
    y = 0
    for ds in ds_canvases:
        paste_image(ds, figure, 0, y)
        y += ds.size[1]

    log("")
    fig_legend = "\n".join(log_lines)

    format = script_params["Format"]
    figure_name = script_params["Figure_Name"]
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

    namespace = NSCREATED + "/omero/figure_scripts/Thumbnail_Figure"
    file_annotation, fa_message = script_utils.create_link_file_annotation(
        conn, output, parent, output="Thumbnail figure", mimetype=mimetype,
        description=fig_legend, namespace=namespace,
        orig_file_path_and_name=figure_name)
    message += fa_message

    return file_annotation, message


def run_script():
    """
    The main entry point of the script. Gets the parameters from the scripting
    service, makes the figure and returns the output to the client.
    def __init__(self, name, optional = False, out = False, description =
    None, type = None, min = None, max = None, values = None)
    """

    formats = [rstring('JPEG'), rstring('PNG'), rstring('TIFF')]
    data_types = [rstring('Dataset'), rstring('Image')]

    client = scripts.client(
        'Thumbnail_Figure.py',
        """Export a figure of thumbnails, optionally sorted by tag.
See http://help.openmicroscopy.org/publish.html#figures""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.",
            values=data_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image"
            " IDs").ofType(rlong(0)),

        scripts.List(
            "Tag_IDs", grouping="3",
            description="Group thumbnails by these tags."),

        scripts.Bool(
            "Show_Untagged_Images", grouping="3.1", default=False,
            description="If true (and you're sorting by tagIds) also"
            " show images without the specified tags"),

        scripts.Long(
            "Parent_ID", grouping="4",
            description="Attach figure to this Project (if datasetIds"
            " above) or Dataset if imageIds. If not specified, attach"
            " figure to first dataset or image."),
        # this will be ignored if only a single ID in list - attach to
        # that object instead.

        scripts.Int(
            "Thumbnail_Size", grouping="5", min=10, max=250, default=100,
            description="The dimension of each thumbnail. Default is 100"),

        scripts.Int(
            "Max_Columns", grouping="5.1", min=1, default=10,
            description="The max number of thumbnail columns. Default is 10"),

        scripts.String(
            "Format", grouping="6",
            description="Format to save image.", values=formats,
            default="JPEG"),

        scripts.String(
            "Figure_Name", grouping="6.1", default='Thumbnail_Figure',
            description="File name of figure to create"),

        version="4.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
        )

    try:
        conn = BlitzGateway(client_obj=client)

        command_args = client.getInputs(unwrap=True)

        # Makes the figure and attaches it to Project/Dataset. Returns
        # FileAnnotationI object
        file_annotation, message = make_thumbnail_figure(conn, command_args)

        # Return message and file annotation (if applicable) to the client
        client.setOutput("Message", rstring(message))
        if file_annotation is not None:
            client.setOutput("File_Annotation", robject(file_annotation._obj))
    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
