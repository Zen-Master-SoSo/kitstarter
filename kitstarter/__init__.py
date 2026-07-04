#  kitstarter/kitstarter/__init__.py
#
#  Copyright 2025-2026 Leon Dionne <ldionne@dridesign.sh.cn>
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
import sys, argparse, logging, json, glob
from os.path import dirname
try:
	from os import startfile
except ImportError:
	pass
from platform import system
from subprocess import Popen, run
from collections import namedtuple
try:
	from functools import cache
except ImportError:
	from functools import lru_cache as cache
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication, QWidget, QSplitter
from qt_extras import DevilBox

__version__ = "0.8.1"


APPLICATION_NAME	= 'KitStarter'
PACKAGE_DIR			= dirname(__file__)
FILE_FILTERS		= ['*.ogg', '*.wav', '*.flac', '*.sfz']
SAMPLE_EXTENSIONS	= ['.ogg', '.wav', '.flac']
LOG_FORMAT			= "[%(filename)24s:%(lineno)4d] %(levelname)-8s %(message)s"
KEY_SAMPLES_MODE	= 'SamplesMode'
KEY_RECENT_OPEN_DIR	= 'RecentOpenDirectory'
KEY_RECENT_SAVE_DIR	= 'RecentSaveDirectory'
KEY_SFZS_ROOT		= 'SFZRoot'
KEY_SFZS_CURRENT	= 'SFZCurrent'
KEY_MIDI_SOURCE		= 'MIDISource'
KEY_AUDIO_SINK		= 'AudioSink'
KEY_FILTER_INST		= 'FilterInstrumentSamples'
KEY_SHOW_SELECTED	= 'ShowSelectedSamples'
KEY_SHOW_PINNED		= 'ShowPinnedSamples'

SampleFileInfo		= namedtuple('SampleInfo', ['path', 'pitch', 'sfz_path', 'pinned'])


# -------------------------------------------------------------------
# Per-user application settings

def __settings():
	if not hasattr(__settings, 'settings'):
		__settings.settings = QSettings('ZenSoSo', APPLICATION_NAME)
	return __settings.settings

def get_setting(key, default = None, type_ = None):
	value = __settings().value(key, default)
	if type_:
		if value is None:
			return type_()
		if type_ is bool:
			return value == '1'
		return type_(value)
	return value

def set_setting(key, value):
	if isinstance(value, bool):
		value = '1' if value else '0'
	__settings().setValue(key, value)

def delete_setting(key):
	__settings().remove(key)

# -------------------------------------------------------------------
# Cross-platform open any file / folder with system associated tool

def xdg_open(filename):
	if system() == "Windows":
		startfile(filename)
	elif system() == "Darwin":
		Popen(["open", filename])		# pylint: disable = consider-using-with
	else:
		Popen(["xdg-open", filename])	# pylint: disable = consider-using-with


# -------------------------------------------------------------------
# Add save / restore geometry methods to the QWidget class:

def _restore_geometry(widget):
	"""
	Restores geometry from musecbox settings using automatically generated key.
	"""
	if not hasattr(widget, 'restoreGeometry'):
		return
	geometry = get_setting(_geometry_key(widget))
	if not geometry is None:
		widget.restoreGeometry(geometry)
	for splitter in widget.findChildren(QSplitter):
		geometry = get_setting(_splitter_geometry_key(widget, splitter))
		if not geometry is None:
			splitter.restoreState(geometry)

def _save_geometry(widget):
	"""
	Saves geometry to musecbox settings using automatically generated key.
	"""
	if not hasattr(widget, 'saveGeometry'):
		return
	set_setting(_geometry_key(widget), widget.saveGeometry())
	for splitter in widget.findChildren(QSplitter):
		set_setting(_splitter_geometry_key(widget, splitter), splitter.saveState())

def _geometry_key(widget):
	"""
	Automatic QSettings key generated from class name.
	"""
	return f'{widget.__class__.__name__}/geometry'

def _splitter_geometry_key(widget, splitter):
	"""
	Automatic QSettings key generated from class name.
	"""
	return f'{widget.__class__.__name__}/{splitter.objectName()}/geometry'

QWidget.restore_geometry = _restore_geometry
QWidget.save_geometry = _save_geometry


#  end kitstarter/kitstarter/__init__.py
