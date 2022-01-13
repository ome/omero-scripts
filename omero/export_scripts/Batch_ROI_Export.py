#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
#   Copyright (C) 2018-2020 University of Dundee. All rights reserved.

#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# ------------------------------------------------------------------------------

"""This script exports ROI intensities for selected images."""


import omero.scripts as scripts
from omero.gateway import BlitzGateway
from omero.rtypes import rlong, rint, rstring, robject, unwrap
from omero.model import RectangleI, EllipseI, LineI, PolygonI, PolylineI, \
    MaskI, LabelI, PointI
from math import sqrt, pi
import re

DEFAULT_FILE_NAME = "Batch_ROI_Export.csv"
INSIGHT_POINT_LIST_RE = re.compile(r'points\[([^\]]+)\]')


def log(data):
    """Handle logging or printing in one place."""
    print(data)


def get_export_data(conn, script_params, image, units=None):
    """Get pixel data for shapes on image and returns list of dicts."""
    log("Image ID %s..." % image.id)

    # Get pixel size in SAME units for all images
    pixel_size_x = None
    pixel_size_y = None
    if units is not None:
        pixel_size_x = image.getPixelSizeX(units=units)
        pixel_size_x = pixel_size_x.getValue() if pixel_size_x else None
        pixel_size_y = image.getPixelSizeY(units=units)
        pixel_size_y = pixel_size_y.getValue() if pixel_size_y else None

    roi_service = conn.getRoiService()
    all_planes = script_params["Export_All_Planes"]
    include_points = script_params.get("Include_Points_Coords", False)
    size_c = image.getSizeC()
    # Channels index
    channels = script_params.get("Channels", [1])
    ch_indexes = []
    for ch in channels:
        if ch < 1 or ch > size_c:
            log("Channel index: %s out of range 1 - %s" % (ch, size_c))
        else:
            # User input is 1-based
            ch_indexes.append(ch - 1)

    ch_names = image.getChannelLabels()

    ch_names = [ch_name.replace(",", ".") for ch_name in ch_names]
    image_name = image.getName().replace(",", ".")

    result = roi_service.findByImage(image.getId(), None)

    rois = result.rois
    # Sort by ROI.id (same as in iviewer)
    rois.sort(key=lambda r: r.id.val)
    export_data = []

    well_id = None
    # For SPW data, add Well info...
    if image._obj.wellSamplesLoaded:
        for well_sample in image.copyWellSamples():
            well_id = well_sample.getWell().id.val
            well = conn.getObject("Well", well_id)
            well_row = well.getRow()
            well_column = well.getColumn()
            well_label = well.getWellPos()

    for roi in rois:
        for shape in roi.copyShapes():
            label = unwrap(shape.getTextValue())
            # wrap label in double quotes in case it contains comma
            label = "" if label is None else '"%s"' % label.replace(",", ".")
            shape_type = shape.__class__.__name__.rstrip('I').lower()
            # If shape has no Z or T, we may go through all planes...
            the_z = unwrap(shape.theZ)
            z_indexes = [the_z]
            if the_z is None and all_planes:
                z_indexes = range(image.getSizeZ())
            # Same for T...
            the_t = unwrap(shape.theT)
            t_indexes = [the_t]
            if the_t is None and all_planes:
                t_indexes = range(image.getSizeT())

            # get pixel intensities
            for z in z_indexes:
                for t in t_indexes:
                    if z is None or t is None:
                        stats = None
                    else:
                        stats = roi_service.getShapeStatsRestricted(
                            [shape.id.val], z, t, ch_indexes)
                    for c, ch_index in enumerate(ch_indexes):
                        row_data = {
                            "image_id": image.getId(),
                            "image_name": '"%s"' % image_name,
                            "roi_id": roi.id.val,
                            "shape_id": shape.id.val,
                            "type": shape_type,
                            "text": label,
                            "z": z + 1 if z is not None else "",
                            "t": t + 1 if t is not None else "",
                            "channel": ch_names[ch_index],
                            "points": stats[0].pointsCount[c] if stats else "",
                            "min": stats[0].min[c] if stats else "",
                            "max": stats[0].max[c] if stats else "",
                            "sum": stats[0].sum[c] if stats else "",
                            "mean": stats[0].mean[c] if stats else "",
                            "std_dev": stats[0].stdDev[c] if stats else ""
                        }
                        # For SPW data, add Well info...
                        if well_id is not None:
                            row_data['well_id'] = well_id
                            row_data['well_row'] = well_row
                            row_data['well_column'] = well_column
                            row_data['well_label'] = well_label
                        add_shape_coords(shape, row_data,
                                         pixel_size_x, pixel_size_y,
                                         include_points)
                        export_data.append(row_data)

    return export_data


