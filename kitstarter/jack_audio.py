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
import os, logging, tempfile
from itertools import chain
from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QTimer
from soundfile import SoundFile
from liquiphy import LiquidSFZ
from conn_jack import JACK_PORT_IS_INPUT, JackConnectionManager, JackConnectError
from jack_audio_player import JackAudioPlayer
from kitstarter import get_setting, set_setting, KEY_MIDI_SOURCE, KEY_AUDIO_SINK


SYNTH_NAME = 'liquidsfz'
CONNECT_RETRY_INTERVAL = 1776


class Audio(QObject):
	"""
	User interface of the kitstarter application.
	"""

	sig_ports_complete = pyqtSignal()	# \
	sig_sources_changed = pyqtSignal()	#  Used to decouple JackConnectionManager callbacks
	sig_sinks_changed = pyqtSignal()	# /
	sig_jack_down = pyqtSignal()		#
	sig_jack_ready = pyqtSignal(int)

	def __init__(self):
		super().__init__()
		self.conn_man = None
		self.synth = None
		self.audio_player = None
		self.src_connected = False
		self.sink_connected = False
		_, self.tempfile = tempfile.mkstemp(suffix='.sfz')
		self.sig_ports_complete.connect(self.slot_ports_complete, type = Qt.QueuedConnection)
		self.sig_sources_changed.connect(self.slot_sources_changed, type = Qt.QueuedConnection)
		self.sig_sinks_changed.connect(self.slot_sinks_changed, type = Qt.QueuedConnection)
		self.sig_jack_down.connect(self.slot_jack_down, type = Qt.QueuedConnection)
		self.connect_retry_timer = QTimer()
		self.connect_retry_timer.setInterval(CONNECT_RETRY_INTERVAL)
		self.connect_retry_timer.setSingleShot(True)
		self.connect_retry_timer.timeout.connect(self.connect)
		QTimer.singleShot(0, self.connect)

	def connect(self):
		try:
			self.conn_man = JackConnectionManager()
		except JackConnectError:
			self.connect_retry_timer.start()
		else:
			self.conn_man.on_error(self.jack_error)
			self.conn_man.on_shutdown(self.jack_shutdown)
			self.conn_man.on_client_registration(self.jack_client_registration)
			self.conn_man.on_port_registration(self.jack_port_registration)
			self.synth = JackLiquidSFZ(self.tempfile)
			self.audio_player = JackAudioPlayer()
			self.sig_jack_ready.emit(self.conn_man.samplerate)
			self.synth.start()

	def quit(self):
		if self.synth and hasattr(self.synth, 'quit'):
			self.synth.ports_ready = False
			self.synth.quit()	# pylint: disable = no-member
		os.unlink(self.tempfile)

	# -----------------------------------------------------------------
	# JACK callbacks

	def jack_client_registration(self, client_name, action):
		if action and not self.synth.client_name and client_name.startswith(SYNTH_NAME):
			self.synth.client_name = client_name

	def jack_port_registration(self, port, action):
		if action and not self.synth.ports_ready \
			and self.synth.client_name and self.synth.client_name in port.name:
			if port.is_input and port.is_midi:
				self.synth.input_port = port
			elif port.is_output and port.is_audio:
				self.synth.output_ports.append(port)
			if self.synth.input_port and len(self.synth.output_ports) == 2:
				self.synth.ports_ready = True
				self.sig_ports_complete.emit()
		elif port.is_input:
			self.sig_sinks_changed.emit()
		else:
			self.sig_sources_changed.emit()

	def jack_error(self, error_message):
		logging.error('JACK ERROR: "%s"', error_message)

	def jack_shutdown(self):
		logging.warning('JACK is shutting down')
		self.sig_jack_down.emit()

	@pyqtSlot()
	def slot_jack_down(self):
		"""
		Triggered by sig_jack_down emitted from another thread in "jack_shutdown"
		"""
		self.conn_man.close()
		self.conn_man = None
		self.connect_retry_timer.start()

	# -----------------------------------------------------------------
	# Source / sink management

	@pyqtSlot()
	def slot_ports_complete(self):
		"""
		Triggered by sig_ports_complete, emitted in "jack_port_registration".
		"""
		self.connect_midi_source()
		self.connect_audio_sink()

	@pyqtSlot()
	def slot_sources_changed(self):
		"""
		Triggered by sig_sources_changed, emitted in "jack_port_registration".
		"""
		if self.synth.ports_ready:
			self.connect_midi_source()

	@pyqtSlot()
	def slot_sinks_changed(self):
		"""
		Triggered by sig_sinks_changed, emitted in "jack_port_registration".
		"""
		if self.synth.ports_ready:
			self.connect_audio_sink()

	@property
	def midi_src(self):
		return get_setting(KEY_MIDI_SOURCE)

	@midi_src.setter
	def midi_src(self, value):
		set_setting(KEY_MIDI_SOURCE, value)

	@property
	def audio_sink(self):
		return get_setting(KEY_AUDIO_SINK)

	@audio_sink.setter
	def audio_sink(self, value):
		set_setting(KEY_AUDIO_SINK, value)

	def connect_midi_source(self):
		if self.conn_man and self.synth and self.synth.ports_ready:
			midi_src = self.midi_src
			for port_name in self.conn_man.get_port_connections_names(self.synth.input_port):
				if port_name != midi_src:
					self.conn_man.disconnect_by_name(port_name, self.synth.input_port.name)
			self.src_connected = False
			if midi_src:
				if src_port := self.conn_man.get_port_by_name(midi_src):
					self.conn_man.connect(src_port, self.synth.input_port)
					self.src_connected = True

	def connect_audio_sink(self):
		if self.conn_man and self.synth and self.synth.ports_ready:
			audio_sink = get_setting(KEY_AUDIO_SINK)
			for output_port in chain(self.synth.output_ports, self.audio_player.output_ports):
				output_port = self.conn_man.get_port_by_name(output_port.name)
				for port_name in self.conn_man.get_port_connections_names(output_port):
					if port_name.split(':')[0] != audio_sink:
						self.conn_man.disconnect_by_name(output_port.name, port_name)
			self.sink_connected = False
			if audio_sink:
				audio_sink_ports = self.conn_man.get_ports(JACK_PORT_IS_INPUT,
					port_name_pattern = f'{audio_sink}:*')
				if audio_sink_ports:
					for src_port, dest_port in zip(self.synth.output_ports, audio_sink_ports):
						self.conn_man.connect(src_port, dest_port)
					for src_port, dest_port in zip(self.audio_player.output_ports, audio_sink_ports):
						self.conn_man.connect(src_port, dest_port)
					self.sink_connected = True

	def load_kit(self, kit):
		with open(self.tempfile, 'w', encoding = 'utf-8') as fob:
			kit.write(fob)
		self.synth.load(self.tempfile)	# pylint: disable = no-member

	@pyqtSlot(SoundFile)
	def slot_play_soundfile(self, soundfile):
		soundfile.seek(0)
		self.audio_player.play_python_soundfile(soundfile)

	@pyqtSlot()
	def slot_stop_playing(self):
		self.audio_player.stop()


class JackLiquidSFZ(LiquidSFZ):
	"""
	Wraps a LiquidSFZ instance in order to hold references to jacklib ports created
	by JackConnectionManager.
	"""

	def __init__(self, filename):
		self.client_name = None
		self.input_port = None
		self.output_ports = []
		self.ports_ready = False
		super().__init__(filename, defer_start = True)


#  end kitstarter/kitstarter/jack_audio.py
