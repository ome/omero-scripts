#!/usr/bin/env python
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
#   Copyright (C) 2018 University of Dundee. All rights reserved.

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
from omero.rtypes import unwrap, rstring, rlong, robject

DEFAULT_FILE_NAME = "roi_intensities.csv"


def log(data):
    """Handle logging or printing in one place."""
    print data


def get_export_data(conn, script_params, image):
    """Get pixel data for shapes on image and returns list of dicts."""
    log("Image ID %s..." % image.id)
    roi_service = conn.getRoiService()
    all_planes = script_params["Export_All_Planes"]
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

    export_data = []

    for roi in result.rois:
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
                        export_data.append({
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
                        })
    return export_data


COLUMN_NAMES = ["image_id",
                "image_name",
                "roi_id",
                "shape_id",
                "type",
                "text",
                "z",
                "t",
                "channel",
                "points",
                "min",
                "max",
                "sum",
                "mean",
                "std_dev"]


def write_csv(conn, export_data, script_params):
    """Write the list of data to a CSV file & create file annotation."""
    file_name = script_params.get("File_Name", "")
    if len(file_name) == 0:
        file_name = DEFAULT_FILE_NAME
    if not file_name.endswith(".csv"):
        file_name += ".csv"

    csv_rows = [",".join(COLUMN_NAMES)]
    for row in export_data:
        cells = [str(row.get(name)) for name in COLUMN_NAMES]
        csv_rows.append(",".join(cells))

    with open(file_name, 'w') as csv_file:
        csv_file.write("\n".join(csv_rows))

    file_ann = conn.createFileAnnfromLocalFile(file_name,
                                               mimetype="text/csv")
    return file_ann


def link_images(images, file_ann):
    """Link the File Annotation to each image."""
    for i in images:
        if i.canAnnotate():
            i.linkAnnotation(file_ann)


def batch_roi_export(conn, script_params):
    """Main entry point. Get images, process them and return result."""
    images = []

    if script_params['Data_Type'] == "Image":
        images = list(conn.getObjects("Image", script_params['IDs']))
    else:
        for dataset in conn.getObjects("Dataset", script_params['IDs']):
            images.extend(list(dataset.listChildren()))

    log("Processing %s images..." % len(images))
    if len(images) == 0:
        return None

    # build a list of dicts.
    export_data = []
    for image in images:
        export_data.extend(get_export_data(conn, script_params, image))

    # Write to csv
    file_ann = write_csv(conn, export_data, script_params)
    link_images(images, file_ann)
    message = "Exported %s shapes" % len(export_data)
    return file_ann, message


def run_script():
    """The main entry point of the script, as called by the client."""
    data_types = [rstring('Dataset'), rstring('Image')]

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
            "Channels", grouping="3", default=[1L, 2L, 3L, 4L],
            description="Indecies of Channels to measure intensity."
            ).ofType(rlong(0)),

        scripts.Bool(
            "Export_All_Planes", grouping="4",
            description=("Export all Z and T planes for shapes "
                         "where Z and T are not set?"),
            default=False),

        scripts.String(
            "File_Name", grouping="5", default=DEFAULT_FILE_NAME,
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
