#  kitstarter/gui/main_window.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
#
import os, logging, platform, subprocess, tempfile
from os.path import join, dirname, basename, abspath, splitext
from functools import lru_cache
from collections import namedtuple

from PyQt5 import 			uic
from PyQt5.QtCore import	Qt, pyqtSignal, pyqtSlot, QPoint, QDir, QItemSelection, QTimer
from PyQt5.QtGui import		QIcon
from PyQt5.QtWidgets import	QApplication, QMainWindow, QFileDialog, QListWidget, QListWidgetItem, \
							QFileSystemModel, QAbstractItemView, QMenu, QAction, QComboBox, QLabel

import soundfile as sf
from soundfile import LibsndfileError
from midi_notes import MIDI_DRUM_NAMES
from liquiphy import LiquidSFZ
from conn_jack import JackConnectionManager
from jack_audio_player import JackAudioPlayer
from qt_extras import SigBlock, ShutUpQT
from sfzen.drumkits import Drumkit, iter_pitch_by_group

from kitstarter import	settings, xdg_open, \
						APPLICATION_NAME, PACKAGE_DIR, KEY_RECENT_FOLDER, \
						KEY_FILES_ROOT, KEY_FILES_CURRENT, KEY_MIDI_SOURCE, KEY_AUDIO_SINK
from kitstarter.starter_kits import StarterKit
from kitstarter.pindb import PinDatabase
from kitstarter.gui.samples_widget import SamplesWidget, init_paint_resources

SampleEntry = namedtuple('Sample', ['path', 'pitch', 'sfz_path', 'soundfile'])

FILE_FILTERS = ['*.ogg', '*.wav', '*.flac', '*.sfz']
SAMPLE_EXTENSIONS = ['.ogg', '.wav', '.flac']
SYNTH_NAME = 'liquidsfz'
MESSAGE_TIMEOUT = 3000


