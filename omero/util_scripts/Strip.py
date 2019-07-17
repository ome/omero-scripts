import omero.scripts as scripts
from omero.gateway import BlitzGateway, ImageWrapper, FileAnnotationWrapper, TagAnnotationWrapper, MapAnnotationWrapper, CommentAnnotationWrapper
from omero.rtypes import rstring, rlong

# Count deleted annotations
rois_deleted = 0
annos_deleted = 0

def delete_annotations(conn, object, del_f=False, del_t=False, del_m=False, del_c=False):
    """Deletes annotations from an object

    Parameters:
    conn (BlitzGateway): Reference to the gateway
    obj (BlitzObjectWrapper): The object which annotations should be deleted
    del_f (Bool): Flag to delete file annotations
    del_t (Bool): Flag to delete tag annotations
    del_m (Bool): Flag to delete map annotations
    del_c (Bool): Flag to delete comment annotations

    Returns:
    str:A message about how many annotations have been deleted
   """
    global annos_deleted
    del_ids = []
    for anno in object.listAnnotations():
        if del_f and isinstance(anno, FileAnnotationWrapper):
            del_ids.append(long(anno.getId()))
        if del_t and isinstance(anno, TagAnnotationWrapper):
            del_ids.append(long(anno.getId()))
        if del_m and isinstance(anno, MapAnnotationWrapper):
            del_ids.append(long(anno.getId()))
        if del_c and isinstance(anno, CommentAnnotationWrapper):
            del_ids.append(long(anno.getId()))

    if del_ids:
        conn.deleteObjects("Annotation", del_ids, wait=True)
    annos_deleted += len(del_ids)
    return "Deleted %i Annotations from %s %s" % (len(del_ids), str(object.OMERO_CLASS), object.getName()) 


def delete_rois(conn, object):
    """Deletes ROIs from an object

    Parameters:
    conn (BlitzGateway): Reference to the gateway
    object (BlitzObjectWrapper): The object which annotations should be deleted

    Returns:
    str:A message about how many ROIs have been deleted

   """
    global rois_deleted
    roi_service = conn.getRoiService()
    result = roi_service.findByImage(object.getId(), None)
    del_ids = [long(roi.getId().getValue()) for roi in result.rois]
    if del_ids:
        conn.deleteObjects("Roi", del_ids, wait=True)

    rois_deleted += len(del_ids)
    return "Deleted %i Rois from Image %s" % (len(del_ids), object.getName())


def perform_action(conn, obj, del_r=False, del_f=False, del_t=False, del_m=False, del_c=False, traverse=False):
    """Performs the main action of the script, ie delete annotations and rois from an object

    Parameters:
    conn (BlitzGateway): Reference to the gateway
    obj (BlitzObjectWrapper): The object which annotations should be deleted
    del_r (Bool): Flag to delete ROIs
    del_f (Bool): Flag to delete file annotations
    del_t (Bool): Flag to delete tag annotations
    del_m (Bool): Flag to delete map annotations
    del_c (Bool): Flag to delete comment annotations
    traverse (Bool): Flag to traverse the tree (ie also delete annotations of all descendants)

    Returns:
    str:A message about how many ROIs and annotations have been deleted
   """
    message = delete_annotations(conn, obj, del_f = del_f,del_t = del_t,del_m = del_m,del_c = del_c) + "\n"
    if del_r and isinstance(obj, ImageWrapper):
        message += delete_rois(conn, obj) + "\n"
    if traverse and not isinstance(obj, ImageWrapper) and obj.countChildren() > 0:
        for child in obj.listChildren():
            message += perform_action(conn, child, del_r = del_r,del_f = del_f,del_t = del_t,del_m = del_m,del_c = del_c, traverse=traverse)
    return message

def run_script():
    data_types = [rstring('Image'), rstring('Dataset'), rstring('Project'), rstring('Screen'), rstring('Plate'), rstring('Well')]

    client = scripts.client(
        'Strip.py',
        """
Remove annotations from OMERO objects.

Warning: This script really deletes the annotations, it does not just 
unlink them!
        """,

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="The target object type", values=data_types,
            default="Image"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of target objects ids").ofType(rlong(0)),

        scripts.Bool("Traverse", grouping="3",
            description="Also delete the annotations of all descendants", default=False),

        scripts.Bool("ROIs", grouping="4.1",
            description="Delete all ROIs", default=True),

        scripts.Bool("Tags", grouping="4.2",
            description="Delete all Tags", default=True),

        scripts.Bool("File Attachments", grouping="4.3",
            description="Delete all File Attachments", default=True),

        scripts.Bool("Key-Value Pairs", grouping="4.4",
            description="Delete all Key-Value Pairs", default=True),

        scripts.Bool("Comments", grouping="4.5",
            description="Delete all Comments", default=True),

        version="0.0.1",
        authors=["Dominik Lindner", "OME Team"],
        institutions=["University of Dundee"],
        contact="d.lindner@dundee.ac.uk",
    )

    try:
        conn = BlitzGateway(client_obj=client)

        script_params = client.getInputs(unwrap=True)

        objects = conn.getObjects(script_params['Data_Type'], ids=script_params['IDs'])

        message = "Results:\n"
        for obj in objects:
            message += perform_action(conn, obj, del_r = script_params['ROIs'],\
                                                 del_f = script_params['File Attachments'],\
                                                 del_t = script_params['Tags'],\
                                                 del_m = script_params['Key-Value Pairs'],\
                                                 del_c = script_params['Comments'],\
                                                 traverse = script_params['Traverse']) + "\n"
        print message
        client.setOutput("Message", rstring("Deleted %i ROIs and %i other annotations" % (rois_deleted, annos_deleted)))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