# well_id, well_row, well_column, well_label inserted if SPW
# Points inserted if exporting shape points string
COLUMN_NAMES = ["image_id",
                "image_name",
                "roi_id",
                "shape_id",
                "type",
                "text",
                "z",
                "t",
                "channel",
                "area",
                "length",
                "points",
                "min",
                "max",
                "sum",
                "mean",
                "std_dev",
                "X",
                "Y",
                "Width",
                "Height",
                "RadiusX",
                "RadiusY",
                "X1",
                "Y1",
                "X2",
                "Y2"]


def add_shape_coords(shape, row_data, pixel_size_x, pixel_size_y,
                     include_points=True):
    """Add shape coordinates and length or area to the row_data dict."""
    if shape.getTextValue():
        row_data['Text'] = shape.getTextValue().getValue()
    if isinstance(shape, (RectangleI, EllipseI, PointI, LabelI, MaskI)):
        row_data['X'] = shape.getX().getValue()
        row_data['Y'] = shape.getY().getValue()
    if isinstance(shape, (RectangleI, MaskI)):
        row_data['Width'] = shape.getWidth().getValue()
        row_data['Height'] = shape.getHeight().getValue()
        row_data['area'] = row_data['Width'] * row_data['Height']
    if isinstance(shape, EllipseI):
        row_data['RadiusX'] = shape.getRadiusX().getValue()
        row_data['RadiusY'] = shape.getRadiusY().getValue()
        row_data['area'] = pi * row_data['RadiusX'] * row_data['RadiusY']
    if isinstance(shape, LineI):
        row_data['X1'] = shape.getX1().getValue()
        row_data['X2'] = shape.getX2().getValue()
        row_data['Y1'] = shape.getY1().getValue()
        row_data['Y2'] = shape.getY2().getValue()
        dx = (row_data['X1'] - row_data['X2'])
        dx = dx if pixel_size_x is None else dx * pixel_size_x
        dy = (row_data['Y1'] - row_data['Y2'])
        dy = dy if pixel_size_y is None else dy * pixel_size_y
        row_data['length'] = sqrt((dx * dx) + (dy * dy))
    if isinstance(shape, (PolygonI, PolylineI)):
        point_list = shape.getPoints().getValue()
        match = INSIGHT_POINT_LIST_RE.search(point_list)
        if match is not None:
            point_list = match.group(1)
        if include_points:
            row_data['Points'] = '"%s"' % point_list
    if isinstance(shape, PolylineI):
        coords = point_list.strip(" ").split(" ")
        try:
            coords = [[float(x.strip(", ")) for x in coord.split(",", 1)]
                      for coord in coords]
        except ValueError:
            log("Invalid Polyline coords: %s" % coords)
        else:
            lengths = []
            for i in range(len(coords)-1):
                dx = (coords[i][0] - coords[i + 1][0])
                dy = (coords[i][1] - coords[i + 1][1])
                dx = dx if pixel_size_x is None else dx * pixel_size_x
                dy = dy if pixel_size_y is None else dy * pixel_size_y
                lengths.append(sqrt((dx * dx) + (dy * dy)))
            row_data['length'] = sum(lengths)
    if isinstance(shape, PolygonI):
        # https://www.mathopenref.com/coordpolygonarea.html
        coords = point_list.strip(" ").split(" ")
        try:
            coords = [[float(x.strip(", ")) for x in coord.split(",", 1)]
                      for coord in coords]
        except ValueError:
            log("Invalid Polygon coords: %s" % coords)
        else:
            total = 0
            for c in range(len(coords)):
                coord = coords[c]
                next_c = coords[(c + 1) % len(coords)]
                total += (coord[0] * next_c[1]) - (next_c[0] * coord[1])
            row_data['area'] = abs(0.5 * total)
    if 'area' in row_data and pixel_size_x and pixel_size_y:
        row_data['area'] = row_data['area'] * pixel_size_x * pixel_size_y


def get_file_name(script_params):
    file_name = script_params.get("File_Name", "")
    if len(file_name) == 0:
        file_name = DEFAULT_FILE_NAME
    if not file_name.endswith(".csv"):
        file_name += ".csv"
    return file_name


