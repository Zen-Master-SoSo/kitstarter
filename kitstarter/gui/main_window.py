#  kitstarter/kitstarter/gui/main_window.py
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
Provides MainWindow of the kitstarter application.
"""
import logging
from os.path import join, dirname, basename, abspath
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot, QTimer
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QComboBox, QLabel
from qt_extras import SigBlock, ShutUpQT
from midi_notes import MIDI_DRUM_NAMES
from sfzen.drumkits import iter_pitch_by_group
from kitstarter import (
	get_setting, set_setting, APPLICATION_NAME, KEY_RECENT_OPEN_DIR, KEY_RECENT_SAVE_DIR)
from kitstarter.gui.instrument_widget import InstrumentWidget, init_paint_resources
from kitstarter.gui.samples_explorer import SamplesExplorer
from kitstarter.gui.files_explorer import FilesExplorer
from kitstarter.gui.instrument_list import InstrumentList
from kitstarter.starter_kits import StarterKit
from kitstarter.jack_audio import Audio

SYNTH_NAME = 'liquidsfz'
MESSAGE_TIMEOUT = 3000


class MainWindow(QMainWindow):
	"""
	User interface of the kitstarter application.
	"""

	def __init__(self, filename):
		super().__init__()
		# Setup GUI
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'main_window.ui'), self)
		self.sfz_filename = filename
		self.kit = StarterKit()
		self.audio = Audio()

		# Setup stacked samples widget
		for pitch in iter_pitch_by_group():
			instrument_widget = InstrumentWidget(self, self.kit.instrument(pitch))
			instrument_widget.sig_updating.connect(self.slot_updating)
			instrument_widget.sig_updated.connect(self.slot_updated)
			instrument_widget.sig_mouse_press.connect(self.slot_trackpad_pressed)
			instrument_widget.sig_mouse_release.connect(self.slot_trackpad_release)
			self.stk_instrument_widget.addWidget(instrument_widget)
		# Remove first (placeholder) widget from QStackedWidget
		widget = self.stk_instrument_widget.widget(0)
		self.stk_instrument_widget.removeWidget(widget)
		widget.deleteLater()

		# Setup InstrumentList
		self.instrument_list = InstrumentList(self)
		self.central_layout.replaceWidget(
			self.frm_inst_list_placeholder,
			self.instrument_list)
		self.frm_inst_list_placeholder.setVisible(False)
		self.frm_inst_list_placeholder.deleteLater()
		del self.frm_inst_list_placeholder

		# Setup FilesExplorer
		self.files_explorer = FilesExplorer(self)
		self.explorer_layout.replaceWidget(
			self.frm_file_expl_placeholder,
			self.files_explorer)
		self.frm_file_expl_placeholder.setVisible(False)
		self.frm_file_expl_placeholder.deleteLater()
		del self.frm_file_expl_placeholder

		# Setup SamplesExplorer
		self.samples_explorer = SamplesExplorer(self)
		self.explorer_layout.replaceWidget(
			self.frm_samp_expl_placeholder,
			self.samples_explorer)
		self.frm_samp_expl_placeholder.setVisible(False)
		self.frm_samp_expl_placeholder.deleteLater()
		del self.frm_samp_expl_placeholder

		# Setup statusbar
		self.lbl_jack_state = QLabel('[not connected]', self)
		self.statusbar.addPermanentWidget(self.lbl_jack_state)
		self.cmb_midi_srcs = QComboBox(self.statusbar)
		self.cmb_midi_srcs.setSizeAdjustPolicy(QComboBox.AdjustToContents)
		self.statusbar.addPermanentWidget(QLabel('Src:', self.statusbar))
		self.statusbar.addPermanentWidget(self.cmb_midi_srcs)
		self.cmb_audio_sinks = QComboBox(self.statusbar)
		self.cmb_audio_sinks.setSizeAdjustPolicy(QComboBox.AdjustToContents)
		self.statusbar.addPermanentWidget(QLabel('Sink:', self.statusbar))
		self.statusbar.addPermanentWidget(self.cmb_audio_sinks)

		# Connect signals
		self.stk_instrument_widget.currentChanged.connect(
			self.slot_current_sample_widget_changed)
		self.instrument_list.sig_row_changed.connect(
			self.stk_instrument_widget.setCurrentIndex)
		self.files_explorer.sig_selection_changed.connect(
			self.samples_explorer.slot_files_selection_changed)
		self.files_explorer.sig_open_sfz.connect(
			self.slot_open_selected)
		self.files_explorer.sig_use_samples.connect(
			self.slot_use_samples)
		self.samples_explorer.sig_use_samples.connect(
			self.slot_use_samples)
		self.samples_explorer.sig_play_soundfile.connect(
			self.audio.slot_play_soundfile)
		self.samples_explorer.sig_stop_playing.connect(
			self.audio.slot_stop_playing)
		self.cmb_midi_srcs.currentTextChanged.connect(
			self.audio.slot_midi_src_selected)
		self.cmb_audio_sinks.currentTextChanged.connect(
			self.audio.slot_audio_sink_selected)
		self.audio.sig_jack_down.connect(
			self.slot_jack_down)
		self.audio.sig_jack_ready.connect(
			self.slot_jack_ready)
		self.audio.sig_jack_ready.connect(
			self.samples_explorer.slot_jack_ready)
		self.audio.sig_sources_changed.connect(
			self.slot_sources_changed)
		self.audio.sig_sinks_changed.connect(
			self.slot_sinks_changed)
		self.audio.sig_midi_connected.connect(
			self.slot_midi_connected)

		# Connect menu actions
		self.action_new.triggered.connect(self.slot_new)
		self.action_open.triggered.connect(self.slot_open)
		self.action_save.triggered.connect(self.slot_save)
		self.action_save_as.triggered.connect(self.slot_save_as)
		self.action_exit.triggered.connect(self.close)

		# Prep UI
		init_paint_resources()
		self.restore_geometry()
		QTimer.singleShot(0, self.layout_complete)

	def layout_complete(self):
		self.slot_current_sample_widget_changed(None)
		self.files_explorer.layout_complete()
		self.audio.connect()
		if self.sfz_filename:
			self.load_sfz()

	def update_window_title(self):
		title = APPLICATION_NAME if self.sfz_filename is None \
			else f'{self.sfz_filename} - {APPLICATION_NAME}'
		if self.kit.is_dirty():
			title = '*' + title
		self.setWindowTitle(title)

	# pylint: disable-next = invalid-name
	def closeEvent(self, _):
		self.audio.quit()
		self.save_geometry()

	# -----------------------------------------------------------------
	# Load / save

	def iterate_sample_widgets(self):
		for index in range(self.stk_instrument_widget.count()):
			yield self.stk_instrument_widget.widget(index)

	@pyqtSlot()
	def slot_new(self):
		for widget in self.iterate_sample_widgets():
			widget.clear()

	@pyqtSlot()
	def slot_open(self):
		filename, _ = QFileDialog.getOpenFileName(self,
			"Open .sfz file",
			get_setting(KEY_RECENT_OPEN_DIR, ''),
			".SFZ files (*.sfz)"
		)
		if filename != '':
			self.sfz_filename = abspath(filename)
			set_setting(KEY_RECENT_OPEN_DIR, dirname(self.sfz_filename))
			self.load_sfz()

	@pyqtSlot(str)
	def slot_open_selected(self, filename):
		self.sfz_filename = abspath(filename)
		set_setting(KEY_RECENT_OPEN_DIR, dirname(self.sfz_filename))
		self.load_sfz()

	def load_sfz(self):
		self.kit = StarterKit(self.sfz_filename)
		for index, widget in enumerate(self.iterate_sample_widgets()):
			widget.load_instrument(self.kit.instrument(widget.instrument.pitch))
			self.instrument_list.update_instrument(index, widget.has_samples())
		self.audio.load_kit(self.kit)
		self.statusbar.showMessage(f'Opened {self.sfz_filename}', MESSAGE_TIMEOUT)
		self.update_window_title()

	@pyqtSlot()
	def slot_save(self):
		if self.sfz_filename is None:
			self.slot_save_as()
		else:
			self.save()

	@pyqtSlot()
	def slot_save_as(self):
		"""
		Triggered by "File -> Save bashed kit" menu
		See also: slot_drumkit_bashed
		"""
		dir_ = get_setting(KEY_RECENT_SAVE_DIR)
		filename, _ = QFileDialog.getSaveFileName(
			self,
			'Save as .sfz ...',
			dir_ if self.sfz_filename is None else join(dir_, basename(self.sfz_filename)),
			"SFZ (*.sfz)")
		if filename:
			self.sfz_filename = filename
			set_setting(KEY_RECENT_SAVE_DIR, dirname(self.sfz_filename))
			self.save()

	def save(self):
		with open(self.sfz_filename, 'w', encoding = 'utf-8') as fob:
			self.kit.write(fob)
		self.statusbar.showMessage(f'Saved {self.sfz_filename}', MESSAGE_TIMEOUT)
		self.kit.clear_dirty()
		self.update_window_title()

	# -----------------------------------------------------------------
	# Main three widget slots
	# (InstrumentList, FilesExplorer, SamplesExplorer)

	@pyqtSlot(int)
	def slot_current_sample_widget_changed(self, _):
		"""
		Instrument selection is made in InstrumentList

		When the selection changes, the InstrumentWidget switches to the corresponding
		row. When that happens, its "currentChanged" signal triggers this slot.
		"""
		instrument = self.stk_instrument_widget.currentWidget().instrument
		for widget in [self.files_explorer, self.samples_explorer]:
			widget.set_current_instrument(instrument)

	@pyqtSlot(list)
	def slot_use_samples(self, paths):
		"""
		Emitted from
			SamplesExplorer.sig_use_samples
			FilesExplorer.sig_use_samples
		paths is a list of str
		"""
		for path in paths:
			self.stk_instrument_widget.currentWidget().add_sample(path)

	# -----------------------------------------------------------------
	# Audio previews

	@pyqtSlot(int, int)
	def slot_trackpad_pressed(self, pitch, velocity):
		self.audio.synth.noteon(10, pitch, velocity) # pylint: disable = no-member

	@pyqtSlot(int)
	def slot_trackpad_release(self, pitch):
		self.audio.synth.noteoff(10, pitch) # pylint: disable = no-member

	@pyqtSlot(int, bool)
	def slot_updating(self, pitch, _):
		"""
		Triggered by InstrumentWidget.sig_updating
		"""
		self.statusbar.showMessage(f'Preparing to update {MIDI_DRUM_NAMES[pitch]}...')
		self.update_window_title()

	@pyqtSlot(int, bool)
	def slot_updated(self, pitch, has_samples):
		self.audio.load_kit(self.kit)
		index = self.stk_instrument_widget.currentIndex()
		has_samples = self.stk_instrument_widget.currentWidget().has_samples()
		self.instrument_list.update_instrument(index, has_samples)
		self.statusbar.showMessage(f'Updated {MIDI_DRUM_NAMES[pitch]}', MESSAGE_TIMEOUT)

	# -----------------------------------------------------------------
	# JACK audio / source / sink management

	@pyqtSlot(int)
	def slot_jack_ready(self, samplerate):
		self.lbl_jack_state.setText(f'JACK samplerate: {samplerate}')

	@pyqtSlot()
	def slot_jack_down(self):
		self.lbl_jack_state.setText('JACK is down')

	@pyqtSlot()
	def slot_sources_changed(self):
		with SigBlock(self.cmb_midi_srcs):
			self.cmb_midi_srcs.clear()
			self.cmb_midi_srcs.addItem('')
			for port in self.audio.conn_man.output_ports():
				if port.is_midi:
					self.cmb_midi_srcs.addItem(port.name)
			if self.audio.synth.connected_midi_src_port:
				self.cmb_midi_srcs.setCurrentText(self.audio.midi_src)

	@pyqtSlot()
	def slot_sinks_changed(self):
		with SigBlock(self.cmb_audio_sinks):
			self.cmb_audio_sinks.clear()
			self.cmb_audio_sinks.addItem('')
			valid_clients = set(
				port.client_name for port in self.audio.conn_man.input_ports()
				if port.is_audio )
			for client in valid_clients:
				self.cmb_audio_sinks.addItem(client)
			if self.audio.synth.connected_audio_sink_ports:
				self.cmb_audio_sinks.setCurrentText(self.audio.audio_sink)

	@pyqtSlot(str)
	def slot_midi_connected(self, port_name):
		self.statusbar.showMessage(f'Connected to "{port_name}"', MESSAGE_TIMEOUT)


#  end kitstarter/kitstarter/gui/main_window.py
