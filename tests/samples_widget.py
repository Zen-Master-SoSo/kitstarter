#  kitstarter/gui/samples_widget.py
#
#  Copyright 2025 liyang <liyang@veronica>
#
"""
Test the SamplesWidget using a window.
"""
import sys, logging

from PyQt5.QtCore import	pyqtSlot
from PyQt5.QtWidgets import	QApplication, QDialog, QVBoxLayout, QPushButton

from sfzen.drumkits import StarterKit

from kitstarter import set_application_style
from kitstarter.gui.samples_widget import SamplesWidget, init_paint_resources


class TestWindow(QDialog):
	"""
	Window with one SamplesWidget used for testing.
	"""

	def __init__(self):
		super().__init__()
		init_paint_resources()
		self.kit = StarterKit()
		self.instrument = self.kit.instrument('side_stick')
		lo = QVBoxLayout()
		self.tracks_widget = SamplesWidget(self, self.instrument)
		self.tracks_widget.sig_updated.connect(self.slot_instrument_changed)
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
		self.add_button.clicked.connect(self.slot_add_sample)
		lo.addWidget(self.add_button)
		self.setLayout(lo)

	@pyqtSlot()
	def slot_add_sample(self):
		try:
			self.tracks_widget.append(next(self.samples))
		except StopIteration:
			self.add_button.setEnabled(False)

	@pyqtSlot()
	def slot_instrument_changed(self):
		self.kit.write(sys.stdout)

	@pyqtSlot(int, int)
	def slot_mouse_press(self, pitch, velocity):
		print(f'Mouse press: {pitch} {velocity}')

	@pyqtSlot(int)
	def slot_mouse_release(self, pitch):
		print(f'Mouse release: {pitch}')


if __name__ == "__main__":
	logging.basicConfig(
		stream = sys.stdout,
		level = logging.DEBUG,
		format = "[%(filename)24s:%(lineno)-4d] %(levelname)-8s %(message)s"
	)
	app = QApplication([])
	set_application_style()
	dialog = TestWindow()
	dialog.exec_()
	sys.exit(0)


#  end kitstarter/gui/samples_widget.py
