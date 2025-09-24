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
from PyQt5.QtWidgets import	QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, \
							QCheckBox, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, \
							QSlider, QFrame

from qt_extras import SigBlock
from qt_extras.list_layout import VListLayout

from kitstarter import PACKAGE_DIR
from kitstarter.starter_kits import Velcurve


FEATURE_LOVEL = 1
FEATURE_HIVEL = 2
FEATURE_BOTH = 3
LINEAR_SNAP_RANGE = 4
POLAR_SNAP_RANGE = sqrt(pow(LINEAR_SNAP_RANGE, 2) * 2)
TRACK_HEIGHT = 32
TRACK_WIDTH = 224
LABEL_WIDTH = 180
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
		self.setFixedHeight(TRACK_HEIGHT)
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


class SampleTrack(_Track):
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
		self.setFixedWidth(TRACK_WIDTH)
		self.sample = sample
		self.overlaps = []
		self.setMouseTracking(True)
		self.hover_point_index = None
		self.hover_point_grabbed = False

	def __str__(self):
		return f'SampleTrack for "{self.sample}"'

	def mouseMoveEvent(self, event):
		if event.buttons() == Qt.LeftButton:
			if self.hover_point_index is None:
				self.mouse_lohivel_event(event)
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
				self.mouse_lohivel_event(event)
			else:
				self.hover_point_grabbed = True
				self.update()

	def mouseReleaseEvent(self, event):
		if self.hover_point_grabbed:
			self.hover_point_grabbed = False
			self.sig_value_changed.emit()
			self.update()

	def mouse_lohivel_event(self, event):
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


