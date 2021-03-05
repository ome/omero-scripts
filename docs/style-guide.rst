Guidelines for writing OMERO.scripts
====================================

These guidelines for writing OMERO scripts are designed to improve the
interaction of the scripts with OMERO clients so that they can:

-  generate a nice, usable UI for the script
-  handle the script results appropriately

.. figure:: /images/omero-scripting-movie-roi.png
  :align: center
  :alt: Scripting movie ROI figure

  Movie ROI figure script UI
      
If you want instructions on how to get started with OMERO scripts, see
the link above or the :doc:`user-guide`.

Most of the points below are implemented in the example :source:`Edit_Descriptions.py <examples/ScriptingService/Edit_Descriptions.py>`.

Script naming and file path
---------------------------

-  Script Name should be in the form 'Script\_Name.py'. The OMERO.web and OMERO.insight
   clients will replace underscores with spaces in the script selection menu.
-  File paths - The clients will use the parent folder to build a
   scripts menu, capitalising and removing underscores. For example, a script
   uploaded from /omero/export\_scripts/Batch\_Image\_Export.py will be
   displayed in the clients under "Export Scripts".
-  Script Descriptions should give a brief summary of what
   the script does. If a longer description or instructions for using
   the script are desired, it is suggested that a URL is included. The
   description will be displayed in the script UI and any URLs will be
   'clickable' to launch a browser.

Parameters
----------

-  Parameter Names should be in the form 'Parameter\_Name'.
   Underscores will be replaced by spaces in the UI generated in
   the clients.
-  Where applicable, parameters should be supplied with a list of
   options. For example:

   ::

       scripts.String("Algorithm", values=[rstring('Maximum_Intensity'),rstring('Mean_Intensity')] )

-  Where possible, parameters should be supplied with default values.
   These will be used to populate fields in the clients script UI
   and will be used by default when launching the script from the
   command line.

   ::

       scripts.String("Folder_Name", description="Name of folder to store images", default='Batch_Image_Export'),

-  Where applicable, parameters should have min and max values, e.g.:

   ::

       scripts.Int("Size_Z", description="Number of Z planes in new image", min=1),

Parameter grouping / ordering
-----------------------------

Parameters are not ordered by default. They can be ordered and grouped
by adding a "grouping" attribute, which is a string, where 'groups' are
separated by a '.' e.g. "01.A". Parameters will be ordered by the
lexographic sorting of this string and groups indicated in the UI. In
most cases this will simply be a common indentation of parameters in the
same group. In addition, if the 'parent' parameter of a group is a
boolean, then un-checking the check-box in the UI will disable the child
parameters. For example a UI generated from the code below will have a
'Show Scalebar' option. If this is un-checked, then the 'Size' and 'Colour'
parameters will be disabled and will not be passed to the script.

::

    scripts.Bool("Show_Scalebar", grouping="10", default=True),
    scripts.Int("Scalebar_Size", grouping="10.1"),
    scripts.String("Scalebar_Colour", grouping="10.2"),

Pick selected Images, Datasets or Projects from OMERO clients
-------------------------------------------------------------

Both OMERO.insight and OMERO.web recognize and populate a pair of
fields named 'Data\_Type' (string) and 'IDs' (Long list) with the objects 
currently selected in the client UI when the script is launched. You should 
specify the 'Data\_Type' options that your script should accept.
For example:

::

    dataTypes = [rstring('Dataset'),rstring('Image')]

    client = scripts.client('Thumbnail_Figure.py', "Export a figure of thumbnails",
        scripts.String("Data_Type", optional=False, grouping="01", values=dataTypes, default="Dataset"),
        scripts.List("IDs", optional=False, grouping="02").ofType(rlong(0))
        )

Script outputs
--------------

-  Scripts may return a short message to report success or failure. This
   should use the key: 'Message' in the output map. This will be
   displayed in clients when the script completes.

   ::

       client.setOutput("Message", rstring("Script generated new Image"))

-  Scripts that generate an Image should return the omero.model.ImageI object.
   The clients will provide a link to view the Image. The key that is used
   ("Image" in this example) is not important for this to work, but
   'image' should be an omero.model.ImageI object.

   ::

           client.setOutput("Image",robject(image))

-  Scripts that generate a File Annotation or Original File should
   return these objects. The clients will give users the option of
   downloading the File, and may also allow viewing of the file if it is
   of a suitable type. This should be set as the mimetype of the File
   Annotation (e.g. 'plain/text', 'image/jpeg', etc.). In this example,
   fileAnnotation should be an omero.model.FileAnnotationI object, but
   could also be an omero.model.OriginalFileI object.

   ::

           client.setOutput("File_Annotation",robject(fileAnnotation))

-  Scripts that generate a URL link should return the omero.rtypes.rmap,
   with the following keys: "type": "URL", "href": "URL address to open",
   "title": "Help message". The client will give users the option
   of opening the URL in a new browser window/tab. To use this feature 
   the URL omero.types.rmap should use the key: 'URL' in the output map.

   ::

           url = omero.rtypes.wrap({
               "type": "URL",
               "href": "https://www.openmicroscopy.org",
               "title": "Open URL link to OME's website.",
            })
           client.setOutput("URL", url)

More tips
---------

-  Use the 'unwrap()' function from omero.rtypes to unwrap rtypes from
   the script parameters since this function will iteratively unwrap
   lists, maps, etc..

   ::

       from omero.rtypes import *
       scriptParams = {}
       for key in client.getInputKeys():
           if client.getInput(key):
               scriptParams[key] = unwrap(client.getInput(key))

       print(scriptParams)    # stdout will be returned - useful for bug fixing etc. 
