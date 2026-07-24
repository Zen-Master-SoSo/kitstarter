#  kitstarter/kitstarter/__main__.py
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
kitstarter is a program you can use to "sketch in" a drumkit SFZ file.
"""
import sys, logging
from os import environ, getlogin
from argparse import ArgumentParser
from PyQt5.QtWidgets import QApplication
from xdg_soso import is_xdg
from kitstarter import LOG_FORMAT, KitStarterSetup
from kitstarter.gui.main_window import MainWindow


# -------------------------------------------------------------------
# Main

def main():
	parser = ArgumentParser()
	parser.epilog = __doc__
	parser.add_argument('Filename', type=str, nargs='?',
		help='.SFZ file to import')
	if is_xdg():
		parser.add_argument('--install', '-i', action = 'store_true',
			help = """Install this application into your desktop
environment. This will create a desktop launcher so you can start KitStarter from
your menu or Dash, and associate KitStarter with SFZ files.""")
		parser.add_argument('--uninstall', '-u', action = 'store_true',
			help = """Remove KitStarter from your desktop environment.
The program will still be on your computer, and can be called from the command
line as "kitbash", but you won't be able to see it in your desktop applications
menu.""")
	parser.add_argument("--verbose", "-v", action="store_true",
		help="Show more detailed debug information")
	options = parser.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	logging.basicConfig(level = log_level, format = LOG_FORMAT)

	if options.install:
		KitStarterSetup().install()
		print(f'Successfully installed KitStarter for {getlogin()} on this machine.')
	elif options.uninstall:
		KitStarterSetup().uninstall()
		print(f'Successfully uninstalled KitStarter for {getlogin()} on this machine.')
	else:
		#-----------------------------------------------------------------------
		# Annoyance fix per:
		# https://stackoverflow.com/questions/986964/qt-session-management-error
		try:
			del environ['SESSION_MANAGER']
		except KeyError:
			pass
		#-----------------------------------------------------------------------
		app = QApplication([])
		main_window = MainWindow(options.Filename or None)
		main_window.show()
		return app.exec()


if __name__ == "__main__":
	sys.exit(main())


#  end kitstarter/kitstarter/__main__.py
