#  kitstarter/gui/samples_widget.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
#
import logging
from os.path import join, basename
from math import sqrt
from functools import partial
from itertools import combinations
from collections import namedtuple

from PyQt5.QtCore import	Qt, pyqtSignal, pyqtSlot, QPointF, QRectF, QSize, QTimer
from PyQt5.QtGui import		QPainter, QColor, QPen, QBrush, QIcon
from PyQt5.QtWidgets import	QWidget, QSizePolicy, QLayout, QVBoxLayout, QHBoxLayout, \
							QCheckBox, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, \
							QSlider, QFrame

from qt_extras import SigBlock
from qt_extras.shuffle_grid import ShuffleGrid

from kitstarter import PACKAGE_DIR
from kitstarter.starter_kits import Velcurve

# Suggested sizes:
TRACK_HEIGHT = 34
TRACK_WIDTH = 224
SCALE_HEIGHT = 25
LABEL_WIDTH = 190

# Grid column indexes
COL_LABEL = 0
COL_GRAPH = 1
COL_VOLUME = 2
COL_SEMITONES = 3
COL_CENTS = 4
COL_BUTTONS = 5

# VelocityGraph grab feature
FEATURE_LOVEL = 1
FEATURE_HIVEL = 2
FEATURE_BOTH = 3

# VelocityGraph snap ranges
LINEAR_SNAP_RANGE = 4
POLAR_SNAP_RANGE = sqrt(pow(LINEAR_SNAP_RANGE, 2) * 2)

# Milliseconds to wait after changes are made before signalling change
UPDATES_DEBOUNCE = 680

Overlap = namedtuple('Overlap', ['lovel', 'hivel', 't1', 't2'])


def str_feature(feature):
	if feature == FEATURE_LOVEL:
		return 'lovel'
	if feature == FEATURE_HIVEL:
		return 'hivel'
	return 'both'


def init_paint_resources():
	if hasattr(init_paint_resources, 'initialized'):
		logging.warning('Already initialized')
	init_paint_resources.initialized = True
	for cls in _Track.__subclasses__():
		if hasattr(cls, 'init_paint_resources'):
			cls.init_paint_resources()


