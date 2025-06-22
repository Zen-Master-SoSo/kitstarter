#  kitstarter/gui/samples_widget.py
#
#  Copyright 2025 liyang <liyang@veronica>
#
import logging
from functools import partial
from itertools import combinations
from collections import namedtuple

from PyQt5.QtCore import	Qt, pyqtSignal, pyqtSlot, QPointF, QRectF, QTimer
from PyQt5.QtGui import		QPainter, QColor, QPen, QBrush
from PyQt5.QtWidgets import	QWidget, QVBoxLayout, QHBoxLayout, \
							QCheckBox, QPushButton, QLabel, QSizePolicy

from qt_extras.list_layout import VListLayout


FEATURE_LOVEL = 1
FEATURE_HIVEL = 2
FEATURE_BOTH = 3
SNAP_RANGE = 5
TRACK_HEIGHT = 28
TRACK_WIDTH = 224
UPDATES_DEBOUNCE = 680

Overlap = namedtuple('Overlap', ['lovel', 'hivel', 't1', 't2'])
Velcurve = namedtuple('Velcurve', ['velocity', 'amplitude'])


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
		cls.init_paint_resources()


class _Track(QWidget):
	"""
	Abstract widget which handles scaling between velocity and screen coordinates.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		self.setFixedHeight(TRACK_HEIGHT)
		self.setFixedWidth(TRACK_WIDTH)
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
		(Used when there are no scale points - only lovel, hivel)
		"""
		return self.a2y(self.v2a(velocity))


