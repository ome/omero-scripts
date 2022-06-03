#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2016 University of Dundee & Open Microscopy Environment.
# All rights reserved. Use is subject to license terms supplied in LICENSE.txt
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
   Integration test for import scripts.
"""

import omero
import omero.scripts
from script import ScriptTest
from script import run_script
from omero.util.temp_files import create_path
from omero.gateway import BlitzGateway


populate_metadata = "/omero/import_scripts/Populate_Metadata.py"


class TestImportScripts(ScriptTest):

    def test_populate_metadata_for_plate(self):
        sid = super(TestImportScripts, self).get_script(populate_metadata)
        assert sid > 0

        client, user = self.new_client_and_user()
        plates = self.import_plates(client, plate_cols=3, plate_rows=1)
        plate = plates[0]
        cvs_file = create_path("test_plate", ".csv")

        # create a file annotation
        with open(cvs_file.abspath(), 'w+') as f:
            f.write("Well,Well Type, Facility-Salt-Batch-ID\n")
            f.write("A01,Treatment,FOOL10041-101-2\n")
            f.write("A02,Control,\n")
            f.write("A03,Treatment,FOOL10041-101-2\n")

        conn = BlitzGateway(client_obj=client)
        fa = conn.createFileAnnfromLocalFile(cvs_file, mimetype="text/csv")
        assert fa is not None
        assert fa.id > 0
        link = omero.model.PlateAnnotationLinkI()
        link.setParent(plate)
        link.setChild(omero.model.FileAnnotationI(fa.id, False))
        client.getSession().getUpdateService().saveAndReturnObject(link)
        # run the script
        plate_ids = []
        plate_ids.append(omero.rtypes.rlong(plate.id.val))

        args = {
            "Data_Type": omero.rtypes.rstring("Plate"),
            "IDs": omero.rtypes.rlist(plate_ids),
            "File_Annotation": omero.rtypes.rstring(str(fa.id))
        }
        message = run_script(client, sid, args, "Message")
        assert message is not None
        assert message.getValue().startswith('Table data populated')
        conn.close()

    def test_populate_metadata_for_screen(self):
        sid = super(TestImportScripts, self).get_script(populate_metadata)
        assert sid > 0

        client, user = self.new_client_and_user()
        update_service = client.getSession().getUpdateService()
        plates = self.import_plates(client, plate_cols=3, plate_rows=1)
        plate = plates[0]
        name = plate.name.val
        screen = omero.model.ScreenI()
        screen.name = omero.rtypes.rstring("test_for_screen")
        spl = omero.model.ScreenPlateLinkI()
        spl.setParent(screen)
        spl.setChild(plate)
        spl = update_service.saveAndReturnObject(spl)
        screen_id = spl.getParent().id.val
        assert screen_id > 0
        assert spl.getChild().id.val == plate.id.val

        cvs_file = create_path("test_screen", ".csv")

        # create a file annotation
        with open(cvs_file.abspath(), 'w+') as f:
            f.write("Well,Plate, Well Type, Facility-Salt-Batch-ID\n")
            f.write("A01,%s,Treatment,FOOL10041-101-2\n" % name)
            f.write("A02,%s,Control,\n" % name)
            f.write("A03,%s,Treatment,FOOL10041-101-2\n" % name)

        conn = BlitzGateway(client_obj=client)
        fa = conn.createFileAnnfromLocalFile(cvs_file, mimetype="text/csv")
        assert fa is not None
        assert fa.id > 0
        link = omero.model.ScreenAnnotationLinkI()
        link.setParent(omero.model.ScreenI(screen_id, False))
        link.setChild(omero.model.FileAnnotationI(fa.id, False))
        link = update_service.saveAndReturnObject(link)
        assert link.id.val > 0
        # run the script
        screen_ids = []
        screen_ids.append(spl.getParent().id)

        args = {
            "Data_Type": omero.rtypes.rstring("Screen"),
            "IDs": omero.rtypes.rlist(screen_ids),
            "File_Annotation": omero.rtypes.rstring(str(fa.id))
        }
        message = run_script(client, sid, args, "Message")
        assert message is not None
        assert message.getValue().startswith('Table data populated')
        conn.close()

    def test_populate_metadata_for_encodings(self):
        sid = super(TestImportScripts, self).get_script(populate_metadata)
        assert sid > 0
        import encodings
        import os
        from omero.util.populate_roi import DownloadingOriginalFileProvider
        
        # Skip test if the omero-py version does not yet provide support for the encodings
        if "encoding" in DownloadingOriginalFileProvider.get_original_file_data.__code__.co_varnames:
            print("Skipping test of populate_metadata.py for encodings as omero-py version does not support it!")
            return
        
        AvailEncodings=[]
        for i in os.listdir(os.path.split(__import__("encodings").__file__)[0]):
            name=os.path.splitext(i)[0]
            try:
                "".encode(name)
            except:
                pass
            else:
                AvailEncodings.append(name.replace("_","-"))
            
        client, user = self.new_client_and_user()
        conn = BlitzGateway(client_obj=client)
        update_service = client.getSession().getUpdateService()
        
        for enc in AvailEncodings:
            plates = self.import_plates(client, plate_cols=3, plate_rows=1)
            plate = plates[0]
            name = plate.name.val
            screen = omero.model.ScreenI()
            screen.name = omero.rtypes.rstring("test_for_%s" % (enc))
            spl = omero.model.ScreenPlateLinkI()
            spl.setParent(screen)
            spl.setChild(plate)
            spl = update_service.saveAndReturnObject(spl)
            screen_id = spl.getParent().id.val
            assert screen_id > 0
            assert spl.getChild().id.val == plate.id.val
            cvs_file = create_path("test_cp1252", ".csv")
            # create a file annotation
            with open(cvs_file.abspath(), 'wb+') as f:
                f.write("Well,Plate, Well Type, Facility-Salt-Batch-ID,Comment,\n".encode(enc))
                f.write(("A01,%s,Treatment,FOOL10041-101-2,TestString containing greek µ\n" % name).encode(enc))
                f.write(("A02,%s,Control,TestString containing symbol ±\n" % name).encode(enc))
                f.write(("A03,%s,Treatment,FOOL10041-101-2,TestString containing special character §\n" % name).encode(enc))
            fa = conn.createFileAnnfromLocalFile(cvs_file, mimetype="text/csv")
            assert fa is not None
            assert fa.id > 0
            link = omero.model.ScreenAnnotationLinkI()
            link.setParent(omero.model.ScreenI(screen_id, False))
            link.setChild(omero.model.FileAnnotationI(fa.id, False))
            link = update_service.saveAndReturnObject(link)
            assert link.id.val > 0
            # run the script
            screen_ids = []
            screen_ids.append(spl.getParent().id)

            args = {
                "Data_Type": omero.rtypes.rstring("Screen"),
                "IDs": omero.rtypes.rlist(screen_ids),
                "File_Annotation": omero.rtypes.rstring(str(fa.id)),
                "CSV Encoding": omero.rtypes.rstring(str(enc))
            }
            message = run_script(client, sid, args, "Message")
            assert message is not None
            assert message.getValue().startswith('Table data populated') or message.getValue.startswith('The CSV file provided could not be decoded')
        conn.close()