class _Track(QWidget):
	"""
	Abstract widget which handles scaling between velocity and screen coordinates.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		self.v2x_scale = None

	def resizeEvent(self, _):
		self.v2x_scale = self.width() / 127

	def x2v(self, x):
		"""
		Convert a screen x coordinate to a velocity
		"""
		return max(0, min(127, round(x / self.v2x_scale)))

	def v2x(self, velocity):
		"""
		Convert a velocity to a screen x coordinate
		"""
		return velocity * self.v2x_scale

	def y2a(self, y):
		"""
		Convert a screen y coordinate to a normalized amplitude
		"""
		return max(0.0, min(1.0,
			(self.height() - y) / self.height()
		))

	def a2y(self, scale_point):
		"""
		Convert a normalized amplitude to a screen y coordinate
		"""
		return self.height() - scale_point * self.height()

	def v2a(self, velocity):
		"""
		Convert a velocity to a normalized amplitude
		"""
		return velocity / 127

	def v2y(self, velocity):
		"""
		Convert a velocity to a screen y coordinate
		"""
		return self.a2y(self.v2a(velocity))


class VelocityGraph(_Track):
	"""
	Graphically displays the effects of lovel, hivel, and amp_velcurve_N.
	"""

	sig_range_changed = pyqtSignal(QWidget, int)
	sig_value_changed = pyqtSignal()

	@classmethod
	def init_paint_resources(cls):
		cls.outline_pen = QPen(QColor("#AAA"))
		cls.outline_pen.setWidth(1)
		cls.envelope_pen = QPen(QColor("#7777D4"))
		cls.envelope_pen.setWidth(1)
		cls.fill_brush = QBrush(QColor("#DDE"), Qt.SolidPattern)
		cls.velcurve_pen_normal = QPen(QColor("#B670FF"))
		cls.velcurve_pen_normal.setWidth(3)
		cls.velcurve_pen_hover = QPen(QColor("#E173FF"))
		cls.velcurve_pen_hover.setWidth(4)
		cls.velcurve_pen_grabbed = QPen(QColor("#E14782"))
		cls.velcurve_pen_grabbed.setWidth(4)

	def __init__(self, parent, sample):
		super().__init__(parent)
		self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
		self.setMinimumHeight(TRACK_HEIGHT)
		self.sample = sample
		self.overlaps = []
		self.setMouseTracking(True)
		self.hover_point_index = None
		self.hover_point_grabbed = False

	def __str__(self):
		return f'VelocityGraph for "{self.sample}"'

	def sizeHint(self):
		return QSize(TRACK_WIDTH, TRACK_HEIGHT)

	def mouseMoveEvent(self, event):
		if event.buttons() == Qt.LeftButton:
			if self.hover_point_index is None:
				self.range_change_event(event)
			else:
				self.sample._velcurves[self.hover_point_index] = Velcurve(
					self.sample._velcurves[self.hover_point_index].velocity \
						if event.modifiers() & Qt.ControlModifier \
						else self.x2v(event.x()),
					self.sample._velcurves[self.hover_point_index].amplitude \
						if event.modifiers() & Qt.ShiftModifier \
						else self.y2a(event.y())
				)
				self.update()
		elif event.buttons() == Qt.NoButton and self.sample._velcurves:
			near_points = [ (
				sqrt(
					pow(abs(self.v2x(velcurve.velocity) - event.x()), 2) +
					pow(abs(self.a2y(velcurve.amplitude) - event.y()), 2)
				),
				index
			) for index, velcurve in enumerate(self.sample._velcurves) ]
			near_points.sort()
			hover_point_index = near_points[0][1] if near_points[0][0] < POLAR_SNAP_RANGE else None
			if hover_point_index != self.hover_point_index:
				self.hover_point_index = hover_point_index
				self.update()

	def mousePressEvent(self, event):
		if event.buttons() == Qt.LeftButton:
			if self.hover_point_index is None:
				self.range_change_event(event)
			else:
				self.hover_point_grabbed = True
				self.update()

	def mouseReleaseEvent(self, event):
		if self.hover_point_grabbed:
			self.hover_point_grabbed = False
			self.sig_value_changed.emit()
			self.update()

	def range_change_event(self, event):
		velocity = self.x2v(event.x())
		feature = None
		if velocity <= self.sample.lovel:
			self.sample.lovel = velocity
			feature = FEATURE_LOVEL
		elif velocity >= self.sample.hivel:
			self.sample.hivel = velocity
			feature = FEATURE_HIVEL
		else:
			lodiff = abs(velocity - self.sample.lovel)
			hidiff = abs(velocity - self.sample.hivel)
			if lodiff < hidiff:
				self.sample.lovel = velocity
				feature = FEATURE_LOVEL
			else:
				self.sample.hivel = velocity
				feature = FEATURE_HIVEL
		self.sig_range_changed.emit(self, feature)
		self.update()

	def paintEvent(self, _):
		painter = QPainter(self)

		x_lo = self.v2x(self.sample.lovel)
		x_hi = self.v2x(self.sample.hivel)
		velrange_rect = QRectF(x_lo, 0, x_hi - x_lo, self.height())
		painter.fillRect(velrange_rect, self.fill_brush)

		painter.setPen(self.outline_pen)
		painter.drawLine(self.rect().bottomLeft(), self.rect().bottomRight())
		painter.drawLine(self.rect().bottomLeft(), self.rect().bottomRight())

		painter.setPen(self.envelope_pen)
		painter.setRenderHint(QPainter.Antialiasing)

		points = []
		points.append(QPointF(self.rect().bottomLeft()))
		if self.lovel > 0:
			# line across to lovel:
			points.append(QPointF(self.v2x(self.lovel), self.rect().bottom()))

		if self.sample._velcurves:
			for velcurve in self.sample._velcurves:
				points.append(QPointF(self.v2x(velcurve.velocity), self.a2y(velcurve.amplitude)))
		else:
			points.append(QPointF(self.v2x(self.lovel), self.v2y(self.lovel)))
			points.append(QPointF(self.v2x(self.hivel), self.v2y(self.hivel)))

		if self.hivel < 127:
			# line across from hivel:
			points.append(QPointF(self.v2x(self.hivel), self.rect().bottom()))

		points.append(QPointF(self.rect().bottomRight()))

		piter = iter(points)
		start = next(piter)
		while True:
			try:
				end = next(piter)
			except StopIteration:
				break
			else:
				painter.drawLine(start, end)
				start = end

		for index, velcurve in enumerate(self.sample._velcurves):
			if self.hover_point_index == index:
				painter.setPen(self.velcurve_pen_grabbed \
					if self.hover_point_grabbed else self.velcurve_pen_hover)
			else:
				painter.setPen(self.velcurve_pen_normal)
			painter.drawPoint(QPointF(self.v2x(velcurve.velocity), self.a2y(velcurve.amplitude)))

		painter.end()

	@property
	def lovel(self):
		return self.sample.lovel

	@lovel.setter
	def lovel(self, value):
		self.sample.lovel = value
		self.update()

	@property
	def hivel(self):
		return self.sample.hivel

	@hivel.setter
	def hivel(self, value):
		self.sample.hivel = value
		self.update()

	# -----------------------------------------------------------------
	# These slots catch signals from the spinners on the same grid row
	# as this VelocityGraph

	@pyqtSlot(float)
	def slot_volume_changed(self, value):
		self.sample.volume = value
		self.sig_value_changed.emit()

	@pyqtSlot(int)
	def slot_transpose_changed(self, value):
		self.sample.transpose = value
		self.sig_value_changed.emit()

	@pyqtSlot(int)
	def slot_tune_changed(self, value):
		self.sample.tune = value
		self.sig_value_changed.emit()

	# -----------------------------------------------------------------
	# Velocity curve functions:

	def overlap(self, other_track):
		"""
		Used to determine if this track overlaps abother track.
		Returns Overlap(lovel, hivel, self, other), if tracks overlap, else None
		"""
		lovel = max(other_track.lovel, self.lovel)
		hivel = min(other_track.hivel, self.hivel)
		return Overlap(lovel, hivel, self, other_track) \
			if lovel < hivel else None

	def update_velcurves(self):
		velcurves = []
		if self.overlaps:
			self.overlaps.sort(key = lambda overlap: overlap.lovel)
			lo_overlap = self.overlaps.pop(0) if self.overlaps[0].lovel == self.lovel else None
			if self.overlaps:
				hi_overlap = self.overlaps.pop(-1) if self.overlaps[-1].hivel == self.hivel else None
			else:
				hi_overlap = None
			if self.overlaps:
				mid_overlaps = self.overlaps
			else:
				mid_overlaps = []
			if lo_overlap:
				velcurves.append(Velcurve(self.lovel, 0.0))
				velcurves.append(Velcurve(lo_overlap.hivel, self.v2a(lo_overlap.hivel)))
			else:
				velcurves.append(Velcurve(self.lovel, self.v2a(self.lovel)))
			for mid_overlap in mid_overlaps:
				velcurves.append(Velcurve(mid_overlap.lovel, self.v2a(mid_overlap.lovel)))
				mid_overlap_center = mid_overlap.lovel + round((mid_overlap.hivel -  mid_overlap.lovel) / 2)
				velcurves.append(Velcurve(mid_overlap_center, 0.0))
				velcurves.append(Velcurve(mid_overlap.hivel, self.v2a(mid_overlap.hivel)))
			if hi_overlap:
				velcurves.append(Velcurve(hi_overlap.lovel, self.v2a(hi_overlap.lovel)))
				velcurves.append(Velcurve(self.hivel, 0.0))
			else:
				velcurves.append(Velcurve(self.hivel, self.v2a(self.hivel)))
		self.sample.velcurves = velcurves
		self.update()


class Scale(_Track):
	"""
	Renders a scale at the top of all tracks with ticks at points representing the
	velocity of common musical dynamics notations.
	"""

	@classmethod
	def init_paint_resources(cls):
		cls.outline_pen = QPen(QColor("#AAA"))
		cls.outline_pen.setWidth(1)

	def __init__(self, parent):
		super().__init__(parent)
		self.setFixedHeight(SCALE_HEIGHT)
		self.indicator_points = [
			QPointF(-4,0),
			QPointF(0,4),
			QPointF(6,0)
		]
		self.scale_points = {
			'ppp'	: 16,
			'pp'	: 33,
			'p'		: 49,
			'mp'	: 64,
			'mf'	: 80,
			'f'		: 96,
			'ff'	: 112
		}
		self.label_font = self.font()
		self.label_font.setItalic(True)
		self.label_font.setPixelSize(11)

	def paintEvent(self, _):
		painter = QPainter(self)
		painter.setFont(self.label_font)
		for text, velocity in self.scale_points.items():
			point = QPointF(self.v2x(velocity), 9)
			rect = QRectF(0, 0, 40, TRACK_HEIGHT)
			rect.moveCenter(point)
			painter.drawText(rect, Qt.AlignCenter, text)
			painter.drawLine(
				point + QPointF(0, 10),
				point + QPointF(0, TRACK_HEIGHT)
			)
		painter.setPen(self.outline_pen)
		painter.drawLine(self.rect().bottomLeft(), self.rect().bottomRight())
		painter.end()


class Pad(_Track):
	"""
	A visual "drumpad" which generates signals when the mouse is pressed for
	triggering a synth.
	"""

	sig_mouse_press = pyqtSignal(int)
	sig_mouse_release = pyqtSignal()

	@classmethod
	def init_paint_resources(cls):
		normal_color = QColor('#BBB')
		mouse_down_color = QColor('#989898')
		cls.normal_brush = QBrush(normal_color, Qt.Dense4Pattern)
		cls.mouse_down_brush = QBrush(mouse_down_color, Qt.Dense4Pattern)
		cls.pen = QPen(normal_color)

	def __init__(self, parent):
		super().__init__(parent)
		self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
		self.setMinimumHeight(TRACK_HEIGHT)
		self.mouse_pressed = False

	def mousePressEvent(self, event):
		self.sig_mouse_press.emit(self.x2v(event.x()))
		self.mouse_pressed = True
		self.update()

	def mouseReleaseEvent(self, _):
		self.sig_mouse_release.emit()
		self.mouse_pressed = False
		self.update()

	def paintEvent(self, _):
		painter = QPainter(self)
		painter.setPen(self.pen)
		painter.setBrush(self.mouse_down_brush if self.mouse_pressed else self.normal_brush)
		painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 8, 8)
		painter.end()


class SamplesWidget(QWidget):
	"""
	A widget which displays the lovel, hivel range and amp_veltrack points of .sfz
	regions associated with a sample. Modifications to the region are done with
	mouse interaction.
	"""

	sig_updating = pyqtSignal()
	sig_updated = pyqtSignal()
	sig_mouse_press = pyqtSignal(int, int)
	sig_mouse_release = pyqtSignal(int)

	def __init__(self, parent, instrument):
		super().__init__(parent)
		self.instrument = instrument

		# Setup common icons / fonts
		self.small_font = self.font()
		self.small_font.setPointSize(10)
		self.icon_up_enabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-up-enabled.svg'))
		self.icon_down_enabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-down-enabled.svg'))
		self.icon_up_disabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-up-disabled.svg'))
		self.icon_down_disabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-down-disabled.svg'))
		self.icon_delete = QIcon(join(PACKAGE_DIR, 'res', 'delete.svg'))
		self.icon_size = QSize(14, 14)

		# Setup update timer (used to prevent triggering file update when changes are being made)
		self.update_timer = QTimer()
		self.update_timer.setSingleShot(True)
		self.update_timer.setInterval(UPDATES_DEBOUNCE)
		self.update_timer.timeout.connect(self.slot_updated)

		# Create main layout
		main_layout = QVBoxLayout()
		main_layout.setContentsMargins(8,4,8,8) # left, top, right, bottom
		main_layout.setSpacing(8)

		# Setup title area
		title_layout = QHBoxLayout()
		label = QLabel(self.instrument.name)
		font = label.font()
		font.setBold(True)
		font.setPointSize(13)
		label.setFont(font)
		label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
		title_layout.addWidget(label)
		self.sample_count_label = QLabel('[no samples]', self)
		self.sample_count_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
		font = self.sample_count_label.font()
		font.setItalic(True)
		self.sample_count_label.setFont(font)
		title_layout.addWidget(self.sample_count_label)
		title_layout.addStretch()
		main_layout.addLayout(title_layout)

		# Setup main grid
		self.grid = ShuffleGrid()
		self.grid.setHorizontalSpacing(12)
		self.grid.setVerticalSpacing(0)
		self.grid.setSizeConstraint(QLayout.SetMinimumSize)
		# Row 0
		self.grid.addWidget(Scale(self), 0, COL_GRAPH)
		for text, col in [
			('Vol.', COL_VOLUME),
			('Semi.', COL_SEMITONES),
			('Cents', COL_CENTS)
		]:
			label = QLabel(text, self)
			label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
			label.setFont(self.small_font)
			self.grid.addWidget(label, 0, col)
		# Row 1
		self.pad = Pad(self)
		self.grid.addWidget(self.pad, 1, COL_GRAPH)
		# Set grid stretch
		self.grid.setColumnStretch(COL_LABEL, 2)
		self.grid.setColumnStretch(COL_GRAPH, 12)
		# Add grid
		main_layout.addLayout(self.grid)

		# Setup options area
		self.spread_button = QPushButton('Spread')
		self.chk_crossfade = QCheckBox('Cross fade', self)
		self.chk_snap = QCheckBox('Snap', self)
		lbl_pan = QLabel('Pan:', self)
		self.sld_pan = QSlider(self)
		self.sld_pan.setOrientation(Qt.Horizontal)
		self.sld_pan.setMinimum(-100)
		self.sld_pan.setMaximum(100)
		self.sld_pan.setTickInterval(50)
		self.sld_pan.setTickPosition(QSlider.TicksBelow)
		self.spread_button.setFont(self.small_font)
		self.chk_crossfade.setFont(self.small_font)
		self.chk_snap.setFont(self.small_font)
		lbl_pan.setFont(self.small_font)
		options_layout = QHBoxLayout()
		options_layout.setContentsMargins(4, 0, 4, 0)
		options_layout.setSpacing(8)
		options_layout.addStretch()
		options_layout.addWidget(self.spread_button)
		options_layout.addWidget(self.chk_crossfade)
		options_layout.addWidget(self.chk_snap)
		options_layout.addWidget(lbl_pan)
		options_layout.addWidget(self.sld_pan)
		options_layout.addStretch()
		options_layout.setSizeConstraint(QLayout.SetFixedSize)
		main_layout.addSpacing(5)
		main_layout.addLayout(options_layout)

		# Set main layout and update ui
		self.setLayout(main_layout)
		self.update_ui()

		# Connect UI signals
		self.spread_button.clicked.connect(self.slot_spread)
		self.chk_crossfade.stateChanged.connect(self.slot_crossfade_state_change)
		self.chk_snap.stateChanged.connect(self.slot_snap_state_change)
		self.sld_pan.valueChanged.connect(self.slot_pan_changed)
		self.pad.sig_mouse_press.connect(self.slot_mouse_press)
		self.pad.sig_mouse_release.connect(self.slot_mouse_release)

	def load_instrument(self, instrument):
		while self.grid.inhabited_row_count() > 2:
			self.grid.delete_row(self.grid.inhabited_row_indexes()[1])
		self.instrument = instrument
		with SigBlock(self.sld_pan):
			self.sld_pan.setValue(int(self.instrument.pan * 100))
		for sample in self.instrument.samples.values():
			self._add_sample(sample)
		self.update_ui()

	def add_sample(self, path):
		if path in self.instrument.samples:
			logging.warning('%s already in %s samples', path, self.instrument.name)
			return
		self._add_sample(self.instrument.add_sample(path))
		self.update_ui()
		self.slot_value_changed()

	def _add_sample(self, sample):

		widgets = []

		label = QLabel(basename(sample.path), self)
		label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
		label.setToolTip(sample.path)
		label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
		widgets.append(label)

		velo_graph = VelocityGraph(self, sample)
		velo_graph.sig_range_changed.connect(self.slot_range_changed)
		velo_graph.sig_value_changed.connect(self.slot_value_changed)
		widgets.append(velo_graph)

		frame = QFrame(self)
		lo = QVBoxLayout()
		lo.setContentsMargins(0,0,0,0)
		lo.setSpacing(0)
		spinner = QDoubleSpinBox(frame)
		spinner.setRange(-144, 6)
		spinner.setValue(sample.volume)
		spinner.setSingleStep(0.25)
		spinner.valueChanged.connect(velo_graph.slot_volume_changed)
		spinner.setMaximumWidth(58)
		spinner.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
		lo.addWidget(spinner)
		lo.addStretch()
		frame.setLayout(lo)
		widgets.append(frame)

		frame = QFrame(self)
		lo = QVBoxLayout()
		lo.setContentsMargins(0,0,0,0)
		lo.setSpacing(0)
		spinner = QSpinBox(frame)
		spinner.setRange(-11, 11)
		spinner.setValue(sample.transpose)
		spinner.valueChanged.connect(velo_graph.slot_transpose_changed)
		spinner.setMaximumWidth(46)
		spinner.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
		lo.addWidget(spinner)
		lo.addStretch()
		frame.setLayout(lo)
		widgets.append(frame)

		frame = QFrame(self)
		lo = QVBoxLayout()
		lo.setContentsMargins(0,0,0,0)
		lo.setSpacing(0)
		spinner = QSpinBox(frame)
		spinner.setRange(-100, 100)
		spinner.setValue(sample.tune)
		spinner.valueChanged.connect(velo_graph.slot_tune_changed)
		spinner.setMaximumWidth(46)
		spinner.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
		lo.addWidget(spinner)
		lo.addStretch()
		frame.setLayout(lo)
		widgets.append(frame)

		frame = QFrame(self)
		btnlo = QHBoxLayout()
		btnlo.setContentsMargins(0,0,0,0)
		btnlo.setSpacing(2)

		frame.up_button = QPushButton(frame)
		frame.up_button.setIcon(self.icon_up_enabled)
		frame.up_button.setIconSize(self.icon_size)
		frame.up_button.clicked.connect(partial(self.slot_move_up, frame.up_button))
		btnlo.addWidget(frame.up_button)

		frame.down_button = QPushButton(frame)
		frame.down_button.setIcon(self.icon_down_enabled)
		frame.down_button.setIconSize(self.icon_size)
		frame.down_button.clicked.connect(partial(self.slot_move_down, frame.down_button))
		btnlo.addWidget(frame.down_button)

		button = QPushButton(frame)
		button.setIcon(self.icon_delete)
		button.setIconSize(self.icon_size)
		button.clicked.connect(partial(self.slot_delete, button))
		btnlo.addWidget(button)

		frmlo = QVBoxLayout()
		frmlo.setContentsMargins(0,0,0,0)
		frmlo.addLayout(btnlo)
		frmlo.addStretch()
		frame.setLayout(frmlo)
		widgets.append(frame)

		valid_indexes = self.grid.inhabited_row_indexes()
		self.grid.insert_row(widgets, valid_indexes[-1])

	def get_button_row(self, button):
		idx = self.grid.indexOf(button.parent())
		row, *_ = self.grid.getItemPosition(idx)
		return row

	def velo_graphs(self):
		"""
		Returns a list of VelocityGraph
		"""
		# Exclude first row (scale) and last row (pad)
		return self.grid.column(COL_GRAPH)[1:-1]

	def button_frames(self):
		"""
		Returns a list of QFrame, each containing an up / down / delete button
		"""
		# Exclude first row (scale) and last row (pad)
		return self.grid.column(COL_BUTTONS)[1:-1]

	@pyqtSlot(int)
	def slot_mouse_press(self, velocity):
		self.sig_mouse_press.emit(self.instrument.pitch, velocity)

	@pyqtSlot()
	def slot_mouse_release(self):
		self.sig_mouse_release.emit(self.instrument.pitch)

	@pyqtSlot(int)
	def slot_snap_state_change(self, state):
		if state:
			self.chk_crossfade.setChecked(0)
			self.clear_overlaps()

	@pyqtSlot(int)
	def slot_crossfade_state_change(self, state):
		if state:
			self.chk_snap.setChecked(0)
			self.find_overlaps()
		else:
			self.clear_overlaps()

	@pyqtSlot(int)
	def slot_pan_changed(self, value):
		self.instrument.pan = value / 100
		self.slot_value_changed()

	@pyqtSlot()
	def slot_spread(self):
		tracks = self.velo_graphs()
		spread = 127 / len(tracks)
		for i in range(len(tracks)):
			tracks[i].lovel = round(i * spread)
			tracks[i].hivel = round((i + 1) * spread)
		self.find_overlaps()
		self.slot_value_changed()

	@property
	def snap(self):
		return self.chk_snap.isChecked()

	@snap.setter
	def snap(self, state):
		self.chk_snap.setChecked(bool(state))

	@property
	def crossfade(self):
		return self.chk_crossfade.isChecked()

	@crossfade.setter
	def crossfade(self, state):
		self.chk_crossfade.setChecked(bool(state))

	@pyqtSlot(QWidget, int)
	def slot_range_changed(self, source_track, feature):
		if self.snap:
			other_tracks = list(set(self.velo_graphs()) ^ set([source_track]))
			if feature == FEATURE_LOVEL:
				for other_track in other_tracks:
					if abs(source_track.lovel - other_track.hivel) <= LINEAR_SNAP_RANGE:
						other_track.hivel = source_track.lovel
			else:
				for other_track in other_tracks:
					if abs(source_track.hivel - other_track.lovel) <= LINEAR_SNAP_RANGE:
						other_track.lovel = source_track.hivel
		elif self.crossfade:
			self.find_overlaps()
		self.slot_value_changed()

	@pyqtSlot()
	def slot_value_changed(self):
		self.sig_updating.emit()
		self.update_timer.start()

	@pyqtSlot()
	def slot_updated(self):
		self.sig_updated.emit()

	@pyqtSlot(QPushButton)
	def slot_move_up(self, button):
		self.grid.move_row_up(self.get_button_row(button))
		self.update_ui()

	@pyqtSlot(QPushButton)
	def slot_move_down(self, button):
		self.grid.move_row_down(self.get_button_row(button))
		self.update_ui()

	@pyqtSlot(QPushButton)
	def slot_delete(self, button):
		row = self.get_button_row(button)
		velo_graph = self.grid.itemAtPosition(row, COL_GRAPH).widget()
		self.instrument.remove_sample(velo_graph.sample.path)
		self.grid.delete_row(row)
		self.slot_value_changed()
		self.update_ui()

	def update_ui(self):
		frames = self.button_frames()
		has_samples = bool(frames)
		self.sld_pan.setEnabled(has_samples)
		self.spread_button.setEnabled(has_samples)
		self.chk_crossfade.setEnabled(has_samples)
		self.chk_snap.setEnabled(has_samples)
		self.sld_pan.setEnabled(has_samples)
		self.sample_count_label.setEnabled(has_samples)
		self.sample_count_label.setText(
			'[1 sample]' if len(frames) == 1 else f'[{len(frames)} samples]')
		if has_samples:
			frames[0].up_button.setEnabled(False)
			frames[0].up_button.setIcon(self.icon_up_disabled)
			for button_track in frames[1:]:
				button_track.up_button.setEnabled(True)
				button_track.up_button.setIcon(self.icon_up_enabled)
			for button_track in frames[:-1]:
				button_track.down_button.setEnabled(True)
				button_track.down_button.setIcon(self.icon_down_enabled)
			frames[-1].down_button.setEnabled(False)
			frames[-1].down_button.setIcon(self.icon_down_disabled)

	def find_overlaps(self):
		self.clear_overlaps()
		tracks = self.velo_graphs()
		for tup in combinations(tracks, 2):
			overlap = tup[0].overlap(tup[1])
			if overlap:
				tup[0].overlaps.append(overlap)
				tup[1].overlaps.append(overlap)
		for velo_graph in tracks:
			velo_graph.update_velcurves()

	def clear_overlaps(self):
		for velo_graph in self.velo_graphs():
			velo_graph.overlaps = []


#  end kitstarter/gui/samples_widget.py
