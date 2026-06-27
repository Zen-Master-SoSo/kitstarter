#  kitstarter/kitstarter/gui/instrument_list.py
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
from os.path import join, dirname
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget, QListWidgetItem
from qt_extras import ShutUpQT
from sfzen.drumkits import iter_pitch_by_group
from midi_notes import MIDI_DRUM_NAMES
from kitstarter import PACKAGE_DIR


class InstrumentList(QWidget):

	sig_row_changed = pyqtSignal(int)	# Emits row that selected instrument is on

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'instrument_list.ui'), self)
		font = self.lst_instruments.font()
		font.setPointSizeF(11.5)
		self.lst_instruments.setFont(font)
		self.lst_instruments.setFixedWidth(180)
		self.icon_complete = QIcon(join(PACKAGE_DIR, 'res', 'inst-complete.svg'))
		self.icon_incomplete = QIcon(join(PACKAGE_DIR, 'res', 'inst-incomplete.svg'))
		for pitch in iter_pitch_by_group():
			list_item = QListWidgetItem(self.lst_instruments)
			list_item.setText(MIDI_DRUM_NAMES[pitch])
			list_item.setIcon(self.icon_incomplete)
			list_item.setData(Qt.UserRole, pitch)
		self.lst_instruments.currentRowChanged.connect(self.sig_row_changed)

	def iter_instrument_list(self):
		for row in range(self.lst_instruments.count()):
			yield self.lst_instruments.item(row)

	def update_instrument_list(self):
		for list_item in self.iter_instrument_list():
			instrument = self.kit.instrument(list_item.data(Qt.UserRole))
			list_item.setIcon(self.icon_complete if len(instrument.samples) else self.icon_incomplete)


#  end kitstarter/kitstarter/gui/instrument_list.py
