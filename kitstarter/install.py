#  kitstarter/kitstarter/install.py
#
#  Copyright 2026 Leon Dionne <ldionne@dridesign.sh.cn>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
"""
Install kitstarter as an application on XDG-compliant systems like Gnome desktop.
"""
import sys, logging
from os.path import dirname, join
from xdg_soso import is_xdg, XDGSetup, XDGMime
from kitstarter import LOG_FORMAT


def main():
	if is_xdg():
		xdg = XDGSetup('kitstarter', 'KitStarter')
		xdg.comment = 'KitStarter is a Qt -based program you can use to "sketch in" a drumkit SFZ file..'
		xdg.vendor_name = 'zen_soso'
		xdg.application_icon = join(dirname(__file__), 'res', 'kitstarter-icon.svg')
		xdg.categories = ['AudioVideo', 'Audio']
		xdg.keywords = ['Audio', 'Sound', 'midi', 'SFZ', 'Drumkit']
		xdg.append_mime_type(XDGMime('audio/x-sfz', '*.sfz'))
		xdg.install()


if __name__ == '__main__':
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	sys.exit(main() or 0)


#  end kitstarter/kitstarter/install.py
