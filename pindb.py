#  kitstarter/pindb.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
#
import os, logging, re
from operator import attrgetter
from sqlite3 import connect
from appdirs import user_config_dir


class PinDatabase():

	instance = None		# Enforce singleton
	conn = None

	def __new__(cls, path = None):
		if cls.instance is None:
			cls.instance = super().__new__(cls)
		return cls.instance

	@classmethod
	def db_file(cls):
		try:
			os.mkdir(os.path.join(user_config_dir(), 'ZenSoSo'))
		except FileExistsError:
			pass
		return os.path.join(user_config_dir(), 'ZenSoSo', 'kitstarter-favorites.db')

	@classmethod
	def remove_file(cls):
		try:
			os.remove(cls.db_file())
		except FileNotFoundError:
			pass

	def __init__(self, path = None):
		if self.conn is None:
			self.path = self.db_file() if path is None else path
			self.conn = connect(self.path)
			# self.conn.execute('PRAGMA foreign_keys = ON')
			if len(self.conn.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()) == 0:
				self._init_schema()
			else:
				self.clean()

	def _init_schema(self):
		logging.debug('Initializing schema')
		self.conn.execute("""
			CREATE TABLE pinned(
				path TEXT,
				pitch INTEGER,
				sfz_path TEXT,
				PRIMARY KEY(path)
			)""")

	def dump(self):
		for line in self.conn.iterdump():
			print(line)

	def reset(self):
		self.conn.close()
		os.remove(self.db_file())
		self.conn = connect(self.db_file())
		self._init_schema()

	def clean(self):
		"""
		Deletes all samples that do not exist on the file system
		"""
		cursor = self.conn.execute("""
			SELECT path
			FROM pinned
		""")
		paths = [ result[0] for result in cursor.fetchall() if not os.path.isfile(result[0]) ]
		self.conn.execute("""
			DROP TABLE IF EXISTS selections
		""")
		self.conn.execute("""
			CREATE TEMPORARY TABLE selections (
				path TEXT,
				PRIMARY KEY(path)
			)
		""")
		data = [ (path,) for path in paths]
		self.conn.executemany('INSERT INTO selections(path) VALUES(?)', data)
		self.conn.execute("""
			DELETE FROM pinned
			WHERE ROWID IN (
				SELECT pinned.ROWID FROM pinned JOIN selections USING(path)
			)
		""")
		self.conn.commit()

	def pin(self, path, pitch, sfz_path):
		"""
		Inserts the given sample info
		"""
		self.conn.execute('INSERT OR IGNORE INTO pinned VALUES (?, ?, ?)', (path, pitch, sfz_path))
		self.conn.commit()

	def all_pinned(self):
		"""
		Returns list of tuples (path, pitch, sfz_path).
		"""
		cursor = self.conn.execute("""
			SELECT path, pitch, sfz_path
			FROM pinned
		""")
		return cursor.fetchall()

	def pinned_by_pitch(self, pitch):
		"""
		Returns list of tuples (path, pitch, sfz_path).
		"""
		cursor = self.conn.execute("""
			SELECT path, pitch, sfz_path
			FROM pinned
			WHERE pitch = ?
		""", (pitch, ))
		return cursor.fetchall()

	def pinned_by_sfz(self, sfz_path):
		"""
		Returns list of tuples (path, pitch, sfz_path).
		"""
		cursor = self.conn.execute("""
			SELECT path, pitch, sfz_path
			FROM pinned
			WHERE sfz_path = ?
		""", (sfz_path, ))
		return cursor.fetchall()

	def is_pinned(self, path):
		cursor = self.conn.execute("""
			SELECT path FROM pinned
			WHERE path = ?
		""", (path, ))
		return bool(cursor.fetchall())

	def unpin(self, path):
		self.conn.execute("""
			DELETE FROM pinned
			WHERE path = ?
		""", (path, ))
		self.conn.commit()


#  end kitstarter/pindb.py
