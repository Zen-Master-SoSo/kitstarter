#  kitstarter/tests/samples_widget.py
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
Test the InstrumentWidget using a window.
"""
import sys, logging

from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QPushButton

from kitstarter.starter_kits import StarterKit
from kitstarter.gui.instrument_widget import InstrumentWidget, init_paint_resources


class TestWindow(QDialog):
	"""
	Window with one InstrumentWidget used for testing.
	"""

	def __init__(self):
		super().__init__()
		init_paint_resources()
		self.kit = StarterKit()
		self.instrument = self.kit.instrument('side_stick')
		lo = QVBoxLayout()
		self.tracks_widget = InstrumentWidget(self, self.instrument)
		self.tracks_widget.sig_updated.connect(self.slot_updated)
		self.tracks_widget.sig_mouse_press.connect(self.slot_mouse_press)
		self.tracks_widget.sig_mouse_release.connect(self.slot_mouse_release)
		self.samples = iter([
			'samples/sample_pp',
			'samples/sample_p',
			'samples/sample_mp',
			'samples/sample_f'
		])
		lo.addWidget(self.tracks_widget)
		self.add_button = QPushButton('Add sample')
		self.add_button.clicked.connect(self.slot_add_btn_clicked)
		lo.addWidget(self.add_button)
		self.setLayout(lo)
		self.resize(600, 200)

	@pyqtSlot()
	def slot_add_btn_clicked(self):
		try:
			self.tracks_widget.add_sample(next(self.samples))
		except StopIteration:
			self.add_button.setEnabled(False)

	@pyqtSlot()
	def slot_updated(self):
		self.kit.write(sys.stdout)

	@pyqtSlot(int, int)
	def slot_mouse_press(self, pitch, velocity):
		print(f'Mouse press: {pitch} {velocity}')

	@pyqtSlot(int)
	def slot_mouse_release(self, pitch):
		print(f'Mouse release: {pitch}')


if __name__ == "__main__":
	logging.basicConfig(
		level = logging.DEBUG,
		format = "[%(filename)24s:%(lineno)-4d] %(levelname)-8s %(message)s"
	)
	app = QApplication([])
	dialog = TestWindow()
	dialog.exec_()
	sys.exit(0)


#  end kitstarter/tests/samples_widget.py
