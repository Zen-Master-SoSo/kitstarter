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
from os.path import join, dirname, splitext
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QPoint, QDir, QItemSelection
from PyQt5.QtWidgets import (
	QApplication, QWidget, QFileSystemModel, QAbstractItemView, QMenu, QAction)
from qt_extras import ShutUpQT
from kitstarter import (
	get_setting, set_setting, xdg_open, FILE_FILTERS, SAMPLE_EXTENSIONS,
	KEY_FILES_ROOT, KEY_FILES_CURRENT)


class FilesExplorer(QWidget):

	sig_selection_changed = pyqtSignal(str)
	sig_use_samples = pyqtSignal(list)

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'files_explorer.ui'), self)
		self.current_instrument = None
		root_path = get_setting(KEY_FILES_ROOT, QDir.homePath())
		current_path = get_setting(KEY_FILES_CURRENT, QDir.homePath())
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
		indexes = self.tree_files.selectedIndexes()
		if len(indexes):
			menu = QMenu(self)
			paths = [ self.files_model.filePath(index) for index in indexes ]
			def copy_paths():
				QApplication.instance().clipboard().setText("\n".join(paths))
			action = QAction('Copy path' if len(indexes) == 1 else 'Copy paths', self)
			action.triggered.connect(copy_paths)
			menu.addAction(action)
			pitch = self.current_instrument.pitch
			if all(splitext(path)[-1] in SAMPLE_EXTENSIONS for path in paths):
				def use_samples():
					self.sig_use_samples.emit(paths)
				action = QAction(f'Use for "{self.current_instrument.name}"', self)
				action.triggered.connect(use_samples)
				menu.addAction(action)
			def open_file():
				xdg_open(paths[0])
			if len(indexes) == 1:
				action = QAction('Open in external program ...')
				action.triggered.connect(open_file)
				menu.addAction(action)
			menu.exec(self.tree_files.mapToGlobal(position))

	def layout_complete(self):
		index = self.tree_files.currentIndex()
		self.tree_files.scrollTo(index, QAbstractItemView.PositionAtTop)
		self.slot_files_selection_changed()

	@pyqtSlot(QItemSelection, QItemSelection)
	def slot_files_selection_changed(self, *_):
		path = self.files_model.filePath(self.tree_files.currentIndex())
		set_setting(KEY_FILES_CURRENT, path)
		self.sig_selection_changed.emit(path)


#  end kitstarter/kitstarter/gui/files_explorer.py
