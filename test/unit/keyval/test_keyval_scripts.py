# -*- coding: utf-8 -*-

#
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
   Unit test for keyval scripts.
"""

import sys
import os
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..',
                                                '..',
                                                '..',
                                                'omero',
                                                'keyval_scripts'
                                                )
                                   )
                )
# Additional libs.
import pytest

# Test class.
class TestKeyValScripts():

    def test_module_imports(self):
        """ Test that the scripts can be imported. """


        import KeyVal_from_csv
        import KeyVal_from_Description
        import KeyVal_from_Filename
        import KeyVal_to_csv
        import Remove_KeyVal

        assert os.path.exists(KeyVal_from_csv.__file__)
        assert os.path.exists(KeyVal_from_csv.__file__)
        assert os.path.exists(KeyVal_from_csv.__file__)
        assert os.path.exists(KeyVal_from_csv.__file__)
        assert os.path.exists(KeyVal_from_csv.__file__)

   
if __name__ == "__main__":
    pytest.main()
