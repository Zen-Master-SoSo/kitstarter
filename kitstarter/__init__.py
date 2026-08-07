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
from os.path import dirname, join
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
from qt_extras.settings import get_setting, set_setting
from xdg_soso import XDGSetup, XDGMime

__version__ = "1.0.1"


VENDOR_NAME			= 'ZenSoSo'
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


class KitStarterSetup(XDGSetup):

	def __init__(self):
		super().__init__(__package__, APPLICATION_NAME)
		self.vendor_name = VENDOR_NAME
		self.comment = 'KitStarter is a Qt -based program you can use to "sketch in" a drumkit SFZ file..'
		self.application_icon = join(dirname(__file__), 'res', 'kitstarter-icon.svg')
		self.categories = ['AudioVideo', 'Audio']
		self.keywords = ['Audio', 'Sound', 'midi', 'SFZ', 'Drumkit']
		self.append_mime_type(XDGMime('audio/x-sfz', '*.sfz'))


def xdg_open(filename):
	"""
	Cross-platform open any file / folder with system associated tool
	"""
	if system() == "Windows":
		startfile(filename)
	elif system() == "Darwin":
		Popen(["open", filename])		# pylint: disable = consider-using-with
	else:
		Popen(["xdg-open", filename])	# pylint: disable = consider-using-with


#  end kitstarter/kitstarter/__init__.py
