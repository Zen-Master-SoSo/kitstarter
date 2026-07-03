#  kitstarter/kitstarter/gui/samples_explorer.py
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
import logging
from os.path import join, dirname, basename
from functools import lru_cache
from soundfile import SoundFile, LibsndfileError
from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint
from PyQt5.QtWidgets import QApplication, QWidget, QMenu, QAction, QListWidget, QListWidgetItem
from qt_extras import SigBlock, ShutUpQT
from midi_notes import MIDI_DRUM_NAMES
from kitstarter import (
	set_setting, get_setting, PACKAGE_DIR, KEY_FILTER_INST, KEY_SHOW_SELECTED, KEY_SHOW_PINNED)
from kitstarter.pindb import PinDatabase


class SamplesExplorer(QWidget):

	sig_use_samples = pyqtSignal(list)
	sig_play_soundfile = pyqtSignal(SoundFile)
	sig_stop_playing = pyqtSignal()

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'samples_explorer.ui'), self)
		self.pindb = PinDatabase()
		self.current_instrument = None
		self.jack_sample_rate = None
		self.file_selection_infos = []
		self.icon_sample_okay = QIcon(join(PACKAGE_DIR, 'res', 'sample-okay.svg'))
		self.icon_sample_mismatch = QIcon(join(PACKAGE_DIR, 'res', 'sample-mismatch.svg'))
		self.icon_sample_pinned = QIcon(join(PACKAGE_DIR, 'res', 'pin.svg'))
		self.icon_sample_unpinned = QIcon(join(PACKAGE_DIR, 'res', 'unpinned.svg'))
		self.icon_use_sample = QIcon.fromTheme("list-add")
		self.icon_copy = QIcon.fromTheme("edit-copy")
		self.icon_sample_err = QIcon.fromTheme('dialog-warning')
		self.chk_filter_instrument.stateChanged.connect(self.slot_filter_checked)
		self.chk_show_pinned.stateChanged.connect(self.slot_show_pinned_checked)
		self.chk_show_selected.stateChanged.connect(self.slot_show_selected_checked)
		self.lst_samples.itemPressed.connect(self.slot_sample_pressed)
		self.lst_samples.mouseReleaseEvent = self.samples_mouse_release
		self.lst_samples.setContextMenuPolicy(Qt.CustomContextMenu)
		self.lst_samples.customContextMenuRequested.connect(self.slot_context_menu)
		with SigBlock(self.chk_filter_instrument, self.chk_show_selected, self.chk_show_pinned):
			self.chk_filter_instrument.setChecked(get_setting(KEY_FILTER_INST, True, bool))
			self.chk_show_selected.setChecked(get_setting(KEY_SHOW_SELECTED, True, bool))
			self.chk_show_pinned.setChecked(get_setting(KEY_SHOW_PINNED, True, bool))

	def set_current_instrument(self, instrument):
		"""
		Called from MainWindow.
		"instrument" is the stack widget's current instrument.
		"""
		self.current_instrument = instrument
		self.chk_filter_instrument.setText(f'Filter "{instrument.name}"')
		if self.chk_filter_instrument.isChecked():
			self.update_list()

	@pyqtSlot(list)
	def slot_files_selection_changed(self, sample_infos):
		"""
		SFZ selection is made in FilesExplorer.
		"""
		self.file_selection_infos = sample_infos
		self.update_list()

	@pyqtSlot(int)
	def slot_filter_checked(self, state):
		set_setting(KEY_FILTER_INST, bool(state))
		self.update_list()

	@pyqtSlot(int)
	def slot_show_selected_checked(self, state):
		set_setting(KEY_SHOW_SELECTED, bool(state))
		self.update_list()

	@pyqtSlot(int)
	def slot_show_pinned_checked(self, state):
		set_setting(KEY_SHOW_PINNED, bool(state))
		self.update_list()

	@pyqtSlot(QPoint)
	def slot_context_menu(self, position):
		"""
		Display context menu for self.lst_samples
		"""
		menu = QMenu(self)
		sample_infos = [ item.data(Qt.UserRole) for item in self.lst_samples.selectedItems() ]
		pinned = [ self.pindb.is_pinned(info.path) for info in sample_infos ]
		pitch = self.current_instrument.pitch

		if len(sample_infos):

			def pin():
				for info in sample_infos:
					self.pindb.pin(info.path, info.pitch, info.sfz_path)
					self.existing_item_from_path(info.path).setIcon(self.icon_sample_pinned)
			if not all(pinned):
				action = QAction('Pin', self)
				action.setIcon(self.icon_sample_unpinned)
				action.triggered.connect(pin)
				menu.addAction(action)

			def unpin():
				for info in sample_infos:
					self.pindb.unpin(info.path)
					self.set_unpinned_icon(self.existing_item_from_path(info.path))
			if any(pinned):
				action = QAction('Unpin', self)
				action.setIcon(self.icon_sample_pinned)
				action.triggered.connect(unpin)
				menu.addAction(action)

			def use_samples():
				self.sig_use_samples.emit([info.path for info in sample_infos])
			title = 'these samples' if len(sample_infos) > 1 else f'"{basename(sample_infos[0].path)}"'
			action = QAction(f'Use {title} for "{MIDI_DRUM_NAMES[pitch]}"', self)
			action.setIcon(self.icon_use_sample)
			action.triggered.connect(use_samples)
			menu.addAction(action)

			def copy_paths():
				QApplication.instance().clipboard().setText(
					"\n".join(info.path for info in sample_infos))
			action = QAction('Copy path(s) to clipboard', self)
			action.setIcon(self.icon_copy)
			action.triggered.connect(copy_paths)
			menu.addAction(action)

		if len(sample_infos) < self.lst_samples.count():
			def select_all():
				self.lst_samples.selectAll()
			action = QAction('Select all', self)
			action.triggered.connect(select_all)
			menu.addAction(action)

		menu.exec(self.lst_samples.mapToGlobal(position))

	@pyqtSlot(QListWidgetItem)
	def slot_sample_pressed(self, list_item):
		if QApplication.mouseButtons() == Qt.LeftButton:
			soundfile = self.soundfile(list_item.data(Qt.UserRole).path)
			if soundfile:
				self.sig_play_soundfile.emit(soundfile)

	def samples_mouse_release(self, event):
		self.sig_stop_playing.emit()
		QListWidget.mouseReleaseEvent(self.lst_samples, event)

	def update_list(self):
		QApplication.setOverrideCursor(Qt.WaitCursor)
		self.lst_samples.clear()
		sample_infos = []
		added_paths = []
		if self.chk_show_pinned.isChecked():
			sample_infos.extend(self.pindb.all_pinned())
			added_paths = [ info.path for info in sample_infos ]
		if self.chk_show_selected.isChecked():
			for info in self.file_selection_infos:
				if info.path in added_paths:
					continue
				added_paths.append(info.path)
				sample_infos.append(info)
		if self.current_instrument and self.chk_filter_instrument.isChecked():
			sample_infos = [ info for info in sample_infos
				if info.pitch is None or info.pitch == self.current_instrument.pitch ]
		sample_infos.sort(key = lambda info: basename(info.path).lower())
		for info in sample_infos:
			list_item = QListWidgetItem(self.lst_samples)
			list_item.setText(basename(info.path))
			list_item.setData(Qt.UserRole, info)
			if self.pindb.is_pinned(info.path):
				list_item.setIcon(self.icon_sample_pinned)
			else:
				self.set_unpinned_icon(list_item)
		QApplication.restoreOverrideCursor()

	def set_unpinned_icon(self, list_item):
		entry = list_item.data(Qt.UserRole)
		soundfile = self.soundfile(entry.path)
		if soundfile is None:
			list_item.setIcon(self.icon_sample_err)
			list_item.setToolTip('Error reading soundfile')
		else:
			if self.jack_sample_rate:
				list_item.setIcon(
					self.icon_sample_okay
					if soundfile.samplerate == self.jack_sample_rate
					else self.icon_sample_mismatch)
			list_item.setToolTip(f'{entry.path}\nSample rate: {soundfile.samplerate} Hz')

	def existing_item_from_path(self, path):
		for item in self.lst_samples.findItems(basename(path), Qt.MatchExactly):
			if item.data(Qt.UserRole).path == path:
				return item
		return None

	@pyqtSlot(int)
	def slot_jack_ready(self, samplerate):
		self.jack_sample_rate = samplerate
		self.update_list()

	@lru_cache(maxsize = 200)
	def soundfile(self, path):
		try:
			return SoundFile(path)
		except LibsndfileError as err:
			logging.error(err)
			return None


#  end kitstarter/kitstarter/gui/samples_explorer.py
