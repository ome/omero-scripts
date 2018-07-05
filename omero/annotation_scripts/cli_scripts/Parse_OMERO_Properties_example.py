#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 20 14:16:53 2017

@author: evenhuis
"""

#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2015 University of Dundee & Open Microscopy Environment.
#                    All Rights Reserved.
# Use is subject to license terms supplied in LICENSE.txt
#

"""
FOR TRAINING PURPOSES ONLY!

Change this file to Parse_OMERO_Properties.py and enter your ID/username 
"""

import omero

client = omero.client('omero-app.research.uts.edu.au')

omeroProperties = client.getProperties().getPropertiesForPrefix('omero')

# Configuration
# =================================================================
# These values will be imported by all the other training scripts.
HOST = omeroProperties.get('omero.host', 'omero-app.research.uts.edu.au')
PORT = omeroProperties.get('omero.port', 4064)
USERNAME = omeroProperties.get('omero.user','111111')
PASSWORD = omeroProperties.get('omero.pass','your-password')
OMERO_WEB_HOST = omeroProperties.get('omero.webhost')
SERVER_NAME = omeroProperties.get('omero-app.research.uts.edu.au')
#projectId = omeroProperties.get('omero.projectid')
#datasetId = omeroProperties.get('omero.datasetid')
#imageId = omeroProperties.get('omero.imageid')
