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
from omero.model import ExperimenterI, \
    WellAnnotationLinkI, \
    WellI
from omero.cmd import Delete2
from omero.sys import ParametersI, Filter
from omero.rtypes import rstring, rlong, robject
from omero.constants.metadata import NSINSIGHTRATING


ANN_TYPES = {
    'Tag': 'TagAnnotationI',
    'File': 'FileAnnotationI',
    'Comment': 'CommentAnnotationI',
    'Rating': 'LongAnnotationI',
    'Key-Value': 'MapAnnotationI'
}


def log(text):
    """Handle logging statements in a single place."""
    print(text)


def move_well_annotations(conn, well, ann_type, remove_anns, ns):
    """Move annotations from Images in this Well onto the Well itself."""
    log("Processing Well: %s %s" % (well.id, well.getWellPos()))
    iids = [well_sample.getImage().id for well_sample in well.listChildren()]
    log("  Image IDs: %s" % iids)
    if len(iids) == 0:
        return 0

    # Params to query links. If not Admin, only work with our own links
    params = ParametersI()
    if not conn.isAdmin():
        params.theFilter = Filter()
        params.theFilter.ownerId = rlong(conn.getUserId())

    old_links = list(conn.getAnnotationLinks('Image', iids,
                                             ns=ns, params=params))

    # Filter by type
    old_links = [l for l in old_links
                 if (ann_type is None
                     or (l.child.__class__.__name__ == ann_type))]

    link_ids = [l.id for l in old_links]

    def get_key(ann_link, with_owner=False):
        # We use ann's 'key' to avoid adding duplicate annotations
        # Key includes link owner (allows multiple links with different owners)
        ann = ann_link.child
        return "%s_%s" % (ann_link.details.owner.id.val, ann.id.val)

    links_dict = {}
    # Remove duplicate annotations according to get_key(l)
    for l in old_links:
        links_dict[get_key(l, conn.isAdmin())] = l

    old_links = links_dict.values()

    # Find existing links on Well so we don't try to duplicate them
    existing_well_links = list(conn.getAnnotationLinks('Well', [well.id],
                                                       ns=ns, params=params))
    existing_well_keys = [get_key(l) for l in existing_well_links]

    new_links = []
    for l in old_links:
        if get_key(l) in existing_well_keys:
            continue
        log("    Annotation: %s %s" % (l.child.id.val,
                                       l.child.__class__.__name__))
        link = WellAnnotationLinkI()
        link.parent = WellI(well.id, False)
        link.child = l.child
        # If Admin, the new link Owner is same as old link Owner
        if conn.isAdmin():
            owner_id = l.details.owner.id.val
            link.details.owner = ExperimenterI(owner_id, False)
        new_links.append(link)
    try:
        conn.getUpdateService().saveArray(new_links)
    except Exception as ex:
        log("Failed to create links: %s" % ex.message)
        return 0

    if remove_anns:
        log("Deleting ImageAnnotation links... %s" % link_ids)
        try:
            delete = Delete2(targetObjects={'ImageAnnotationLink': link_ids})
            handle = conn.c.sf.submit(delete)
            conn.c.waitOnCmd(handle, loops=10, ms=500, failonerror=True,
                             failontimeout=False, closehandle=False)
        except Exception as ex:
            log("Failed to delete links: %s" % ex.message)
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
    remove_anns = script_params['Remove_Annotations_From_Images']

    # Get the Plates or Wells
    objects = list(conn.getObjects(dtype, ids))

    ann_total = 0

    if dtype == 'Well':
        for well in objects:
            ann_count = move_well_annotations(conn, well, filter_type,
                                              remove_anns, ns)
            ann_total += ann_count
    else:
        if dtype == 'Plate':
            plates = objects
        elif dtype == 'Screen':
            for screen in objects:
                plates.extend(list(screen.listChildren()))
        log("Found Plates: %s" % [p.id for p in plates])
        for plate in plates:
            for well in plate.listChildren():
                ann_count = move_well_annotations(conn, well, filter_type,
                                                  remove_anns, ns)
                ann_total += ann_count

    return objects, ann_total


def run_script():
    """The main entry point of the script."""
    data_types = [rstring('Screen'), rstring('Plate'), rstring('Well')]

    ann_types = [rstring('All')]
    ann_types.extend([rstring(k) for k in ANN_TYPES.keys()])

    client = scripts.client(
        'Move_Annotations.py',
        """
For Screen/Plate/Well data, this script moves your Annotations from Images to
their parent Wells. If you are an Admin, this will also move annotations that
other users have added, creating links that belong to the same users.
    """,

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The data you want to work with.", values=data_types,
            default="Plate"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Screen, Plate or Well IDs").ofType(rlong(0)),

        scripts.String(
            "Annotation_Type", grouping="3",
            description="Move all annotations OR just one type of annotation",
            values=ann_types, default='All'),

        scripts.String(
            "Namespace", grouping="4",
            description="Filter annotations by namespace"),

        scripts.Bool(
            "Remove_Annotations_From_Images", grouping="5",
            description="If false, annotations will remain linked to Images",
            default=False),

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
        objects, anns_moved = move_annotations(conn, script_params)

        # return 'Message' to client
        message = ""
        if len(objects) == 0:
            message = ("Found no %ss with IDs: %s" %
                       (script_params['Data_Type'], script_params['IDs']))
        else:
            client.setOutput("Target", robject(objects[0]._obj))
        if anns_moved > 0:
            message = "Moved %s Annotations" % anns_moved
        else:
            message = "No annotations moved. See info."

        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
