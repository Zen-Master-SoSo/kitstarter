#  kitstarter/__init__.py
#
#  Copyright 2025 liyang <liyang@veronica>
#
"""
kitstarter is a program you can use to "sketch in" a drumkit SFZ file.
"""
import sys, os, argparse, logging, json, glob
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication
from qt_extras import DevilBox
from jack_connection_manager import JackConnectError

APPLICATION_NAME	= "KitStarter"
PACKAGE_DIR			= os.path.dirname(__file__)
DEFAULT_STYLE		= 'system'
KEY_STYLE			= 'Style'
KEY_RECENT_FOLDER	= 'RecentProjectFolder'
KEY_FILES_ROOT		= 'FilesRoot'
KEY_FILES_CURRENT	= 'FilesCurrent'

def settings():
	if getattr(settings, 'cached_var', None) is None:
		settings.cached_var = QSettings("ZenSoSo", APPLICATION_NAME)
	return settings.cached_var

def styles():
	if getattr(styles, 'cached_var', None) is None:
		styles.cached_var = {
			os.path.splitext(os.path.basename(path))[0] : path \
			for path in glob.glob(os.path.join(PACKAGE_DIR, 'styles', '*.css'))
		}
	return styles.cached_var

def set_application_style():
	style = settings().value(KEY_STYLE, DEFAULT_STYLE)
	try:
		with open(styles()[style], 'r', encoding = 'utf-8') as cssfile:
			QApplication.instance().setStyleSheet(cssfile.read())
	except KeyError:
		pass

def main():
	from kitstarter.gui.main_window import MainWindow

	p = argparse.ArgumentParser()
	p.epilog = """
	Write your help text!
	"""
	p.add_argument('Filename', type=str, nargs='?', help='.SFZ file to import')
	p.add_argument("--verbose", "-v", action="store_true", help="Show more detailed debug information")
	options = p.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	log_format = "[%(filename)24s:%(lineno)4d] %(levelname)-8s %(message)s"
	logging.basicConfig(level = log_level, format = log_format)

	#-----------------------------------------------------------------------
	# Annoyance fix per:
	# https://stackoverflow.com/questions/986964/qt-session-management-error
	try:
		del os.environ['SESSION_MANAGER']
	except KeyError:
		pass
	#-----------------------------------------------------------------------

	app = QApplication([])
	try:
		main_window = MainWindow(options.Filename or None)
	except JackConnectError:
		DevilBox('Could not connect to JACK server. Is it running?')
		sys.exit(1)
	main_window.show()
	sys.exit(app.exec())

if __name__ == "__main__":
	sys.exit(main())


#  end kitstarter/__init__.py
