#  kitstarter/kitstarter/jack_audio.py
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
Provides MainWindow of the kitstarter application.
"""
import logging	# pylint: disable = unused-import
from tempfile import mkstemp
from os import unlink
from PyQt5.QtCore import pyqtSlot
from soundfile import SoundFile
from qt_liquid_pool import LiquidPool
from jack_audio_player import JackAudioPlayer
from kitstarter import get_setting, set_setting, KEY_MIDI_SOURCE, KEY_AUDIO_SINK


SYNTH_NAME = 'liquidsfz'
AUDIO_PLAYER_CLIENT = 'kitstarter_jack_player'
CONNECT_RETRY_INTERVAL = 1776


class Audio(LiquidPool):
	"""
	Handles audio, including hosting an instance of liquidsfz, and playing samples.
	"""

	def __init__(self):
		super().__init__()
		_, self.tempfile = mkstemp(suffix='.sfz')
		self.synth = None
		self.audio_player = None
		self.sig_jack_ready.connect(self.slot_jack_ready)

	def quit(self):
		super().quit()
		unlink(self.tempfile)

	def slot_jack_ready(self, state):
		if state:
			with open(self.tempfile, 'w', encoding = 'utf-8') as fob:
				fob.write('// Empty\n')
			self.synth = self.create_synth(self.tempfile)
			self.audio_player = JackAudioPlayer(AUDIO_PLAYER_CLIENT)

	def get_preferred_midi_source(self):
		return get_setting(KEY_MIDI_SOURCE)

	def set_preferred_midi_source(self, value):
		set_setting(KEY_MIDI_SOURCE, value)
		super().set_preferred_midi_source(value)

	def get_preferred_audio_sink(self):
		return get_setting(KEY_AUDIO_SINK)

	def set_preferred_audio_sink(self, value):
		set_setting(KEY_AUDIO_SINK, value)
		super().set_preferred_audio_sink(value)

	def disconnect_audio_sinks(self, ports):
		super().disconnect_audio_sinks(ports)
		for src, tgt in zip(self.audio_player.output_ports, ports):
			self.conn_man.disconnect(src, tgt)

	def connect_audio_sinks(self, ports):
		super().connect_audio_sinks(ports)
		for src, tgt in zip(self.audio_player.output_ports, ports):
			self.conn_man.connect(src, tgt)

	def load_kit(self, kit):
		with open(self.tempfile, 'w', encoding = 'utf-8') as fob:
			kit.write(fob)
		self.synth.load(self.tempfile)	# pylint: disable = no-member

	@pyqtSlot(SoundFile)
	def slot_play_soundfile(self, soundfile):
		if self.audio_player:
			soundfile.seek(0)
			self.audio_player.play_python_soundfile(soundfile)

	@pyqtSlot()
	def slot_stop_playing(self):
		if self.audio_player:
			self.audio_player.stop()


#  end kitstarter/kitstarter/jack_audio.py
