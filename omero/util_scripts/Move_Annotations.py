#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2017 University of Dundee & Open Microscopy Environment.
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Moves Annotations from Images to their parent Wells."""

import omero.scripts as scripts
from omero.gateway import BlitzGateway
from omero.model import WellAnnotationLinkI, WellI, ImageAnnotationLinkI
from omero.rtypes import rstring, rlong
from omero.constants.metadata import NSINSIGHTRATING


ANN_TYPES = {
    'Tag': 'TagAnnotationI',
    'File': 'FileAnnotationI',
    'Comment': 'CommentAnnotationI',
    'Rating': 'LongAnnotationI',
    'Key-Value': 'MapAnnotationI'
}


def log(text):
    """Handles logging statements in a single place."""
    print text


def move_well_annotations(conn, well, ann_type, remove_anns, ns):
    """Move annotations from Images in this Well onto the Well itself."""
    log("Processing Well:", well.id, well.getWellPos())
    iids = [wellSample.getImage().id for wellSample in well.listChildren()]
    log("  Image IDs:", iids)
    if len(iids) == 0:
        return 0

    old_links = list(conn.getAnnotationLinks('Image', iids, ns=ns))

    # Filter by type
    old_links = [l for l in old_links
                 if (ann_type is None
                     or (l.child.__class__.__name__ == ann_type))]

    link_ids = [l.id for l in old_links]

    # Remove duplicate annotations
    links_dict = {}
    for l in old_links:
        ann = l.child
        links_dict[ann.id.val] = l
    old_links = links_dict.values()

    new_links = []
    for l in old_links:
        log("    Annotation:", l.child.id.val, l.child.__class__.__name__)
        link = WellAnnotationLinkI()
        link.parent = WellI(well.id, False)
        link.child = l.child
        new_links.append(link)
    try:
        conn.getUpdateService().saveArray(new_links)
    except Exception, ex:
        log("Failed to create links: ", ex.message)
        return 0

    if remove_anns:
        log("Deleting ImageAnnotation links...", link_ids)
        try:
            for link_id in link_ids:
                to_delete = ImageAnnotationLinkI(link_id, False)
                conn.getUpdateService().deleteObject(to_delete)
        except Exception, ex:
            log("Failed to delete links: ", ex.message)
    return len(new_links)


def move_annotations(conn, script_params):
    """Process script parameters and move annotations as specified."""
    plates = []
    filter_type = None

    dtype = script_params['Data_Type']
    ids = script_params['IDs']
    ann_type = script_params['Annotation_Type']
    if ann_type in ANN_TYPES:
        filter_type = ANN_TYPES[ann_type]
    if ann_type == 'Rating':
        ns = NSINSIGHTRATING
    else:
        ns = script_params.get('Namespace')
    remove_anns = script_params['Remove_Annotations']

    # Get the Plates or Wells
    objects = conn.getObjects(dtype, ids)

    ann_total = 0

    if dtype == 'Well':
        for well in objects:
            ann_count = move_well_annotations(conn, well, filter_type,
                                              remove_anns, ns)
            ann_total += ann_count
    else:
        if dtype == 'Plate':
            plates = list(objects)
        elif dtype == 'Screen':
            for screen in objects:
                plates.extend(list(screen.listChildren()))
        log("Found Plates:", plates)
        for plate in plates:
            for well in plate.listChildren():
                ann_count = move_well_annotations(conn, well, filter_type,
                                                  remove_anns, ns)
                ann_total += ann_count

    return ann_total


def run_script():
    """The main entry point of the script."""
    data_types = [rstring('Screen'), rstring('Plate'), rstring('Well')]

    ann_types = [rstring('All')]
    ann_types.extend([rstring(k) for k in ANN_TYPES.keys()])

    client = scripts.client(
        'Move_Annotations.py',
        """Move Annotations from SPW Images to their parent Wells.""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Plate"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Screen, Plate or Well IDs").ofType(rlong(0)),

        scripts.String(
            "Annotation_Type", grouping="3",
            description="Move All annotations OR just one type of annotation",
            values=ann_types, default='All'),

        scripts.String(
            "Namespace", grouping="4",
            description="Filter annotations by namespace"),

        scripts.Bool(
            "Remove_Annotations", grouping="5",
            description="If false, annotations will remain linked to Images",
            default=True),

        version="5.3.0",
        authors=["William Moore", "OME Team"],
        institutions=["University of Dundee"],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)
        log(script_params)

        # call the main script
        anns_moved = move_annotations(conn, script_params)

        message = ""
        # return 'Message' to client
        if anns_moved is not None:
            message = "Moved %s Annotations" % anns_moved
        else:
            message = "No annotations moved. See info."

        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
