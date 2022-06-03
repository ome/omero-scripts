# coding=utf-8
'''
-----------------------------------------------------------------------------
  Copyright (C) 2014-2020 Glencoe Software, Inc. All rights reserved.


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

Populate metadata from CSV.
'''

import omero
from omero.gateway import BlitzGateway
from omero.rtypes import rstring, rlong
import omero.scripts as scripts
import omero.model

import sys

from omero.util.populate_roi import DownloadingOriginalFileProvider

try:
    # Hopefully this will import
    # https://github.com/ome/omero-metadata/blob/v0.3.1/src/populate_metadata.py
    from omero_metadata.populate import ParsingContext
    OBJECT_TYPES = (
        'Plate',
        'Screen',
        'Dataset',
        'Project',
        'Image',
    )
    DEPRECATED = ""

except ImportError:
    from omero.util.populate_metadata import ParsingContext
    OBJECT_TYPES = (
        'Plate',
        'Screen',
    )
    DEPRECATED = """

    Warning: This script is using an outdated metadata plugin.
    Ask your administrator to install the omero-metadata plugin
    for additional features: https://pypi.org/project/omero-metadata/
    """

# Check if the populate_roi scripts was updated to include functionality for encodings other than utf-8
# If yes, define a function to query all available encodings and set a flag
# If no, add information for the user

if "encoding" in DownloadingOriginalFileProvider.get_original_file_data.__code__.co_varnames:
    import os
    EncSup = True
    AvailEncodings= []
    for i in os.listdir(os.path.split(__import__("encodings").__file__)[0]):
        name=os.path.splitext(i)[0]
        try:
            "".encode(name)
        except:
            pass
        else:
            AvailEncodings.append(name.replace("_","-"))
else:
    encoding = 'utf-8'
    EncSup = False
    DEPRECATED += """
    Warning: This script is using an omero-py version without support for different CSV encodings. 
    All CSV files will be assumed to be utf-8 encoded. If you need support for different encodings,
    ask your administrator to update the installation.
    """

def link_file_ann(conn, object_type, object_id, file_ann_id):
    """Link File Annotation to the Object, if not already linked."""
    file_ann = conn.getObject("Annotation", file_ann_id)
    if file_ann is None:
        sys.stderr.write("Error: File Annotation not found: %s.\n"
                         % file_ann_id)
        sys.exit(1)
    omero_object = get_object(conn, object_type, object_id)
    # Check for existing links
    links = list(conn.getAnnotationLinks(object_type, parent_ids=[object_id],
                                         ann_ids=[file_ann_id]))
    if len(links) == 0:
        omero_object.linkAnnotation(file_ann)


def get_object(conn, object_type, object_id):
    if object_type not in OBJECT_TYPES:
        sys.stderr.write("Error: Invalid object type: %s.\n" % object_type)
        sys.exit(1)
    omero_object = conn.getObject(object_type, int(object_id))
    if omero_object is None:
        sys.stderr.write("Error: %s does not exist.\n" % object_type)
        sys.exit(1)
    return omero_object


def get_original_file(conn, object_type, object_id, file_ann_id=None):
    omero_object = get_object(conn, object_type, object_id)
    file_ann = None

    for ann in omero_object.listAnnotations():
        if isinstance(ann, omero.gateway.FileAnnotationWrapper):
            file_name = ann.getFile().getName()
            # Pick file by Ann ID (or name if ID is None)
            if (file_ann_id is None and file_name.endswith(".csv")) or (
                    ann.getId() == file_ann_id):
                file_ann = ann
    if file_ann is None:
        sys.stderr.write("Error: File does not exist.\n")
        sys.exit(1)

    return file_ann.getFile()._obj


def populate_metadata(client, conn, script_params):
    object_ids = script_params["IDs"]
    object_id = object_ids[0]
    data_type = script_params["Data_Type"]
    encoding = script_params["CSV Encoding"]
    if data_type == "Image":
        try:
            from omero_metadata.populate import ImageWrapper    # noqa: F401
        except ImportError:
            return "Please update omero-metadata to support Image type"
    file_ann_id = None
    if "File_Annotation" in script_params:
        file_ann_id = int(script_params["File_Annotation"])
        link_file_ann(conn, data_type, object_id, file_ann_id)
    original_file = get_original_file(
        conn, data_type, object_id, file_ann_id)
    provider = DownloadingOriginalFileProvider(conn)
    try:
        data_for_preprocessing = provider.get_original_file_data(original_file, encoding=encoding)
    except UnicodeDecodeError as e:
        e.add_note("The CSV file provided could not be decoded using the specified encoding. Please check the encoding and contents of the file!")
        raise
        
    temp_name = data_for_preprocessing.name
    # 5.9.1 returns NamedTempFile where name is a string.
    if isinstance(temp_name, int):
        print("omero-py 5.9.1 DownloadingOriginalFileProvider returns "
              "NamedTempFile. Please Upgrade to omero-py 5.9.1 or later")
        return "Please upgrade omero-py to 5.9.1 or later"
    objecti = getattr(omero.model, data_type + 'I')
    omero_object = objecti(int(object_id), False)
    ctx = ParsingContext(client, omero_object, "")

    try:
        # Old
        with open(temp_name, 'rt', encoding='utf-8-sig') as f1:
            ctx.parse_from_handle(f1)
            ctx.write_to_omero()
    except AttributeError:
        # omero-metadata >= 0.3.0
        with open(temp_name, 'rt', encoding='utf-8-sig') as f1:
            ctx.preprocess_from_handle(f1)
            with open(temp_name, 'rt', encoding='utf-8-sig') as f2:
                ctx.parse_from_handle_stream(f2)
    finally:
        data_for_preprocessing.close()
    return "Table data populated for %s: %s" % (data_type, object_id)


def run_script():

    data_types = [rstring(otype) for otype in OBJECT_TYPES]

    fields = [scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=data_types, default=OBJECT_TYPES[0]),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="Container ID.").ofType(rlong(0)),

        scripts.String(
            "File_Annotation", grouping="3",
            description="File Annotation ID containing metadata to populate. "
            "Note this is not the same as the File ID.")]
    
    # Only display the Encoding field if omero.util.populate_roi has support for different encodings
    if EncSup:
        fields.append( scripts.String(
            "CSV Encoding", grouping="4",
            description="""Encoding of the CSV File provided. Can depend on your system locale 
            as well as the program used to generate the CSV File. E.g. Excel defaults to machine specific
            ANSI encoding during export to CSV (i.e. cp1252 on US machines, iso-8859-1 on german machines ...).""",
            values=AvailEncodings,default="utf-8"))
    
    client = scripts.client(
        'Populate_Metadata.py',
        """
    This script processes a CSV file, using it to
    'populate' an OMERO.table, with one row per Image, Well or ROI.
    The table data can then be displayed in the OMERO clients.
    For full details of the supported CSV format, see
    https://github.com/ome/omero-metadata/#populate
        """ + DEPRECATED,
        *fields,
        authors=["Emil Rozbicki", "OME Team"],
        institutions=["Glencoe Software Inc."],
        contact="ome-users@lists.openmicroscopy.org.uk",
    )

    try:
        # process the list of args above.
        script_params = {}
        for key in client.getInputKeys():
            if client.getInput(key):
                script_params[key] = client.getInput(key, unwrap=True)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        message = populate_metadata(client, conn, script_params)
        client.setOutput("Message", rstring(message))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
