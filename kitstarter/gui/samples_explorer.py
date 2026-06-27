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
from os.path import join, dirname, basename, splitext
from collections import namedtuple
from PyQt5 import uic
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint
from PyQt5.QtWidgets import QApplication, QWidget, QMenu, QAction, QListWidget, QListWidgetItem
from qt_extras import ShutUpQT
from midi_notes import MIDI_DRUM_NAMES
from kitstarter import SAMPLE_EXTENSIONS, PACKAGE_DIR
from kitstarter.pindb import PinDatabase


SampleEntry = namedtuple('Sample', ['path', 'pitch', 'sfz_path'])


class SamplesExplorer(QWidget):

	sig_directory_selected = pyqtSignal(str)
	sig_sfz_selected = pyqtSignal(str)
	sig_sample_clicked = pyqtSignal(str)
	sig_use_samples = pyqtSignal(list)


	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'samples_explorer.ui'), self)
		self.pindb = PinDatabase()
		self.current_instrument = None
		self.icon_sample_okay = QIcon(join(PACKAGE_DIR, 'res', 'sample-okay.svg'))
		self.icon_sample_mismatch = QIcon(join(PACKAGE_DIR, 'res', 'sample-mismatch.svg'))
		self.icon_sample_pinned = QIcon(join(PACKAGE_DIR, 'res', 'pin.svg'))
		self.icon_sample_err = QIcon.fromTheme('dialog-warning')
		self.chk_filter_instrument.stateChanged.connect(self.slot_filter_checked)
		self.chk_show_pinned.stateChanged.connect(self.slot_show_pinned_checked)
		self.chk_show_selected.stateChanged.connect(self.slot_show_selected_checked)
		self.lst_samples.itemPressed.connect(self.slot_sample_pressed)
		self.lst_samples.mouseReleaseEvent = self.samples_mouse_release
		self.lst_samples.setContextMenuPolicy(Qt.CustomContextMenu)
		self.lst_samples.customContextMenuRequested.connect(self.slot_samples_context_menu)

	def set_current_instrument(self, instrument):
		self.current_instrument = instrument
		self.chk_filter_instrument.setText(f'Filter "{text}"')
		if self.chk_filter_instrument.isChecked():
			self.update_samples_list()

	@pyqtSlot(int)
	def slot_show_pinned_checked(self, _):
		self.update_samples_list()

	@pyqtSlot(int)
	def slot_filter_checked(self, _):
		self.update_samples_list()

	@pyqtSlot(int)
	def slot_show_selected_checked(self, state):
		self.tree_files.setEnabled(state)
		self.update_samples_list()

	@pyqtSlot(QListWidgetItem)
	def slot_sample_pressed(self, list_item):
		if QApplication.mouseButtons() == Qt.LeftButton:
			soundfile = list_item.data(Qt.UserRole).path
			if soundfile:
				soundfile.seek(0)
				self.audi.play_soundfile(soundfile)

	@pyqtSlot(QPoint)
	def slot_samples_context_menu(self, position):
		"""
		Display context menu for self.lst_samples
		"""
		menu = QMenu(self)
		entries = [ item.data(Qt.UserRole) for item in self.lst_samples.selectedItems() ]
		pinned = [ self.pindb.is_pinned(entry.path) for entry in entries ]
		pitch = self.current_instrument.pitch

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
				self.sig_use_samples.emit([entry.path for entry in entries])
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

	def samples_mouse_release(self, event):
		self.audio_player.stop()
		super(QListWidget, self.lst_samples).mouseReleaseEvent(event)

	def update_samples_list(self):
		QApplication.setOverrideCursor(Qt.WaitCursor)
		self.lst_samples.clear()
		filter_samples = self.chk_filter_instrument.isChecked()
		pitch = self.current_instrument.pitch if filter_samples else None
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
								logging.error('Drumkit "%s" has no instrument pitch %d',
									drumkit.name, pitch)
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
		list_item.setData(Qt.UserRole, SampleEntry(path, pitch, sfz_path))
		if self.pindb.is_pinned(path):
			list_item.setIcon(self.icon_sample_pinned)
		else:
			self.set_unpinned_icon(list_item)

	def set_unpinned_icon(self, list_item):
		entry = list_item.data(Qt.UserRole)
		soundfile = self.audio.soundfile(entry.path)
		if soundfile is None:
			list_item.setIcon(self.icon_sample_err)
			list_item.setToolTip('Error reading soundfile')
		else:
			s_samp = entry.path + \
				f'\nThis file has a sample rate of {soundfile.samplerate} Hz,\n'
			if soundfile.samplerate != self.conn_man.samplerate:
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


#  end kitstarter/kitstarter/gui/samples_explorer.py
