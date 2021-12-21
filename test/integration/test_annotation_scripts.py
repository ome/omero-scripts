#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2016 University of Dundee & Open Microscopy Environment.
# Copyright (C) 2021 Max Planck Institute for Evolutionary Biology
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
   Integration test for keyval scripts.
"""

from __future__ import print_function
import omero
from omero.gateway import BlitzGateway
import omero.scripts
import pytest
from script import ScriptTest
from script import run_script
from omero.cmd import Delete2
from omero.rtypes import wrap

channel_offsets = "/omero/util_scripts/Channel_Offsets.py"
combine_images = "/omero/util_scripts/Combine_Images.py"
images_from_rois = "/omero/util_scripts/Images_From_ROIs.py"
dataset_to_plate = "/omero/util_scripts/Dataset_To_Plate.py"
move_annotations = "/omero/util_scripts/Move_Annotations.py"


class TestAnnotationScripts(ScriptTest):

    @pytest.mark.xfail
    def test_implemented(self):

        raise NotImplementedError()