def get_csv_header(units_symbol):
    csv_header = ",".join(COLUMN_NAMES)
    if units_symbol is None:
        units_symbol = "pixels"
    csv_header = csv_header.replace(",length,", ",length (%s)," % units_symbol)
    csv_header = csv_header.replace(",area,", ",area (%s)," % units_symbol)
    return csv_header


def link_annotation(objects, file_ann):
    """Link the File Annotation to each object."""
    for o in objects:
        if o.canAnnotate():
            o.linkAnnotation(file_ann)


def get_images_from_plate(plate):
    imgs = []
    for well in plate.listChildren():
        for ws in well.listChildren():
            imgs.append(ws.image())
    return imgs


def batch_roi_export(conn, script_params):
    """Main entry point. Get images, process them and return result."""
    images = []

    dtype = script_params['Data_Type']
    ids = script_params['IDs']
    if dtype in ("Screen", "Plate"):
        COLUMN_NAMES.insert(1, "well_id")
        COLUMN_NAMES.insert(2, "well_row")
        COLUMN_NAMES.insert(3, "well_column")
        COLUMN_NAMES.insert(4, "well_label")
    if script_params.get("Include_Points_Coords", False):
        COLUMN_NAMES.append("Points")
    if dtype == "Image":
        images = list(conn.getObjects("Image", ids))
    elif dtype == "Dataset":
        for dataset in conn.getObjects("Dataset", ids):
            images.extend(list(dataset.listChildren()))
    elif dtype == "Project":
        for project in conn.getObjects("Project", ids):
            for dataset in project.listChildren():
                images.extend(list(dataset.listChildren()))
    elif dtype == "Plate":
        for plate in conn.getObjects("Plate", ids):
            images.extend(get_images_from_plate(plate))
    elif dtype == "Screen":
        for screen in conn.getObjects("Screen", ids):
            for plate in screen.listChildren():
                images.extend(get_images_from_plate(plate))

    log("Processing %s images..." % len(images))
    if len(images) == 0:
        return None

    # Find units for length. If any images have NO pixel size, use 'pixels'
    # since we can't convert
    any_none = False
    for i in images:
        if i.getPixelSizeX() is None:
            any_none = True
    pixel_size_x = images[0].getPixelSizeX(units=True)
    units = None if any_none else pixel_size_x.getUnit()
    units_symbol = None if any_none else pixel_size_x.getSymbol()

    # Create a file so we can write direct to open file
    file_name = get_file_name(script_params)
    csv_header = get_csv_header(units_symbol)

    row_count = 0
    with open(file_name, 'w') as csv_file:
        csv_file.write(csv_header)
        for image in images:
            for row in get_export_data(conn, script_params, image, units):
                cells = [str(row.get(name, "")) for name in COLUMN_NAMES]
                csv_file.write("\n" + ",".join(cells))
                row_count += 1

    file_ann = conn.createFileAnnfromLocalFile(file_name, mimetype="text/csv")

    if dtype == "Image":
        link_annotation(images, file_ann)
    else:
        objects = conn.getObjects(dtype, script_params['IDs'])
        link_annotation(objects, file_ann)
    message = "Exported %s shapes" % row_count
    return file_ann, message


def run_script():
    """The main entry point of the script, as called by the client."""
    data_types = [rstring(s) for s in
                  ['Screen', 'Plate', 'Project', 'Dataset', 'Image']]

    client = scripts.client(
        'Batch_ROI_Export.py',
        """Export ROI intensities for selected Images as a CSV file.""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        scripts.List(
            "Channels", grouping="3", default=[1, 2, 3, 4],
            description="Indices of Channels to measure intensity."
            ).ofType(rint(0)),

        scripts.Bool(
            "Export_All_Planes", grouping="4",
            description=("Export all Z and T planes for shapes "
                         "where Z and T are not set?"),
            default=False),

        scripts.Bool(
            "Include_Points_Coords", grouping="5",
            description=("Export the Points string for Polygons "
                         "and Polylines. Disable this to reduce the "
                         "size of the CSV file when exporting large "
                         "numbers of ROIs"),
            default=True),

        scripts.String(
            "File_Name", grouping="6", default=DEFAULT_FILE_NAME,
            description="Name of the exported CSV file"),

        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)
        log("script_params:")
        log(script_params)

        # call the main script
        result = batch_roi_export(conn, script_params)

        # Return message and file_annotation to client
        if result is None:
            message = "No images found"
        else:
            file_ann, message = result
            if file_ann is not None:
                client.setOutput("File_Annotation", robject(file_ann._obj))

        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
