# !/usr/bin/env python
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
#   Copyright (C) 2022 University of Dundee. All rights reserved.

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

# This script exports the OME.xml from all Images in a Dataset.
# The OME.xml from Images with the same Name is compared and
# any differences are shown in the printed log.

from xml.etree import ElementTree

import omero.scripts as scripts
from omero.gateway import BlitzGateway
from omero.rtypes import rlong, rstring


def get_image_ome_xml(conn, image_id):

    exporter = conn.createExporter()
    exporter.addImage(image_id)
    size = exporter.generateXml()
    xml = exporter.read(0, size)
    exporter.close()
    return xml


def compare_xml(xml1, xml2):
    tree1 = ElementTree.ElementTree(ElementTree.fromstring(xml1))
    tree2 = ElementTree.ElementTree(ElementTree.fromstring(xml2))

    mismatch = False
    for child1, child2 in zip(tree1.iter(), tree2.iter()):
        # Ignore IDs which will be unique
        child1.attrib.pop("ID", None)
        child2.attrib.pop("ID", None)

        print("Checking element", child1)

        if child1.attrib != child2.attrib:
            mismatch = True
            print("-------- ** difference... ** --------------")
            print("CHILD1", child1.attrib)
            print("CHILD2", child2.attrib)
            print("...----------------------")

    return mismatch


def process_data(conn, script_params):
    """Main entry point. Get images, process them and return result."""

    dtype = script_params['Data_Type']
    ids = script_params['IDs']

    comparison_count = 0
    mismatch_count = 0

    if dtype == "Dataset":

        for dataset in conn.getObjects("Dataset", ids):
            xml_by_image_name = {}
            for image in dataset.listChildren():
                xml = get_image_ome_xml(conn, image.id)
                name = image.name
                print("Image...", image.id, image.name)
                if name in xml_by_image_name:
                    print("\n\nChecking images named", name)
                    prev_img = xml_by_image_name[name]["image"]
                    print("Compare image ----------", image.id)
                    print(xml)
                    print("with image -----------", prev_img.id)
                    xml2 = xml_by_image_name[name]["xml"]
                    print(xml2)
                    # assert xml == xml2
                    comparison_count += 1

                    print("xml1 from image", image.id)
                    print("xml2 from image", prev_img.id)
                    mismatch = compare_xml(xml, xml2)
                    if mismatch:
                        mismatch_count += 1
                else:
                    xml_by_image_name[name] = {"xml": xml, "image": image}

    return mismatch_count, comparison_count


def run_script():
    data_types = [rstring(s) for s in
                  ['Dataset']]

    client = scripts.client(
        'Compare_Ome_Xml.py',
        """Compares OME.xml for Images with the same Names in each Dataset""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs or Image IDs").ofType(rlong(0)),
    )

    try:
        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)
        print("script_params:")
        print(script_params)

        # call the main script
        mismatch_count, comparison_count = process_data(conn, script_params)
        message = (f"Compared OME.xml for {comparison_count} images," +
                   f" found {mismatch_count} diffs")

        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