class MainWindow(QMainWindow):

	sig_ports_complete = pyqtSignal()

	def __init__(self, filename):
		super().__init__()
		self.sfz_filename = filename
		self.kit = StarterKit()
		# Setup GUI
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'main_window.ui'), self)
		init_paint_resources()
		self.restore_geometry()
		# Setup fonts and icons
		font = self.lst_instruments.font()
		font.setPointSizeF(11.5)
		self.lst_instruments.setFont(font)
		self.lst_instruments.setFixedWidth(180)
		self.icon_complete = QIcon(os.path.join(PACKAGE_DIR, 'res', 'inst-complete.svg'))
		self.icon_incomplete = QIcon(os.path.join(PACKAGE_DIR, 'res', 'inst-incomplete.svg'))
		self.icon_sample_okay = QIcon(os.path.join(PACKAGE_DIR, 'res', 'sample-okay.svg'))
		self.icon_sample_mismatch = QIcon(os.path.join(PACKAGE_DIR, 'res', 'sample-mismatch.svg'))
		self.icon_sample_pinned = QIcon(os.path.join(PACKAGE_DIR, 'res', 'pin.svg'))
		self.icon_sample_err = QIcon.fromTheme('dialog-warning')
		# Setup JackConnectionManager
		self.conn_man = JackConnectionManager()
		self.conn_man.on_error(self.jack_error)
		self.conn_man.on_xrun(self.jack_xrun)
		self.conn_man.on_shutdown(self.jack_shutdown)
		self.conn_man.on_client_registration(self.jack_client_registration)
		self.conn_man.on_port_registration(self.jack_port_registration)
		# Setup tempfile, synth, audio player, pindb
		self.pindb = PinDatabase()
		_, self.tempfile = tempfile.mkstemp(suffix='.sfz')
		self.synth = JackLiquidSFZ(self.tempfile)
		self.audio_player = None	# Instantiated after initial paint delay
		# Startup paths
		root_path = settings().value(KEY_FILES_ROOT, QDir.homePath())
		current_path = settings().value(KEY_FILES_CURRENT, QDir.homePath())
		self.files_model = QFileSystemModel()
		self.files_model.setRootPath(root_path)
		self.files_model.setNameFilters(FILE_FILTERS)
		self.tree_files.setModel(self.files_model)
		self.tree_files.hideColumn(1)
		self.tree_files.hideColumn(2)
		self.tree_files.hideColumn(3)
		self.tree_files.setRootIndex(self.files_model.index(root_path))
		index = self.files_model.index(current_path)
		self.tree_files.setCurrentIndex(index)
		self.tree_files.scrollTo(index, QAbstractItemView.PositionAtBottom)
		# Setup instrument list
		for pitch in iter_pitch_by_group():
			list_item = QListWidgetItem(self.lst_instruments)
			list_item.setText(MIDI_DRUM_NAMES[pitch])
			list_item.setIcon(self.icon_incomplete)
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
		self.lst_instruments.currentRowChanged.connect(self.slot_instrument_changed)
		self.tree_files.selectionModel().selectionChanged.connect(self.slot_files_selection_changed)
		self.tree_files.setContextMenuPolicy(Qt.CustomContextMenu)
		self.tree_files.customContextMenuRequested.connect(self.slot_files_context_menu)
		self.chk_filter_instrument.stateChanged.connect(self.slot_filter_checked)
		self.chk_show_pinned.stateChanged.connect(self.slot_show_pinned_checked)
		self.chk_show_selected.stateChanged.connect(self.slot_show_selected_checked)
		self.lst_samples.itemPressed.connect(self.slot_sample_pressed)
		self.lst_samples.mouseReleaseEvent = self.samples_mouse_release
		self.lst_samples.setContextMenuPolicy(Qt.CustomContextMenu)
		self.lst_samples.customContextMenuRequested.connect(self.slot_samples_context_menu)
		self.cmb_midi_srcs.currentTextChanged.connect(self.slot_midi_src_changed)
		self.cmb_audio_sinks.currentTextChanged.connect(self.slot_audio_sink_changed)
		self.action_new.triggered.connect(self.slot_new)
		self.action_open.triggered.connect(self.slot_open)
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
		index = self.tree_files.currentIndex()
		self.tree_files.scrollTo(index, QAbstractItemView.PositionAtTop)
		self.slot_files_selection_changed()
		if self.sfz_filename:
			self.load_sfz()

	def update_window_title(self):
		title = APPLICATION_NAME if self.sfz_filename is None \
			else f'{self.sfz_filename} - {APPLICATION_NAME}'
		if self.kit.is_dirty():
			title = '*' + title
		self.setWindowTitle(title)

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
		Called in response to sig_ports_complete since sig_ports_complete, emitted in
		"jack_port_registration" is triggered from another thread, not the GUI thread.
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
			if midi_src := settings().value(KEY_MIDI_SOURCE):
				if self.cmb_midi_srcs.findText(midi_src, Qt.MatchExactly):
					self.cmb_midi_srcs.setCurrentText(midi_src)

	def fill_cmb_sinks(self):
		with SigBlock(self.cmb_audio_sinks):
			self.cmb_audio_sinks.clear()
			self.cmb_audio_sinks.addItem('')
			valid_clients = set(port.client_name \
				for port in self.conn_man.input_ports() \
				if port.is_audio)
			for client in valid_clients:
				self.cmb_audio_sinks.addItem(client)
			if audio_sink := settings().value(KEY_AUDIO_SINK):
				if self.cmb_audio_sinks.findText(audio_sink, Qt.MatchExactly):
					self.cmb_audio_sinks.setCurrentText(audio_sink)

	@pyqtSlot(str)
	def slot_midi_src_changed(self, value):
		if midi_src := settings().value(KEY_MIDI_SOURCE):
			self.conn_man.disconnect_by_name(midi_src, self.synth.input_port.name)
		settings().setValue(KEY_MIDI_SOURCE, value)
		self.connect_midi_source()

	@pyqtSlot(str)
	def slot_audio_sink_changed(self, value):
		if audio_sink := settings().value(KEY_AUDIO_SINK):
			for src_port in self.synth.output_ports:
				for dest_port in self.conn_man.get_port_connections(src_port):
					self.conn_man.disconnect(src_port, dest_port)
		settings().setValue(KEY_AUDIO_SINK, value)
		self.connect_audio_sink()

	def connect_midi_source(self):
		if midi_src := settings().value(KEY_MIDI_SOURCE):
			self.conn_man.connect_by_name(midi_src, self.synth.input_port.name)

	def connect_audio_sink(self):
		if audio_sink := settings().value(KEY_AUDIO_SINK):
			audio_sink_ports = [ port for port \
				in self.conn_man.input_ports() \
				if port.client_name == audio_sink ]
			for src_port, dest_port in zip(self.synth.output_ports, audio_sink_ports):
				self.conn_man.connect(src_port, dest_port)
			for src_port, dest_port in zip(self.audio_player.output_ports, audio_sink_ports):
				self.conn_man.connect(src_port, dest_port)

	# -----------------------------------------------------------------
	# Instrument list management

	def iter_instrument_list(self):
		for row in range(self.lst_instruments.count()):
			yield self.lst_instruments.item(row)

	def current_inst_pitch(self):
		return self.stk_samples_widgets.currentWidget().instrument.pitch

	def update_instrument_list(self):
		for list_item in self.iter_instrument_list():
			instrument = self.kit.instrument(list_item.data(Qt.UserRole))
			list_item.setIcon(self.icon_complete if len(instrument.samples) else self.icon_incomplete)

	# -----------------------------------------------------------------
	# Cached objects

	@lru_cache
	def drumkit(self, path):
		return Drumkit(path)

	@lru_cache(maxsize = 200)
	def soundfile(self, path):
		try:
			return sf.SoundFile(path)
		except LibsndfileError as err:
			logging.error(err)
			return None

	# -----------------------------------------------------------------
	# Load / save / SamplesWidget / StarterKit management:

	def iterate_sample_widgets(self):
		for index in range(self.stk_samples_widgets.count()):
			yield self.stk_samples_widgets.widget(index)

	@pyqtSlot()
	def slot_new(self):
		for widget in self.iterate_sample_widgets():
			widget.clear()

	@pyqtSlot()
	def slot_open(self):
		filename, _ = QFileDialog.getOpenFileName(self,
			"Open .sfz file",
			settings().value(KEY_RECENT_FOLDER, ''),
			".SFZ files (*.sfz)"
		)
		if filename != '':
			self.sfz_filename = abspath(filename)
			settings().setValue(KEY_RECENT_FOLDER, dirname(self.sfz_filename))
			self.load_sfz()

	def load_sfz(self):
		self.kit = StarterKit(self.sfz_filename)
		for widget in self.iterate_sample_widgets():
			widget.load_instrument(self.kit.instrument(widget.instrument.pitch))
		self.update_instrument_list()
		self.synth_load_kit()
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
		filename, _ = QFileDialog.getSaveFileName(
			self,
			'Save as .sfz ...',
			'' if self.sfz_filename is None else self.sfz_filename,
			"SFZ (*.sfz)")
		if filename:
			self.sfz_filename = filename
			self.save()

	def save(self):
		with open(self.sfz_filename, 'w', encoding = 'utf-8') as fob:
			self.kit.write(fob)
		self.statusbar.showMessage(f'Saved {self.sfz_filename}', MESSAGE_TIMEOUT)
		self.kit.clear_dirty()
		self.update_window_title()

	# -----------------------------------------------------------------
	# file tree / sample display management

	@pyqtSlot(int)
	def slot_instrument_changed(self, index):
		self.chk_filter_instrument.setText('Filter "{}"'.format(
			self.lst_instruments.currentItem().text()))
		if self.chk_filter_instrument.isChecked():
			self.update_samples_list()

	@pyqtSlot(QItemSelection, QItemSelection)
	def slot_files_selection_changed(self, *_):
		path = self.files_model.filePath(self.tree_files.currentIndex())
		settings().setValue(KEY_FILES_CURRENT, path)
		self.update_samples_list()

	@pyqtSlot(int)
	def slot_show_pinned_checked(self, _):
		self.update_samples_list()

	@pyqtSlot(int)
	def slot_show_selected_checked(self, state):
		self.tree_files.setEnabled(state)
		self.update_samples_list()

	@pyqtSlot(int)
	def slot_filter_checked(self, _):
		self.update_samples_list()

	def update_samples_list(self):
		QApplication.setOverrideCursor(Qt.WaitCursor)
		self.lst_samples.clear()
		filter_samples = self.chk_filter_instrument.isChecked()
		pitch = self.current_inst_pitch() if filter_samples else None
		if self.chk_show_pinned.isChecked():
			pinned = self.pindb.pinned_by_pitch(pitch) \
				if filter_samples \
				else self.pindb.all_pinned()
			pinned.sort(key = lambda row: basename(row[0]))
			for row in pinned:
				self.lst_add_sample(*row)
		if self.chk_show_selected.isChecked():
			for index in self.tree_files.selectedIndexes():
				if not self.files_model.isDir(index):
					path = self.files_model.filePath(index)
					ext = splitext(path)[-1]
					if ext == '.sfz':
						drumkit = self.drumkit(path)
						if filter_samples:
							try:
								self.lst_add_instrument_samples(drumkit.instrument(pitch), pitch, path)
							except KeyError:
								self.statusbar.showMessage(
									f'Drumkit "{drumkit.name}" has no instrument pitch {pitch}',
									MESSAGE_TIMEOUT)
						else:
							for instrument in self.drumkit(path).instruments():
								self.lst_add_instrument_samples(instrument, pitch, path)
					elif not filter_samples and ext in SAMPLE_EXTENSIONS:
						self.lst_add_sample(path, pitch, None)
		QApplication.restoreOverrideCursor()

	def lst_add_instrument_samples(self, instrument, pitch, sfz_path):
		for sample in instrument.samples():
			self.lst_add_sample(sample.abspath, pitch, sfz_path)

	def lst_add_sample(self, path, pitch, sfz_path):
		if self.sample_item_by_path(path):
			return
		list_item = QListWidgetItem(self.lst_samples)
		list_item.setText(basename(path))
		list_item.setData(Qt.UserRole, SampleEntry(
			path, pitch, sfz_path,
			self.soundfile(path)))
		if self.pindb.is_pinned(path):
			list_item.setIcon(self.icon_sample_pinned)
		else:
			self.set_unpinned_icon(list_item)

	def set_unpinned_icon(self, list_item):
		entry = list_item.data(Qt.UserRole)
		if entry.soundfile is None:
			list_item.setIcon(self.icon_sample_err)
			list_item.setToolTip('ERROR READING SOUNDFILE')
		else:
			s_samp = entry.path + \
				f'\nThis file has a sample rate of {entry.soundfile.samplerate} Hz,\n'
			if entry.soundfile.samplerate != self.conn_man.samplerate:
				list_item.setIcon(self.icon_sample_mismatch)
				list_item.setToolTip(s_samp + \
					f'while the JACK server is running at {self.conn_man.samplerate} Hz')
			else:
				list_item.setIcon(self.icon_sample_okay)
				list_item.setToolTip(s_samp + 'the same as the JACK server')

	def sample_item_by_path(self, path):
		for item in self.lst_samples.findItems(basename(path), Qt.MatchExactly):
			if item.data(Qt.UserRole).path == path:
				return item
		return None

	# -----------------------------------------------------------------
	# Context menus

	@pyqtSlot(QPoint)
	def slot_files_context_menu(self, position):
		"""
		Display context menu for self.tree_files
		"""
		indexes = self.tree_files.selectedIndexes()
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
						self.stk_samples_widgets.currentWidget().add_sample(path)
				action = QAction(f'Use for "{MIDI_DRUM_NAMES[pitch]}"', self)
				action.triggered.connect(use_samples)
				menu.addAction(action)
			def open_file():
				xdg_open(paths[0])
			if len(indexes) == 1:
				action = QAction('Open in external program ...')
				action.triggered.connect(open_file)
				menu.addAction(action)
			menu.exec(self.tree_files.mapToGlobal(position))

	@pyqtSlot(QPoint)
	def slot_samples_context_menu(self, position):
		"""
		Display context menu for self.lst_samples
		"""
		menu = QMenu(self)
		entries = [ item.data(Qt.UserRole) for item in self.lst_samples.selectedItems() ]
		pinned = [ self.pindb.is_pinned(entry.path) for entry in entries ]
		pitch = self.current_inst_pitch()

		if len(entries):

			def pin():
				for entry in entries:
					self.pindb.pin(entry.path, entry.pitch, entry.sfz_path)
					self.sample_item_by_path(entry.path).setIcon(self.icon_sample_pinned)
			if not all(pinned):
				action = QAction('Pin', self)
				action.triggered.connect(pin)
				menu.addAction(action)

			def unpin():
				for entry in entries:
					self.pindb.unpin(entry.path)
					self.set_unpinned_icon(self.sample_item_by_path(entry.path))
			if any(pinned):
				action = QAction('Unpin', self)
				action.triggered.connect(unpin)
				menu.addAction(action)

			def use_samples():
				for entry in entries:
					self.stk_samples_widgets.currentWidget().add_sample(entry.path)
			title = 'these samples' if len(entries) > 1 else f'"{basename(entries[0].path)}"'
			action = QAction(f'Use {title} for "{MIDI_DRUM_NAMES[pitch]}"', self)
			action.triggered.connect(use_samples)
			menu.addAction(action)

			def copy_paths():
				QApplication.instance().clipboard().setText(
					"\n".join(entry.path for entry in entries))
			action = QAction('Copy path(s) to clipboard', self)
			action.triggered.connect(copy_paths)
			menu.addAction(action)

		if len(entries) < self.lst_samples.count():
			def select_all():
				self.lst_samples.selectAll()
			action = QAction('Select all', self)
			action.triggered.connect(select_all)
			menu.addAction(action)

		menu.exec(self.lst_samples.mapToGlobal(position))

	# -----------------------------------------------------------------
	# Previews

	@pyqtSlot(QListWidgetItem)
	def slot_sample_pressed(self, list_item):
		if QApplication.mouseButtons() == Qt.LeftButton:
			soundfile = list_item.data(Qt.UserRole).soundfile
			if soundfile:
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
		self.update_instrument_list()
		self.update_window_title()

	@pyqtSlot()
	def slot_updated(self):
		self.synth_load_kit()
		self.statusbar.showMessage('Updated', MESSAGE_TIMEOUT)

	def synth_load_kit(self):
		with open(self.tempfile, 'w', encoding = 'utf-8') as fob:
			self.kit.write(fob)
		self.synth.load(self.tempfile)


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


#  end kitstarter/gui/main_window.py