class ButtonsTrack(QFrame, _Track):

	sig_value_changed = pyqtSignal()
	sig_move_up = pyqtSignal()
	sig_move_down = pyqtSignal()
	sig_delete = pyqtSignal()

	@classmethod
	def init_paint_resources(cls):
		cls.icon_up_enabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-up-enabled.svg'))
		cls.icon_down_enabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-down-enabled.svg'))
		cls.icon_up_disabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-up-disabled.svg'))
		cls.icon_down_disabled = QIcon(join(PACKAGE_DIR, 'res', 'arrow-down-disabled.svg'))
		cls.icon_delete = QIcon(join(PACKAGE_DIR, 'res', 'delete.svg'))
		cls.icon_size = QSize(14, 14)

	def __init__(self, parent, sample):
		super().__init__(parent)
		self.sample = sample

		lo = QHBoxLayout()
		lo.setSpacing(11)
		lo.setContentsMargins(0,0,0,0)

		vollo = QHBoxLayout()
		vollo.setSpacing(3)

		lbl = QLabel('Vol:', self)
		vollo.addWidget(lbl)
		self.spin_volume = QDoubleSpinBox(self)
		self.spin_volume.setMaximumWidth(64)
		self.spin_volume.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
		self.spin_volume.setRange(-144, 6)
		self.spin_volume.setValue(0)
		self.spin_volume.setSingleStep(0.25)
		self.spin_volume.valueChanged.connect(self.slot_value_changed)
		vollo.addWidget(self.spin_volume)

		lo.addItem(vollo)

		tunlo = QHBoxLayout()
		tunlo.setSpacing(3)

		tunlo.addWidget(QLabel('Tune:', self))
		self.spin_transpose = QSpinBox(self)
		self.spin_transpose.setMaximumWidth(42)
		self.spin_transpose.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
		self.spin_transpose.setRange(-11, 11)
		self.spin_transpose.setValue(0)
		self.spin_transpose.valueChanged.connect(self.slot_value_changed)
		tunlo.addWidget(self.spin_transpose)
		tunlo.addWidget(QLabel('semi,', self))

		self.spin_tune = QSpinBox(self)
		self.spin_tune.setMaximumWidth(45)
		self.spin_tune.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
		self.spin_tune.setRange(-100, 100)
		self.spin_tune.setValue(0)
		self.spin_tune.valueChanged.connect(self.slot_value_changed)
		tunlo.addWidget(self.spin_tune)
		tunlo.addWidget(QLabel('cent', self))

		lo.addItem(tunlo)

		btnlo = QHBoxLayout()

		self.up_button = QPushButton(self)
		self.up_button.setIcon(self.icon_up_enabled)
		self.up_button.setIconSize(self.icon_size)
		self.up_button.clicked.connect(self.slot_button_up_click)
		btnlo.addWidget(self.up_button)

		self.down_button = QPushButton(self)
		self.down_button.setIcon(self.icon_down_enabled)
		self.down_button.setIconSize(self.icon_size)
		self.down_button.clicked.connect(self.slot_button_down_click)
		btnlo.addWidget(self.down_button)

		delete_button = QPushButton(self)
		delete_button.setIcon(self.icon_delete)
		delete_button.setIconSize(self.icon_size)
		delete_button.clicked.connect(self.slot_button_delete_click)
		btnlo.addWidget(delete_button)

		lo.addItem(btnlo)

		self.setLayout(lo)

	@pyqtSlot()
	def slot_value_changed(self):
		self.sample.volume = self.spin_volume.value()
		self.sample.transpose = self.spin_transpose.value()
		self.sample.tune = self.spin_tune.value()
		self.sig_value_changed.emit()

	@pyqtSlot()
	def slot_button_up_click(self):
		self.sig_move_up.emit()

	@pyqtSlot()
	def slot_button_down_click(self):
		self.sig_move_down.emit()

	@pyqtSlot()
	def slot_button_delete_click(self):
		self.sig_delete.emit()


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

		self.button_font = self.font()
		self.button_font.setPixelSize(11)

		self.update_timer = QTimer()
		self.update_timer.setSingleShot(True)
		self.update_timer.setInterval(UPDATES_DEBOUNCE)
		self.update_timer.timeout.connect(self.slot_updated)

		main_layout = QVBoxLayout()
		main_layout.setContentsMargins(8,4,8,4) # left, top, right, bottom
		main_layout.setSpacing(8)

		title_label = QLabel(self.instrument.name)
		title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
		title_label.setObjectName('title')
		main_layout.addWidget(title_label)

		tracks_labels_layout = QVBoxLayout()
		tracks_labels_layout.setSpacing(0)
		self.path_labels = VListLayout()
		self.path_labels.setSpacing(0)
		self.path_labels.setContentsMargins(0,0,0,0)
		self.sample_count_label = QLabel('[No samples]', self)
		self.sample_count_label.setFixedHeight(TRACK_HEIGHT)
		self.sample_count_label.setMinimumWidth(LABEL_WIDTH)
		self.sample_count_label.setFont(self.button_font)
		self.sample_count_label.setEnabled(False)
		tracks_labels_layout.insertSpacing(-1, TRACK_HEIGHT)
		tracks_labels_layout.addLayout(self.path_labels)
		tracks_labels_layout.addWidget(self.sample_count_label)

		tracks_velo_layout = QVBoxLayout()
		tracks_velo_layout.setSpacing(0)
		self.tracks = VListLayout()
		self.tracks.setSpacing(0)
		self.tracks.setContentsMargins(0,0,0,0)
		self.tracks.sig_len_changed.connect(self.slot_track_len_changed)
		pad = Pad(self)
		tracks_velo_layout.addWidget(Scale(self))
		tracks_velo_layout.addLayout(self.tracks)
		tracks_velo_layout.addWidget(pad)

		tracks_buttons_layout = QVBoxLayout()
		tracks_buttons_layout.setSpacing(0)
		self.button_tracks = VListLayout()
		self.button_tracks.setSpacing(0)
		self.button_tracks.setContentsMargins(0,0,0,0)
		tracks_buttons_layout.insertSpacing(-1, TRACK_HEIGHT)
		tracks_buttons_layout.addLayout(self.button_tracks)
		tracks_buttons_layout.insertSpacing(-1, TRACK_HEIGHT)

		tracks_layout = QHBoxLayout()
		tracks_layout.addLayout(tracks_labels_layout)
		tracks_layout.addLayout(tracks_velo_layout)
		tracks_layout.addLayout(tracks_buttons_layout)
		tracks_layout.addStretch()

		self.spread_button = QPushButton('Spread')
		self.spread_button.setFixedHeight(TRACK_HEIGHT - 4)
		self.chk_crossfade = QCheckBox('Cross fade', self)
		self.chk_snap = QCheckBox('Snap', self)
		lbl_pan = QLabel('Pan:', self)
		self.sld_pan = QSlider(self)
		self.sld_pan.setOrientation(Qt.Horizontal)
		self.sld_pan.setMinimum(-100)
		self.sld_pan.setMaximum(100)
		self.sld_pan.setTickInterval(50)
		self.sld_pan.setTickPosition(QSlider.TicksBelow)

		self.spread_button.setFont(self.button_font)
		self.chk_crossfade.setFont(self.button_font)
		self.chk_snap.setFont(self.button_font)
		lbl_pan.setFont(self.button_font)

		self.spread_button.setEnabled(False)
		self.chk_crossfade.setEnabled(False)
		self.chk_snap.setEnabled(False)
		self.sld_pan.setEnabled(False)

		options_layout = QHBoxLayout()
		options_layout.setContentsMargins(4, 0, 4, 0)
		options_layout.setSpacing(4)
		options_layout.addWidget(self.spread_button)
		options_layout.addSpacing(4)
		options_layout.addWidget(self.chk_crossfade)
		options_layout.addWidget(self.chk_snap)
		options_layout.addSpacing(4)
		options_layout.addWidget(lbl_pan)
		options_layout.addWidget(self.sld_pan)
		options_layout.addStretch()

		main_layout.addLayout(tracks_layout)
		main_layout.addStretch()
		main_layout.addLayout(options_layout)

		self.setLayout(main_layout)

		self.spread_button.clicked.connect(self.slot_spread)
		self.chk_crossfade.stateChanged.connect(self.slot_crossfade_state_change)
		self.chk_snap.stateChanged.connect(self.slot_snap_state_change)
		self.sld_pan.valueChanged.connect(self.slot_pan_changed)
		pad.sig_mouse_press.connect(self.slot_mouse_press)
		pad.sig_mouse_release.connect(self.slot_mouse_release)

	def clear(self):
		self.path_labels.clear()
		self.button_tracks.clear()
		self.tracks.clear()

	def load_instrument(self, instrument):
		self.clear()
		self.instrument = instrument
		with SigBlock(self.sld_pan):
			self.sld_pan.setValue(self.instrument.pan)
		for sample in self.instrument.samples.values():
			self._add_sample(sample)
		self.enab_updown_buttons()

	def add_sample(self, path):
		if path in self.instrument.samples:
			logging.warning('%s already in %s samples', path, self.instrument.name)
			return
		self._add_sample(self.instrument.add_sample(path))
		self.enab_updown_buttons()
		self.sfz_updated()

	def _add_sample(self, sample):
		sample_track = SampleTrack(self, sample)
		sample_track.sig_range_changed.connect(self.slot_range_changed)
		sample_track.sig_value_changed.connect(self.slot_value_changed)
		self.tracks.append(sample_track)

		label = QLabel(basename(sample.path), self)
		label.setToolTip(sample.path)
		label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
		label.setFixedHeight(TRACK_HEIGHT)
		self.path_labels.append(label)

		button_track = ButtonsTrack(self, sample)
		with SigBlock(
			button_track.spin_volume,
			button_track.spin_transpose,
			button_track.spin_tune
		):
			button_track.spin_volume.setValue(sample.volume)
			button_track.spin_transpose.setValue(sample.transpose)
			button_track.spin_tune.setValue(sample.tune)
		button_track.sig_value_changed.connect(self.slot_value_changed)
		button_track.sig_move_up.connect(partial(self.slot_move_up,
			label, sample_track, button_track))
		button_track.sig_move_down.connect(partial(self.slot_move_down,
			label, sample_track, button_track))
		button_track.sig_delete.connect(partial(self.slot_delete,
			label, sample_track, button_track))
		self.button_tracks.append(button_track)

	def sfz_updated(self):
		self.sig_updating.emit()
		self.update_timer.start()

	@pyqtSlot()
	def slot_updated(self):
		self.sig_updated.emit()

	@pyqtSlot(int)
	def slot_mouse_press(self, velocity):
		self.sig_mouse_press.emit(self.instrument.pitch, velocity)

	@pyqtSlot()
	def slot_mouse_release(self):
		self.sig_mouse_release.emit(self.instrument.pitch)

	@pyqtSlot()
	def slot_track_len_changed(self):
		cnt = len(self.tracks)
		enab = cnt > 1
		self.spread_button.setEnabled(enab)
		self.chk_crossfade.setEnabled(enab)
		self.chk_snap.setEnabled(enab)
		self.sample_count_label.setText('(1 sample)' if cnt == 1 else f'({cnt} samples)')

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
		self.instrument.pan = value
		self.sfz_updated()

	@pyqtSlot()
	def slot_spread(self):
		spread = 127 / len(self.tracks)
		for i in range(len(self.tracks)):
			self.tracks[i].lovel = round(i * spread)
			self.tracks[i].hivel = round((i + 1) * spread)
		self.find_overlaps()
		self.sfz_updated()

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
		self.sfz_updated()
		if self.snap:
			other_tracks = list(set(self.tracks) ^ set([source_track]))
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

	@pyqtSlot()
	def slot_value_changed(self):
		self.sfz_updated()

	@pyqtSlot(QWidget, QWidget, QWidget)
	def slot_move_up(self, label, sample_track, button_widget):
		self.path_labels.move_up(label)
		self.tracks.move_up(sample_track)
		self.button_tracks.move_up(button_widget)
		self.enab_updown_buttons()

	@pyqtSlot(QWidget, QWidget, QWidget)
	def slot_move_down(self, label, sample_track, button_widget):
		self.path_labels.move_down(label)
		self.tracks.move_down(sample_track)
		self.button_tracks.move_down(button_widget)
		self.enab_updown_buttons()

	@pyqtSlot(QWidget, QWidget, QWidget)
	def slot_delete(self, label, sample_track, button_widget):
		self.instrument.remove_sample(sample_track.sample.path)
		self.path_labels.remove(label)
		self.tracks.remove(sample_track)
		self.button_tracks.remove(button_widget)
		self.enab_updown_buttons()

	def enab_updown_buttons(self):
		self.sld_pan.setEnabled(bool(self.button_tracks))
		if bool(self.button_tracks):
			self.button_tracks[0].up_button.setEnabled(False)
			self.button_tracks[0].up_button.setIcon(ButtonsTrack.icon_up_disabled)
			for button_track in self.button_tracks[1:]:
				button_track.up_button.setEnabled(True)
				button_track.up_button.setIcon(ButtonsTrack.icon_up_enabled)
			for button_track in self.button_tracks[:-1]:
				button_track.down_button.setEnabled(True)
				button_track.down_button.setIcon(ButtonsTrack.icon_down_enabled)
			self.button_tracks[-1].down_button.setEnabled(False)
			self.button_tracks[-1].down_button.setIcon(ButtonsTrack.icon_down_disabled)

	def find_overlaps(self):
		self.clear_overlaps()
		for t in combinations(self.tracks, 2):
			overlap = t[0].overlap(t[1])
			if overlap:
				t[0].overlaps.append(overlap)
				t[1].overlaps.append(overlap)
		for sample_track in self.tracks:
			sample_track.update_velcurves()

	def clear_overlaps(self):
		for sample_track in self.tracks:
			sample_track.overlaps = []


#  end kitstarter/gui/samples_widget.py
