#  kitstarter/gui/__init__.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
#
import logging
from PyQt5.QtWidgets import QSplitter
from kitstarter import PACKAGE_DIR, settings


class GeometrySaver:
	"""
	Provides classes declared in this project which inherit from QDialog methods to
	easily save/restore window / splitter geometry.

	Geometry is saved in this project's QSettings accessed as "settings()"
	"""

	def restore_geometry(self):
		if not hasattr(self, 'restoreGeometry'):
			logging.error('Object of type %s has no "restoreGeometry" function',
				type(self).__name__)
			return
		geometry = settings().value(self.__geometry_key())
		if geometry is not None:
			self.restoreGeometry(geometry)
		for splitter in self.findChildren(QSplitter):
			geometry = settings().value(self.__splitter_geometry_key(splitter))
			if geometry is not None:
				splitter.restoreState(geometry)

	def save_geometry(self):
		if not hasattr(self, 'saveGeometry'):
			logging.error('Object of type %s has no "saveGeometry" function',
				type(self).__name__)
			return
		settings().setValue(self.__geometry_key(), self.saveGeometry())
		for splitter in self.findChildren(QSplitter):
			settings().setValue(self.__splitter_geometry_key(splitter), splitter.saveState())

	def __geometry_key(self):
		return '{}/geometry'.format(type(self).__name__)

	def __splitter_geometry_key(self, splitter):
		return '{}/{}/geometry'.format(type(self).__name__, splitter.objectName())


#  end kitstarter/gui/__init__.py
