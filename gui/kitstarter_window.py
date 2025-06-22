#  kitstarter/gui/kitstarter_window.py
#
#  Copyright 2025 liyang <liyang@veronica>
#
import os, logging, platform, subprocess, tempfile
from os.path import join, dirname, basename, abspath, splitext
from functools import lru_cache

from PyQt5 import 			uic
from PyQt5.QtCore import	Qt, pyqtSignal, pyqtSlot, QPoint, QDir, QItemSelection, QTimer
from PyQt5.QtGui import		QIcon
from PyQt5.QtWidgets import	QApplication, QMainWindow, QFileDialog, QListWidget, QListWidgetItem, \
							QFileSystemModel, QAbstractItemView, QMenu, QAction, QComboBox, QLabel

import soundfile as sf
from midi_notes import MIDI_DRUM_NAMES
from liquiphy import LiquidSFZ
from jack_connection_manager import JackConnectionManager
from jack_audio_player import JackAudioPlayer
from qt_extras import SigBlock, ShutUpQT
from sfzen.drumkits import Drumkit, iter_pitch_by_group

from kitstarter import	settings, KEY_FILES_ROOT, KEY_FILES_CURRENT
from kitstarter.starter_kits import StarterKit
from kitstarter.gui import GeometrySaver
from kitstarter.gui.samples_widget import SamplesWidget, init_paint_resources

FILE_FILTERS = ['*.ogg', '*.wav', '*.flac', '*.sfz']
SAMPLE_EXTENSIONS = ['.ogg', '.wav', '.flac']
SYNTH_NAME = 'liquidsfz'
MESSAGE_TIMEOUT = 2500