class SampleTrack(_Track):
	"""
	Graphically displays the effects of lovel, hivel, and amp_velcurve_N.
	"""

	sig_value_changed = pyqtSignal(QWidget, int)

	@classmethod
	def init_paint_resources(cls):
		cls.outline_pen = QPen(QColor("#AAA"))
		cls.outline_pen.setWidth(1)
		cls.envelope_pen = QPen(QColor("#33F"))
		cls.envelope_pen.setWidth(1)
		fill_color = QColor("#DDE")
		cls.fill_brush = QBrush(fill_color, Qt.SolidPattern)

	def __init__(self, parent, sample):
		super().__init__(parent)
		self.sample = sample
		self.sample.lovel = 0
		self.sample.hivel = 127
		self.sample.vtpoints = []
		self.overlaps = []

	def __str__(self):
		return f'SampleTrack for "{self.sample}"'

	def mousePressEvent(self, event):
		self.mouse_event(event)

	def mouseMoveEvent(self, event):
		self.mouse_event(event)

	def mouse_event(self, event):
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
		self.sig_value_changed.emit(self, feature)
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

		if self.sample.vtpoints:
			for vtp in self.sample.vtpoints:
				points.append(QPointF(self.v2x(vtp.velocity), self.a2y(vtp.amplitude)))
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

	def snap_tracks_lo(self, other_tracks):
		"""
		Snap other tracks hivel when this track's lovel changes.
		"""
		for other_track in other_tracks:
			if abs(self.lovel - other_track.hivel) <= SNAP_RANGE:
				other_track.hivel = self.lovel

	def snap_tracks_hi(self, other_tracks):
		"""
		Snap other tracks lovel when this track's hivel changes.
		"""
		for other_track in other_tracks:
			if abs(self.hivel - other_track.lovel) <= SNAP_RANGE:
				other_track.lovel = self.hivel

	def overlap(self, other_track):
		"""
		Used to determine if this track overlaps abother track.
		Returns Overlap(lovel, hivel, self, other), if tracks overlap, else None
		"""
		lovel = max(other_track.lovel, self.lovel)
		hivel = min(other_track.hivel, self.hivel)
		return Overlap(lovel, hivel, self, other_track) \
			if lovel < hivel else None

	def update_vtpoints(self):
		self.sample.vtpoints = []
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
				self.sample.vtpoints.append(Velcurve(self.lovel, 0.0))
				self.sample.vtpoints.append(Velcurve(lo_overlap.hivel, self.v2a(lo_overlap.hivel)))
			else:
				self.sample.vtpoints.append(Velcurve(self.lovel, self.v2a(self.lovel)))
			for mid_overlap in mid_overlaps:
				self.sample.vtpoints.append(Velcurve(mid_overlap.lovel, self.v2a(mid_overlap.lovel)))
				mid_overlap_center = mid_overlap.lovel + round((mid_overlap.hivel -  mid_overlap.lovel) / 2)
				self.sample.vtpoints.append(Velcurve(mid_overlap_center, 0.0))
				self.sample.vtpoints.append(Velcurve(mid_overlap.hivel, self.v2a(mid_overlap.hivel)))
			if hi_overlap:
				self.sample.vtpoints.append(Velcurve(hi_overlap.lovel, self.v2a(hi_overlap.lovel)))
				self.sample.vtpoints.append(Velcurve(self.hivel, 0.0))
			else:
				self.sample.vtpoints.append(Velcurve(self.hivel, self.v2a(self.hivel)))
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

		tracks_layout = QHBoxLayout()
		tracks_left_layout = QVBoxLayout()
		tracks_center_layout = QVBoxLayout()
		tracks_right_layout = QVBoxLayout()
		options_layout = QHBoxLayout()

		tracks_left_layout.setSpacing(0)
		tracks_center_layout.setSpacing(0)
		tracks_right_layout.setSpacing(0)

		tracks_layout.addLayout(tracks_left_layout)
		tracks_layout.addLayout(tracks_center_layout)
		tracks_layout.addLayout(tracks_right_layout)
		tracks_layout.addStretch()

		title_label = QLabel(self.instrument.name)
		title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
		title_label.setObjectName('title')

		main_layout.addWidget(title_label)
		main_layout.addLayout(tracks_layout)
		main_layout.addStretch()
		main_layout.addLayout(options_layout)

		self.path_labels = VListLayout()
		self.path_labels.setSpacing(0)
		self.path_labels.setContentsMargins(0,0,0,0)
		tracks_left_layout.insertSpacing(-1, TRACK_HEIGHT)
		tracks_left_layout.addLayout(self.path_labels)
		self.sample_count_label = QLabel('[No samples]', self)
		self.sample_count_label.setFixedHeight(TRACK_HEIGHT)
		self.sample_count_label.setFont(self.button_font)
		self.sample_count_label.setEnabled(False)
		tracks_left_layout.addWidget(self.sample_count_label)

		self.tracks = VListLayout()
		self.tracks.setSpacing(0)
		self.tracks.setContentsMargins(0,0,0,0)
		self.tracks.sig_size_changed.connect(self.slot_track_len_changed)
		self.pad = Pad(self)
		tracks_center_layout.addWidget(Scale(self))
		tracks_center_layout.addLayout(self.tracks)
		tracks_center_layout.addWidget(self.pad)

		self.remove_buttons = VListLayout()
		self.remove_buttons.setSpacing(0)
		self.remove_buttons.setContentsMargins(0,0,0,0)
		tracks_right_layout.insertSpacing(-1, TRACK_HEIGHT)
		tracks_right_layout.addLayout(self.remove_buttons)
		tracks_right_layout.insertSpacing(-1, TRACK_HEIGHT)

		self.spread_button = QPushButton('Spread')
		self.spread_button.setFixedHeight(TRACK_HEIGHT - 4)
		self.chk_crossfade = QCheckBox('Cross fade', self)
		self.chk_snap = QCheckBox('Snap', self)

		self.spread_button.setFont(self.button_font)
		self.chk_crossfade.setFont(self.button_font)
		self.chk_snap.setFont(self.button_font)

		self.spread_button.setEnabled(False)
		self.chk_crossfade.setEnabled(False)
		self.chk_snap.setEnabled(False)

		options_layout.setContentsMargins(4, 0, 4, 0)
		options_layout.setSpacing(4)
		options_layout.addWidget(self.spread_button)
		options_layout.addSpacing(4)
		options_layout.addWidget(self.chk_crossfade)
		options_layout.addWidget(self.chk_snap)
		options_layout.addStretch()

		self.setLayout(main_layout)

		self.spread_button.clicked.connect(self.slot_spread)
		self.chk_crossfade.stateChanged.connect(self.slot_crossfade_state_change)
		self.chk_snap.stateChanged.connect(self.slot_snap_state_change)
		self.pad.sig_mouse_press.connect(self.slot_mouse_press)
		self.pad.sig_mouse_release.connect(self.slot_mouse_release)

	def clear(self):
		self.path_labels.clear()
		self.remove_buttons.clear()
		self.tracks.clear()
		self.updating()

	def append(self, path):
		if not self.instrument.has_sample(path):
			sample = self.instrument.add_sample(path)
			sample_track = SampleTrack(self, sample)
			sample_track.sig_value_changed.connect(self.slot_value_changed)
			self.tracks.append(sample_track)
			label = QLabel(sample_track.sample.path, self)
			label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
			label.setFixedHeight(TRACK_HEIGHT)
			self.path_labels.append(label)
			button = QPushButton('Remove')
			button.setFont(self.button_font)
			button.setFixedHeight(TRACK_HEIGHT)
			button.clicked.connect(partial(self.slot_remove_track_clicked, label, sample_track, button))
			self.remove_buttons.append(button)
			self.updating()

	def updating(self):
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

	@pyqtSlot(QWidget, QWidget, QWidget)
	def slot_remove_track_clicked(self, label, sample_track, button):
		self.instrument.remove_sample(sample_track.sample.path)
		self.path_labels.remove(label)
		self.tracks.remove(sample_track)
		self.remove_buttons.remove(button)

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
		self.updating()

	@pyqtSlot()
	def slot_spread(self):
		spread = 127 / len(self.tracks)
		for i in range(len(self.tracks)):
			self.tracks[i].lovel = round(i * spread)
			self.tracks[i].hivel = round((i + 1) * spread)
		self.find_overlaps()
		self.updating()

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
	def slot_value_changed(self, source_track, feature):
		self.updating()
		if self.snap:
			other_tracks = list(set(self.tracks) ^ set([source_track]))
			if feature == FEATURE_LOVEL:
				source_track.snap_tracks_lo(other_tracks)
			else:
				source_track.snap_tracks_hi(other_tracks)
		elif self.crossfade:
			self.find_overlaps()

	def find_overlaps(self):
		self.clear_overlaps()
		for t in combinations(self.tracks, 2):
			overlap = t[0].overlap(t[1])
			if overlap:
				t[0].overlaps.append(overlap)
				t[1].overlaps.append(overlap)
		for sample_track in self.tracks:
			sample_track.update_vtpoints()

	def clear_overlaps(self):
		for sample_track in self.tracks:
			sample_track.overlaps = []


#  end kitstarter/gui/samples_widget.py
