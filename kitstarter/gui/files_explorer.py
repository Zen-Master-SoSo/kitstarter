#  kitstarter/kitstarter/gui/files_explorer.py
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
from os.path import join, dirname, splitext
from functools import lru_cache
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint, QDir, QItemSelection
from PyQt5.QtWidgets import (
	QApplication, QWidget, QFileSystemModel, QAbstractItemView, QMenu, QAction)
from qt_extras import ShutUpQT
from sfzen.drumkits import Drumkit
from kitstarter import (
	get_setting, set_setting, xdg_open, SampleFileInfo,
	FILE_FILTERS, SAMPLE_EXTENSIONS, KEY_SFZS_ROOT, KEY_SFZS_CURRENT)


class FilesExplorer(QWidget):

	sig_selection_changed = pyqtSignal(list)
	sig_use_samples = pyqtSignal(list)
	sig_open_sfz = pyqtSignal(str)

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'files_explorer.ui'), self)
		self.current_instrument = None
		root_path = get_setting(KEY_SFZS_ROOT, QDir.homePath())
		current_path = get_setting(KEY_SFZS_CURRENT, QDir.homePath())
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
		self.tree_files.selectionModel().selectionChanged.connect(self.slot_files_selection_changed)
		self.tree_files.setContextMenuPolicy(Qt.CustomContextMenu)
		self.tree_files.customContextMenuRequested.connect(self.slot_files_context_menu)

	def set_current_instrument(self, instrument):
		self.current_instrument = instrument

	@pyqtSlot(QPoint)
	def slot_files_context_menu(self, position):
		"""
		Display context menu for self.tree_files
		"""
		root_parent = dirname(self.files_model.rootPath())
		mouse_index = self.tree_files.indexAt(position)
		menu = QMenu(self)
		if root_parent or mouse_index.isValid():

			def up_to_parent():
				self.files_model.setRootPath(root_parent)
				self.tree_files.setRootIndex(self.files_model.index(root_parent))
				self.tree_files.expandToDepth(0)
				set_setting(KEY_SFZS_ROOT, root_parent)
			if root_parent:
				act_up = QAction('Up to parent')
				act_up.triggered.connect(up_to_parent)
				menu.addAction(act_up)

			if mouse_index.isValid():

				path = self.files_model.filePath(mouse_index)

				def set_root():
					self.files_model.setRootPath(path)
					self.tree_files.setRootIndex(mouse_index)
					self.tree_files.expandToDepth(0)
					set_setting(KEY_SFZS_ROOT, path)

				if self.files_model.isDir(mouse_index):
					act_set_root = QAction('Set this directory as root')
					act_set_root.triggered.connect(set_root)
					menu.addAction(act_set_root)

				else:
					ext = splitext(path)[-1].lower()
					if ext == '.sfz':

						def open_sfz():
							self.sig_open_sfz.emit(path)
						act_open = QAction('Load this SFZ', self)
						act_open.triggered.connect(open_sfz)
						menu.addAction(act_open)

					elif ext in SAMPLE_EXTENSIONS:

						def use_sample():
							self.sig_use_sample.emit([path])
						act_use_sample = QAction(f'Use for "{self.current_instrument.name}"', self)
						act_use_sample.triggered.connect(use_sample)
						menu.addAction(act_use_sample)

				def copy_path():
					QApplication.instance().clipboard().setText(path)
				act_copy_path = QAction('Copy path', self)
				act_copy_path.triggered.connect(copy_path)
				menu.addAction(act_copy_path)

				def open_file():
					xdg_open(path)
				act_open_ext = QAction('Open in external program ...')
				act_open_ext.triggered.connect(open_file)
				menu.addAction(act_open_ext)

			menu.exec(self.tree_files.mapToGlobal(position))

	def layout_complete(self):
		index = self.tree_files.currentIndex()
		self.tree_files.scrollTo(index, QAbstractItemView.PositionAtTop)
		self.slot_files_selection_changed()

	@pyqtSlot(QItemSelection, QItemSelection)
	def slot_files_selection_changed(self, *_):
		path = self.files_model.filePath(self.tree_files.currentIndex())
		set_setting(KEY_SFZS_CURRENT, path)
		sample_infos = []
		for index in self.tree_files.selectedIndexes():
			if self.files_model.isDir(index):
				continue
			path = self.files_model.filePath(index)
			ext = splitext(path)[-1]
			if ext == '.sfz':
				drumkit = self.drumkit(path)
				sample_infos.extend(SampleFileInfo(sample.abspath, instrument.pitch, path, False)
					for instrument in drumkit.instruments()
					for sample in instrument.samples())
			elif ext in SAMPLE_EXTENSIONS:
				sample_infos.append(SampleFileInfo(path, None, None, False))
		self.sig_selection_changed.emit(sample_infos)

	@lru_cache
	def drumkit(self, path):
		return Drumkit(path)


#  end kitstarter/kitstarter/gui/files_explorer.py
