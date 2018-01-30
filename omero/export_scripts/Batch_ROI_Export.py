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

def get_export_data(conn, script_params, image):
    """Get pixel data for shapes on image and returns list of dicts."""
    roi_service = conn.getRoiService()
    all_planes = script_params["Export_All_Planes"]
    channels = script_params.get("Channels", [1])
    ch_names = image.getChannelLabels()

    result = roi_service.findByImage(image.getId(), None)

    export_data = []

    for roi in result.rois:
        for shape in roi.copyShapes():
            label = unwrap(shape.getTextValue())
            label = "" if label is None else label
            shape_type = shape.__class__.__name__.rstrip('I')
            # If shape has no Z or T, we may go through all planes...
            the_z = unwrap(shape.theZ)
            if the_z is not None:
                z_indexes = [the_z]
            elif all_planes:
                z_indexes = range(image.getSizeZ())
            else:
                z_indexes = [image.getDefaultZ()]
            # Same for T...
            the_t = unwrap(shape.theT)
            if the_t is not None:
                t_indexes = [the_t]
            elif all_planes:
                t_indexes = range(image.getSizeT())
            else:
                t_indexes = [image.getDefaultT()]

            # get pixel intensities
            for z in z_indexes:
                for t in t_indexes:
                    stats = roi_service.getShapeStatsRestricted([shape.id.val],
                                                                z, t,
                                                                channels)
                    for ch_index in channels:
                        c = ch_index - 1    # User input is 1-based
                        export_data.append({
                            "Image ID": image.getId(),
                            "Image Name": image.getName(),
                            "ROI ID": roi.id.val,
                            "Shape ID": shape.id.val,
                            "Shape": shape_type,
                            "Label": label,
                            "Z": z,
                            "T": t,
                            "C": c,
                            "Channel": ch_names[c],
                            "Points": stats[0].pointsCount[c],
                            "Min": stats[0].min[c],
                            "Max": stats[0].max[c],
                            "Sum": stats[0].sum[c],
                            "Mean": stats[0].mean[c],
                            "Std dev": stats[0].stdDev[c]
                        })
    return export_data


COLUMN_NAMES = ["Image ID",
                "Image Name",
                "ROI ID",
                "Shape ID",
                "Shape",
                "Label",
                "Z",
                "T",
                "C",
                "Channel",
                "Points",
                "Min",
                "Max",
                "Sum",
                "Mean",
                "Std dev"]


def write_csv(conn, export_data, script_params):
    """Write the list of data to a csv file & create file annotation."""
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


def batch_roi_export(conn, script_params):
    """Main entry point. Get images, process them and return result."""
    images = []

    if script_params['Data_Type'] == "Image":
        images = list(conn.getObjects("Image", script_params['IDs']))
    else:
        for dataset in conn.getObjects("Dataset", script_params['IDs']):
            images.extend(list(dataset.listChildren()))

    print "Processing %s images..." % len(images)
    if len(images) == 0:
        return None

    # build a list of dicts.
    export_data = []
    for image in images:
        export_data.extend(get_export_data(conn, script_params, image))

    # Write to csv
    file_ann = write_csv(conn, export_data, script_params)
    message = "Exported %s shapes" % len(export_data)
    return file_ann, message


def run_script():
    """The main entry point of the script, as called by the client."""
    data_types = [rstring('Dataset'), rstring('Image')]

    client = scripts.client(
        'Batch_ROI_Export.py',
        """Export ROI intensities for selected Images""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),

        scripts.List(
            "Channels", grouping="3",
            description="Indecies of Channels to measure intensity."
            ).ofType(rlong(0)),

        scripts.Bool(
            "Export_All_Planes", grouping="4",
            description="Export all Z and T planes for shapes without Z / T?",
            default=False),

        scripts.String(
            "File_Name", grouping="5", default=DEFAULT_FILE_NAME,
            description="Name of the exported csv file"),

        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)
        print "script_params", script_params

        # call the main script
        result = batch_roi_export(conn, script_params)

        # Return message and file_annotation to client
        if result is None:
            message = "No images found"
        else:
            file_ann, message = result
            client.setOutput("File_Annotation", robject(file_ann._obj))

        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
