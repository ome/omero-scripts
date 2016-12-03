#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""

-----------------------------------------------------------------------------
  Copyright (C) 2016 University of Dundee. All rights reserved.


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

Uses the omero.util.populate_roi functionality to parse all the measurement
files attached to a plate, and generate server-side rois.

params:
    Plate_ID: id of the plate which should be parsed.

    Copyright 2009 Glencoe Software, Inc. All rights reserved.
    Use is subject to license terms supplied in LICENSE.txt

"""

import omero.scripts as scripts
from omero.util.populate_roi import PlateAnalysisCtxFactory

client = scripts.client(
    'Populate_ROI.py',
    scripts.Long(
        "Plate_ID", optional=False,
        description="ID of a valid plate with attached results files"),
    version="4.2.0",
    contact="ome-users@lists.openmicroscopy.org.uk",
    description="""Generates regions of interest from the measurement files \
associated with a plate

This script is executed by the server on initial import, and should typically\
not need to be run by users.""")

factory = PlateAnalysisCtxFactory(client.getSession())
analysis_ctx = factory.get_analysis_ctx(client.getInput("Plate_ID").val)
n_measurements = analysis_ctx.get_measurement_count()

for i in range(n_measurements):
    measurement_ctx = analysis_ctx.get_measurement_ctx(i)
    measurement_ctx.parse_and_populate()
