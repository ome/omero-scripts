#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#   Created by Riccardo Massei
# ------------------------------------------------------------------------------

"""
Generate a unique session token (UUID) representing the current
user session in OMERO.web.

This OMERO.web script retrieves and returns UUID associated with the
currently authenticated user session.

More information regarding create a connection using an existing
session can be found here:
https://omero.readthedocs.io/en/v5.6.9/developers/Python.html

"""

from omero.rtypes import rstring
import omero.scripts as scripts


def main():
    """Fetch the session UUID for the current user."""
    client = scripts.client(
        "UUID_session_key.py",
        "Returns the current session token (UUID)"
    )
    try:
        session_id = client.getSessionId()
        client.setOutput(
            key="Message",
            value=rstring(f"UUID: {session_id}")
        )
    finally:
        client.closeSession()


if __name__ == '__main__':
    main()