class MainWindow(QMainWindow, GeometrySaver):

	sig_ports_complete = pyqtSignal()

	def __init__(self):
		super().__init__()
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'kitstarter_window.ui'), self)
		init_paint_resources()
		self.restore_geometry()
		font = self.lst_instruments.font()
		font.setPointSizeF(11.5)
		self.lst_instruments.setFont(font)
		self.lst_instruments.setFixedWidth(180)
		self.kit = StarterKit()
		# Setup JackConnectionManager
		self.conn_man = JackConnectionManager()
		self.conn_man.on_error(self.jack_error)
		self.conn_man.on_xrun(self.jack_xrun)
		self.conn_man.on_shutdown(self.jack_shutdown)
		self.conn_man.on_client_registration(self.jack_client_registration)
		self.conn_man.on_port_registration(self.jack_port_registration)
		# Setup filname, tempfile, synth, audio player
		self.sfz_filename = None
		_, self.tempfile = tempfile.mkstemp(suffix='.sfz')
		self.synth = JackLiquidSFZ(self.tempfile)
		self.audio_player = None	# Instantiated after initial paint delay
		self.current_midi_source = None
		self.current_audio_sink = None
		# Startup paths
		root_path = settings().value(KEY_FILES_ROOT, QDir.homePath())
		current_path = settings().value(KEY_FILES_CURRENT, QDir.homePath())
		self.files_model = QFileSystemModel()
		self.files_model.setRootPath(root_path)
		self.files_model.setNameFilters(FILE_FILTERS)
		self.tree_sfz_files.setModel(self.files_model)
		self.tree_sfz_files.hideColumn(1)
		self.tree_sfz_files.hideColumn(2)
		self.tree_sfz_files.hideColumn(3)
		self.tree_sfz_files.setRootIndex(self.files_model.index(root_path))
		index = self.files_model.index(current_path)
		self.tree_sfz_files.setCurrentIndex(index)
		self.tree_sfz_files.scrollTo(index, QAbstractItemView.PositionAtBottom)
		# Setup instrument list
		for pitch in iter_pitch_by_group():
			list_item = QListWidgetItem(self.lst_instruments)
			list_item.setText(MIDI_DRUM_NAMES[pitch])
			list_item.setIcon(QIcon.fromTheme('dialog-question'))
			list_item.setData(Qt.UserRole, pitch)
			samples_widget = SamplesWidget(self, self.kit.instrument(pitch))
			samples_widget.sig_updating.connect(self.slot_updating)
			samples_widget.sig_updated.connect(self.slot_updated)
			samples_widget.sig_mouse_press.connect(self.slot_trackpad_pressed)
			samples_widget.sig_mouse_release.connect(self.slot_trackpad_release)
			self.stk_samples_widgets.addWidget(samples_widget)
		# Remove first (placeholder) widget from QStackedWidget
		widget = self.stk_samples_widgets.widget(0)
		self.stk_samples_widgets.removeWidget(widget)
		widget.deleteLater()
		# Setup statusbar
		self.cmb_midi_srcs = QComboBox(self.statusbar)
		self.statusbar.addPermanentWidget(QLabel('Src:', self.statusbar))
		self.statusbar.addPermanentWidget(self.cmb_midi_srcs)
		self.cmb_audio_sinks = QComboBox(self.statusbar)
		self.statusbar.addPermanentWidget(QLabel('Sink:', self.statusbar))
		self.statusbar.addPermanentWidget(self.cmb_audio_sinks)
		# Connect signals
		self.sig_ports_complete.connect(self.slot_ports_complete)
		self.lst_instruments.currentRowChanged.connect(self.stk_samples_widgets.setCurrentIndex)
		self.tree_sfz_files.selectionModel().selectionChanged.connect(self.slot_files_selection_changed)
		self.tree_sfz_files.setContextMenuPolicy(Qt.CustomContextMenu)
		self.tree_sfz_files.customContextMenuRequested.connect(self.slot_files_context_menu)
		self.cmb_sfz_instrument.currentIndexChanged.connect(self.slot_sfz_inst_curr_changed)
		self.lst_samples.itemPressed.connect(self.slot_sample_pressed)
		self.lst_samples.mouseReleaseEvent = self.samples_mouse_release
		self.lst_samples.setContextMenuPolicy(Qt.CustomContextMenu)
		self.lst_samples.customContextMenuRequested.connect(self.slot_samples_context_menu)
		self.cmb_midi_srcs.currentTextChanged.connect(self.slot_midi_src_changed)
		self.cmb_audio_sinks.currentTextChanged.connect(self.slot_audio_sink_changed)
		self.action_new.triggered.connect(self.slot_new)
		self.action_save.triggered.connect(self.slot_save)
		self.action_save_as.triggered.connect(self.slot_save_as)
		self.action_exit.triggered.connect(self.close)
		# Fill sink/source menus:
		self.fill_cmb_sources()
		self.fill_cmb_sinks()
		# Set currently selected file
		QTimer.singleShot(250, self.layout_complete)

	def layout_complete(self):
		self.synth.start()
		self.audio_player = JackAudioPlayer()
		index = self.tree_sfz_files.currentIndex()
		self.tree_sfz_files.scrollTo(index, QAbstractItemView.PositionAtTop)
		self.slot_files_selection_changed()

	def closeEvent(self, _):
		self.synth.quit()
		self.save_geometry()
		os.unlink(self.tempfile)

	# -----------------------------------------------------------------
	# JACK ports / clients management

	def jack_error(self, error_message):
		logging.error('JACK ERROR: %s', error_message)

	def jack_xrun(self, xruns):
		pass

	def jack_shutdown(self):
		logging.error('JACK is shutting down')
		self.close()

	def jack_client_registration(self, client_name, action):
		if action:
			if SYNTH_NAME in client_name:
				self.synth.client_name = client_name
		else:
			if self.cmb_audio_sinks.findText(client_name, Qt.MatchStartsWith) > -1:
				self.fill_cmb_sinks()
			elif self.cmb_midi_srcs.findText(client_name, Qt.MatchStartsWith) > -1:
				self.fill_cmb_sources()

	def jack_port_registration(self, port, action):
		if action and self.synth.client_name in port.name:
			if port.is_input and port.is_midi:
				self.synth.input_port = port
			elif port.is_output and port.is_audio:
				self.synth.output_ports.append(port)
			else:
				logging.error('Incorrect port type: %s', port)
			if self.synth.input_port and len(self.synth.output_ports) == 2:
				self.sig_ports_complete.emit()
		else:
			if port.is_output and port.is_midi:
				self.fill_cmb_sources()
			elif port.is_input and port.is_audio:
				self.fill_cmb_sinks()

	@pyqtSlot()
	def slot_ports_complete(self):
		"""
		Called in response to sig_ports_complete since sig_ports_complete is generated
		in another thread,
		"""
		self.connect_midi_source()
		self.connect_audio_sink()

	# -----------------------------------------------------------------
	# Source / sink management

	def fill_cmb_sources(self):
		with SigBlock(self.cmb_midi_srcs):
			self.cmb_midi_srcs.clear()
			self.cmb_midi_srcs.addItem('')
			for port in self.conn_man.output_ports():
				if port.is_midi:
					self.cmb_midi_srcs.addItem(port.name)
			if self.current_midi_source and \
				self.cmb_midi_srcs.findText(self.current_midi_source, Qt.MatchExactly):
				self.cmb_midi_srcs.setCurrentText(self.current_midi_source)

	def fill_cmb_sinks(self):
		with SigBlock(self.cmb_audio_sinks):
			self.cmb_audio_sinks.clear()
			self.cmb_audio_sinks.addItem('')
			valid_clients = set(port.client_name \
				for port in self.conn_man.input_ports() \
				if port.is_audio)
			for client in valid_clients:
				self.cmb_audio_sinks.addItem(client)
			if self.current_audio_sink and \
				self.cmb_audio_sinks.findText(self.current_audio_sink, Qt.MatchExactly):
				self.cmb_audio_sinks.setCurrentText(self.current_audio_sink)

	@pyqtSlot(str)
	def slot_midi_src_changed(self, value):
		if self.current_midi_source:
			self.conn_man.disconnect_by_name(self.current_midi_source, self.synth.input_port.name)
		self.current_midi_source = value
		self.connect_midi_source()

	@pyqtSlot(str)
	def slot_audio_sink_changed(self, value):
		if self.current_audio_sink:
			for src_port in self.synth.output_ports:
				for dest_port in self.conn_man.get_port_connections(src_port):
					self.conn_man.disconnect(src_port, dest_port)
		self.current_audio_sink = value
		self.connect_audio_sink()

	def connect_midi_source(self):
		if self.current_midi_source:
			self.conn_man.connect_by_name(self.current_midi_source, self.synth.input_port.name)

	def connect_audio_sink(self):
		if self.current_audio_sink:
			audio_sink_ports = [ port for port \
				in self.conn_man.input_ports() \
				if port.client_name == self.current_audio_sink ]
			for src_port, dest_port in zip(self.synth.output_ports, audio_sink_ports):
				self.conn_man.connect(src_port, dest_port)

	# -----------------------------------------------------------------
	# Instrument list management

	def iter_instrument_list(self):
		for row in range(self.lst_instruments.count()):
			yield self.lst_instruments.item(row)

	def current_inst_pitch(self):
		return self.stk_samples_widgets.currentWidget().instrument.pitch

	# -----------------------------------------------------------------
	# Cached objects

	@lru_cache
	def drumkit(self, path):
		return Drumkit(path)

	@lru_cache
	def soundfile(self, path):
		return sf.SoundFile(path)

	# -----------------------------------------------------------------
	# Menu handlers

	@pyqtSlot()
	def slot_new(self):
		self.kit = StarterKit()
		for index in range(self.stk_samples_widgets.count()):
			self.stk_samples_widgets.widget(index).clear()

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
		filename = QFileDialog.getSaveFileName(self, 'Save as .sfz ...', '', "SFZ (*.sfz)")
		logging.debug(filename)
		if filename:
			self.sfz_filename = filename
			self.save()

	def save(self):
		with open(self.sfz_filename, 'w', encoding = 'utf-8') as fob:
			self.kit.write(fob)
		self.statusbar.showMessage(f'Saved {self.sfz_filename}', MESSAGE_TIMEOUT)

	# -----------------------------------------------------------------
	# SFZ / samples files management

	@pyqtSlot(QItemSelection, QItemSelection)
	def slot_files_selection_changed(self, *_):
		QApplication.setOverrideCursor(Qt.WaitCursor)
		self.lst_samples.clear()
		prev_text = self.cmb_sfz_instrument.currentText()
		with SigBlock(self.cmb_sfz_instrument):
			self.cmb_sfz_instrument.clear()
			self.lbl_sfz_inst_heading.setEnabled(False)
			for index in self.tree_sfz_files.selectedIndexes():
				path = self.files_model.filePath(index)
				ext = splitext(path)[-1]
				settings().setValue(KEY_FILES_CURRENT, path)
				if not self.files_model.isDir(index):
					if ext == '.sfz':
						for inst in self.drumkit(path).instruments():
							if self.cmb_sfz_instrument.findData(inst.pitch) == -1:
								self.cmb_sfz_instrument.addItem(inst.name, inst.pitch)
					elif ext in SAMPLE_EXTENSIONS:
						self.lst_samples_append(path)
			if bool(self.cmb_sfz_instrument.count()):
				self.cmb_sfz_instrument.insertItem(0, '[all]', 0)
				self.lbl_sfz_inst_heading.setEnabled(True)
		if self.cmb_sfz_instrument.findText(prev_text, Qt.MatchExactly) > -1:
			self.cmb_sfz_instrument.setCurrentText(prev_text)
		else:
			self.cmb_sfz_instrument.setCurrentIndex(0)
		QApplication.restoreOverrideCursor()

	@pyqtSlot(int)
	def slot_sfz_inst_curr_changed(self, _):
		if self.cmb_sfz_instrument.count():
			QApplication.setOverrideCursor(Qt.WaitCursor)
			self.lst_samples.clear()
			pitch = self.cmb_sfz_instrument.currentData()
			for index in self.tree_sfz_files.selectedIndexes():
				if not self.files_model.isDir(index):
					path = abspath(self.files_model.filePath(index))
					ext = splitext(path)[-1]
					if ext == '.sfz':
						if pitch > 0:
							self.append_sfz_samples(self.drumkit(path).instrument(pitch))
						else:
							for instrument in self.drumkit(path).instruments():
								self.append_sfz_samples(instrument)
			QApplication.restoreOverrideCursor()

	def append_sfz_samples(self, instrument):
		for sample in instrument.samples():
			existing_items = self.lst_samples.findItems(sample.basename, Qt.MatchExactly)
			if len(existing_items) \
				and any(existing_item.data(Qt.UserRole).name == sample.abspath \
				for existing_item in existing_items):
				continue
			self.lst_samples_append(sample.abspath)

	def lst_samples_append(self, path):
		soundfile = self.soundfile(path)
		sfz_inst_item = QListWidgetItem(self.lst_samples)
		sfz_inst_item.setText(basename(path))
		sfz_inst_item.setData(Qt.UserRole, soundfile)
		s_samp = path + \
			f'\nThis file has a sample rate of {soundfile.samplerate} Hz,\n'
		if soundfile.samplerate != self.audio_player.client.samplerate:
			sfz_inst_item.setIcon(QIcon.fromTheme('face-sad'))
			sfz_inst_item.setToolTip(s_samp + \
				f'while the JACK server is running at {self.audio_player.client.samplerate} Hz')
		else:
			sfz_inst_item.setIcon(QIcon.fromTheme('face-cool'))
			sfz_inst_item.setToolTip(s_samp + 'the same as the JACK server')

	# -----------------------------------------------------------------
	# Context menus

	@pyqtSlot(QPoint)
	def slot_files_context_menu(self, position):
		"""
		Display context menu for self.tree_sfz_files
		"""
		indexes = self.tree_sfz_files.selectedIndexes()
		if len(indexes):
			menu = QMenu(self)
			paths = [ self.files_model.filePath(index) for index in indexes ]
			def copy_paths():
				QApplication.instance().clipboard().setText("\n".join(paths))
			action = QAction('Copy path' if len(indexes) == 1 else 'Copy paths', self)
			action.triggered.connect(copy_paths)
			menu.addAction(action)
			pitch = self.current_inst_pitch()
			if all(splitext(path)[-1] in SAMPLE_EXTENSIONS for path in paths):
				def use_samples():
					for path in paths:
						self.stk_samples_widgets.currentWidget().append(path)
				action = QAction(f'Use for "{MIDI_DRUM_NAMES[pitch]}"', self)
				action.triggered.connect(use_samples)
				menu.addAction(action)
			def open_file():
				if platform.system() == "Windows":
					os.startfile(paths[0])
				elif platform.system() == "Darwin":
					subprocess.Popen(["open", paths[0]])
				else:
					subprocess.Popen(["xdg-open", paths[0]])
			if len(indexes) == 1:
				action = QAction('Open in external program ...')
				action.triggered.connect(open_file)
				menu.addAction(action)
			menu.exec(self.tree_sfz_files.mapToGlobal(position))

	@pyqtSlot(QPoint)
	def slot_samples_context_menu(self, position):
		"""
		Display context menu for self.lst_samples
		"""
		menu = QMenu(self)
		items = self.lst_samples.selectedItems()
		if len(items) < self.lst_samples.count():
			def select_all():
				self.lst_samples.selectAll()
			action = QAction('Select all', self)
			action.triggered.connect(select_all)
			menu.addAction(action)
		if len(items):
			def copy_paths():
				QApplication.instance().clipboard().setText("\n".join(
					item.data(Qt.UserRole).name for item in items))
			action = QAction('Copy path(s) to clipboard', self)
			action.triggered.connect(copy_paths)
			menu.addAction(action)
		pitch = self.current_inst_pitch()
		def use_samples():
			for item in items:
				self.stk_samples_widgets.currentWidget().append(item.data(Qt.UserRole).name)
		action = QAction(f'Use sample(s) for "{MIDI_DRUM_NAMES[pitch]}"', self)
		action.triggered.connect(use_samples)
		menu.addAction(action)
		menu.exec(self.lst_samples.mapToGlobal(position))

	# -----------------------------------------------------------------
	# Previews

	@pyqtSlot(QListWidgetItem)
	def slot_sample_pressed(self, list_item):
		soundfile = list_item.data(Qt.UserRole)
		soundfile.seek(0)
		self.audio_player.play_python_soundfile(soundfile)

	def samples_mouse_release(self, event):
		self.audio_player.stop()
		super(QListWidget, self.lst_samples).mouseReleaseEvent(event)

	@pyqtSlot(int, int)
	def slot_trackpad_pressed(self, pitch, velocity):
		self.synth.noteon(10, pitch, velocity)

	@pyqtSlot(int)
	def slot_trackpad_release(self, pitch):
		self.synth.noteoff(10, pitch)

	# -----------------------------------------------------------------
	# Samples update management

	@pyqtSlot()
	def slot_updating(self):
		self.statusbar.showMessage('Preparing to update ...')
		for list_item in self.iter_instrument_list():
			instrument = self.kit.instrument(list_item.data(Qt.UserRole))
			list_item.setIcon(QIcon.fromTheme(
				'dialog-information' if len(instrument.samples) else 'dialog-question'))

	@pyqtSlot()
	def slot_updated(self):
		with open(self.tempfile, 'w', encoding = 'utf-8') as fob:
			self.kit.write(fob)
		self.synth.load(self.tempfile)
		self.statusbar.showMessage('Updated', MESSAGE_TIMEOUT)


class JackLiquidSFZ(LiquidSFZ):
	"""
	Wraps a LiquidSFZ instance in order to hold references to jacklib ports created
	by JackConnectionManager.
	"""

	def __init__(self, filename):
		self.client_name = None
		self.input_port = None
		self.output_ports = []
		super().__init__(filename, defer_start = True)


#  end kitstarter/gui/kitstarter_window.py
