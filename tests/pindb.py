#  kitstarter/tests/pindb.py
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
import os, sys, logging, tempfile
from pprint import pprint
from kitstarter.pindb import PinDatabase

if __name__ == "__main__":
	logging.basicConfig(
		level = logging.DEBUG,
		format = "[%(filename)24s:%(lineno)-4d] %(levelname)-8s %(message)s"
	)

	_, tempfile = tempfile.mkstemp(suffix='.db')
	db = PinDatabase(tempfile)
	home = '/home/user'
	path = f'{home}/sfzs/samples/side_stick.wav'
	pitch = 37
	sfz_path = f'{home}/sfzs/drumkit.sfz'
	db.pin(path, pitch, sfz_path)
	all_pinned = db.all_pinned()
	pinned_by_pitch = db.pinned_by_pitch(pitch)
	pinned_by_sfz = db.pinned_by_sfz(sfz_path)
	assert(all_pinned == pinned_by_pitch)
	assert(all_pinned == pinned_by_sfz)
	assert(db.is_pinned(path))
	assert(not db.is_pinned('gobbledygook'))

	db.conn.close()
	os.unlink(db.path)
	sys.exit(0)


#  end kitstarter/tests/pindb.py
