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
   Integration test for export scripts.
"""

import pytest
import omero
import omero.scripts
from script import ScriptTest
from script import run_script
from script import check_file_annotation
from script import get_file_contents
from omero.rtypes import rstring, rint, rlong, rlist, rdouble, rbool


batch_image_export = "/omero/export_scripts/Batch_Image_Export.py"
batch_roi_export = "/omero/export_scripts/Batch_ROI_Export.py"
make_movie = "/omero/export_scripts/Make_Movie.py"


class TestExportScripts(ScriptTest):

    def test_batch_image_export(self):
        sid = super(TestExportScripts, self).get_script(batch_image_export)
        assert sid > 0

        client, user = self.new_client_and_user()
        # x,y,z,c,t
        image = self.create_test_image(100, 100, 1, 1, 1, client.getSession())
        image_ids = []
        image_ids.append(rlong(image.id.val))
        args = {
            "Data_Type": rstring("Image"),
            "IDs": rlist(image_ids)
        }
        ann = run_script(client, sid, args, "File_Annotation")
        c = self.new_client(user=user)
        check_file_annotation(c, ann)

    @pytest.mark.parametrize("all_planes", [True, False])
    def test_batch_roi_export(self, all_planes):
        sid = super(TestExportScripts, self).get_script(batch_roi_export)
        assert sid > 0

        client, user = self.new_client_and_user()
        session = client.getSession()
        # x,y,z,c,t
        size_c = 2
        size_z = 3
        size_t = 4
        image_name = "ROI_image"
        label_text = "Shape_Text"
        image = self.create_test_image(100, 100, size_z, size_c, size_t,
                                       session, name=image_name)
        # Add 2 Shapes... A Rectangle and Polygon covering same area
        polygon = omero.model.PolygonI()
        polygon.points = rstring("10,10, 91,10, 91,91, 10,91")
        polygon.textValue = rstring(label_text)
        rect = omero.model.RectangleI()
        rect.x = rdouble(10)
        rect.y = rdouble(10)
        rect.width = rdouble(81)
        rect.height = rdouble(81)
        rect.theZ = rint(1)
        rect.theT = rint(1)
        # ...to an ROI
        roi = omero.model.RoiI()
        roi.setImage(image)
        roi.addShape(polygon)
        roi.addShape(rect)
        roi = session.getUpdateService().saveAndReturnObject(roi)
        shapes = roi.copyShapes()
        polygon = shapes[0]

        image_ids = []
        file_name = "test_batch_roi_export"
        image_ids.append(rlong(image.id.val))
        channels = [rlong(c) for c in range(4)]
        args = {
            "Data_Type": rstring("Image"),
            "IDs": rlist(image_ids),
            # Should ignore Channels out of range. 1-based index
            "Channels": rlist(channels),
            "Export_All_Planes": rbool(all_planes),
            "File_Name": rstring(file_name)
        }
        ann = run_script(client, sid, args, "File_Annotation")
        c = self.new_client(user=user)
        check_file_annotation(c, ann,
                              file_name="%s.csv" % file_name)
        file_id = ann.getValue().getFile().id.val
        csv_text = get_file_contents(self.new_client(user=user), file_id)

        # Check we have expected number of rows
        polygon_planes = size_c
        if all_planes:
            polygon_planes = size_c * size_z * size_t
        # Rows: Header + rect with Z/T set + polygon without Z/T
        row_count = 1 + size_c + polygon_planes
        assert len(csv_text.split("\n")) == row_count

        # Check first 2 rows of csv (except Std dev)
        zt = ","
        points_min_max_sum_mean = ",,,,"
        if all_planes:
            zt = "1,1"
            points_min_max_sum_mean = "6561,10.0,90.0,328050.0,50.0"
        expected = ("image_id,image_name,roi_id,shape_id,type,text,"
                    "z,t,channel,points,min,max,sum,mean,std_dev\n"
                    "%s,\"%s\",%s,%s,polygon,\"%s\",%s,0,%s,") % (
                    image.id.val, image_name, roi.id.val,
                    polygon.id.val, label_text, zt, points_min_max_sum_mean)
        assert csv_text.startswith(expected)

    @pytest.mark.broken(
        reason=('https://trello.com/c/AlN5hp6g/144-make-movie-tests-failures'))
    @pytest.mark.xfail(
        reason=('https://trello.com/c/AlN5hp6g/144-make-movie-tests-failures'))
    def test_make_movie(self):
        script_id = super(TestExportScripts, self).get_script(make_movie)
        assert script_id > 0

        client, user = self.new_client_and_user()
        # x,y,z,c,t
        image = self.create_test_image(10, 10, 2, 1, 2, client.getSession())
        image_ids = []
        image_ids.append(rlong(image.id.val))
        args = {
            "Data_Type": rstring("Image"),
            "IDs": rlist(image_ids),
            "Movie_Name": rstring("test_make_movie")
        }
        ann = run_script(client, script_id, args, "File_Annotation")
        c = self.new_client(user=user)
        check_file_annotation(c, ann)
