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
import sys, os, argparse, logging
from PyQt5.QtWidgets import QApplication
from kitstarter import LOG_FORMAT
from kitstarter.gui.main_window import MainWindow

# -------------------------------------------------------------------
# Main

def main():
	p = argparse.ArgumentParser()
	p.epilog = """
	Write your help text!
	"""
	p.add_argument('Filename', type=str, nargs='?', help='.SFZ file to import')
	p.add_argument("--verbose", "-v", action="store_true", help="Show more detailed debug information")
	options = p.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	logging.basicConfig(level = log_level, format = LOG_FORMAT)

	#-----------------------------------------------------------------------
	# Annoyance fix per:
	# https://stackoverflow.com/questions/986964/qt-session-management-error
	try:
		del os.environ['SESSION_MANAGER']
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
