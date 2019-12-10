#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
   Test of the omero.scripts.parse functionality
   Copyright 2009-2019 Open Microscopy Environment. All rights reserved.
   Use is subject to license terms supplied in LICENSE.txt
"""

try:
    from omero_ext.path import path
except ImportError:
    # Python 2
    from path import path
from omero.scripts import parse_file


SCRIPTS = path(".") / ".." / "omero"


class TestParse(object):

    def test_parse_all_official_scripts(self):
        for script in SCRIPTS.walk("*.py"):
            try:
                parse_file(str(script))
            except Exception as e:
                assert False, "%s\n%s" % (script, e)
