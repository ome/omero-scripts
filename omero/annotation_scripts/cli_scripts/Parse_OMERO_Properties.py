#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 20 14:16:53 2017

@author: evenhuis

FOR TRAINING PURPOSES ONLY!

Change this file to Parse_OMERO_Properties.py and enter your ID/username 
"""

import omero
import os
import sys

try:
    omero_app_url = os.environ["OMERO_APP_URL"]
    omero_username = os.environ["OMERO_USERNAME"]
    omero_user_password = os.environ["OMERO_USER_PASSWORD"]
except KeyError:
    print "Please set the environment variable OMERO_USERNAME, OMERO_USER_PASSWORD and OMERO_APP_URL"
    sys.exit(1)

client = omero.client(omero_app_url)

omeroProperties = client.getProperties().getPropertiesForPrefix('omero')

# Configuration
# =================================================================
# These values will be imported by all the other training scripts.
HOST = omeroProperties.get('omero.host', omero_app_url)
PORT = omeroProperties.get('omero.port', 4064)
USERNAME = omeroProperties.get('omero.user', omero_username)
PASSWORD = omeroProperties.get('omero.pass', omero_user_password)
OMERO_WEB_HOST = omeroProperties.get('omero.webhost')
SERVER_NAME = omeroProperties.get(omero_app_url)
# projectId = omeroProperties.get('omero.projectid')
# datasetId = omeroProperties.get('omero.datasetid')
# imageId = omeroProperties.get('omero.imageid')
