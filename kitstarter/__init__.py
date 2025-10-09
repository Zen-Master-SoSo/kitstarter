#  kitstarter/__init__.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
#
"""
kitstarter is a program you can use to "sketch in" a drumkit SFZ file.
"""
import sys, os, argparse, logging, json, glob
try:
	from functools import cache
except ImportError:
	from functools import lru_cache as cache
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication, QWidget, QSplitter
from qt_extras import DevilBox
from conn_jack import JackConnectError

__version__ = "0.2.0"


APPLICATION_NAME	= "KitStarter"
PACKAGE_DIR			= os.path.dirname(__file__)
KEY_RECENT_FOLDER	= 'RecentProjectFolder'
KEY_FILES_ROOT		= 'FilesRoot'
KEY_FILES_CURRENT	= 'FilesCurrent'
KEY_MIDI_SOURCE		= 'MIDISource'
KEY_AUDIO_SINK		= 'AudioSink'

# -------------------------------------------------------------------
# Per-user application settings

@cache
def settings():
	return QSettings('ZenSoSo', 'kitstarter')


# -------------------------------------------------------------------
# Cross-platform open any file / folder with system associated tool

def xdg_open(filename):
	if system() == "Windows":
		startfile(filename)
	elif system() == "Darwin":
		Popen(["open", filename])
	else:
		Popen(["xdg-open", filename])


# -------------------------------------------------------------------
# Add save / restore geometry methods to the QWidget class:

def _restore_geometry(widget):
	"""
	Restores geometry from musecbox settings using automatically generated key.
	"""
	if not hasattr(widget, 'restoreGeometry'):
		return
	geometry = settings().value(_geometry_key(widget))
	if not geometry is None:
		widget.restoreGeometry(geometry)
	for splitter in widget.findChildren(QSplitter):
		geometry = settings().value(_splitter_geometry_key(widget, splitter))
		if not geometry is None:
			splitter.restoreState(geometry)

def _save_geometry(widget):
	"""
	Saves geometry to musecbox settings using automatically generated key.
	"""
	if not hasattr(widget, 'saveGeometry'):
		return
	settings().setValue(_geometry_key(widget), widget.saveGeometry())
	for splitter in widget.findChildren(QSplitter):
		settings().setValue(_splitter_geometry_key(widget, splitter), splitter.saveState())

def _geometry_key(widget):
	"""
	Automatic QSettings key generated from class name.
	"""
	return f'{type(widget).__name__}/geometry'

def _splitter_geometry_key(widget, splitter):
	"""
	Automatic QSettings key generated from class name.
	"""
	return f'{type(widget).__name__}/{splitter.objectName()}/geometry'

QWidget.restore_geometry = _restore_geometry
QWidget.save_geometry = _save_geometry


# -------------------------------------------------------------------
# Main

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
		return 1
	main_window.show()
	return app.exec()


if __name__ == "__main__":
	sys.exit(main())


#  end kitstarter/__init__.py
