#  kitbash/drumkits.py
#
#  Copyright 2025 liyang <liyang@veronica>
#
#
"""
Provides Drumkit SFZ wrapper which allows import / copy operations.
"""
import logging
from os.path import abspath, basename
from collections import namedtuple
from midi_notes import Note, MIDI_DRUM_IDS, MIDI_DRUM_NAMES
from sfzen import SFZ
from sfzen.drumkits import Drumkit, PITCH_GROUPS, pitch_id_tuple, iter_pitch_by_group

Velcurve = namedtuple('Velcurve', ['velocity', 'amplitude'])


# -----------------------------------------------------------------
# StarterKit classes

class StarterKit:
	"""
	Allows you to construct an sfz file from a basic drumkit structure.
	"""

	def __init__(self, filename = None):
		self.filename = filename
		self.instruments = { pitch:StarterInstrument(pitch) \
			for pitch in MIDI_DRUM_IDS }
		if self.filename:
			sfz = SFZ(self.filename)
			for pitch, instrument in self.instruments.items():
				for region in sfz.regions_for(key=pitch, lokey=pitch, hikey=pitch):
					for region_sample in region.samples():
						starter_sample = StarterSample(region_sample.abspath, pitch)
						opcodes = region_sample.parent.inherited_opcodes()
						if 'lovel' in opcodes:
							starter_sample._lovel = opcodes['lovel'].value
						if 'hivel' in opcodes:
							starter_sample._hivel = opcodes['hivel'].value
						if 'volume' in opcodes:
							starter_sample._volume = opcodes['volume'].value
						for code, opcode in region.opcodes.items():
							if code.startswith('amp_velcurve'):
								starter_sample._vtpoints.append(Velcurve(int(code[13:]), float(opcode.value)))
						instrument.samples[starter_sample.path] = starter_sample

	def samples(self):
		for instrument in self.instruments:
			yield from instrument.samples.values()

	def is_dirty(self):
		return any(sample.dirty for sample in self.samples())

	def clear_dirty(self):
		for sample in self.samples():
			sample.dirty = False

	def instrument(self, pitch_or_id):
		"""
		Returns StarterInstrument
		"pitch_or_id" may be a pitch or an instrument id string (i.e. "side_stick").
		"""
		pitch, _ = pitch_id_tuple(pitch_or_id)
		return self.instruments[pitch]

	def write(self, stream):
		stream.write("""
<global>
loop_mode=one_shot
ampeg_attack=0.001

""")
		for pitch in iter_pitch_by_group():
			instrument = self.instruments[pitch]
			if len(instrument.samples):
				instrument.write(stream)


class StarterInstrument:
	"""
	Contains basic instrument info which is compiled to .sfz opcodes.
	"""

	def __init__(self, pitch):
		self.pitch = pitch
		self.inst_id = MIDI_DRUM_IDS[pitch]
		self.name = MIDI_DRUM_NAMES[pitch]
		self.note_name = Note(pitch).name
		self.samples = {}

	def __str__(self):
		return self.name

	def has_sample(self, path):
		return abspath(path) in self.samples

	def add_sample(self, path):
		path = abspath(path)
		if path in self.samples:
			raise RuntimeError(f'Cannot add "{path}" - already used')
		self.samples[path] = StarterSample(path, self.pitch)
		return self.samples[path]

	def remove_sample(self, path):
		if not path in self.samples:
			raise IndexError(f'Cannot remove "{path}" - not found in samples')
		del self.samples[path]

	def write(self, stream):
		stream.write(f'// "{self.name}" ({self.note_name})\n')
		stream.write(f'<group>\nkey={self.pitch}\n')
		if PITCH_GROUPS[self.pitch] == 'high_hats':
			stream.write(f'group=88\n')
			stream.write(f'off_by=88\n')
		stream.write("\n")
		for sample in self.samples.values():
			sample.write(stream)
		stream.write("\n")


class StarterSample:

	def __init__(self, path, pitch):
		self.path = abspath(path)
		self.pitch = pitch
		self._lovel = 0
		self._hivel = 127
		self._volume = 0.0
		self._vtpoints = []
		self.dirty = False

	def __str__(self):
		return basename(self.path)

	@property
	def lovel(self):
		return self._lovel

	@lovel.setter
	def lovel(self, value):
		self._lovel = value
		self.dirty = True

	@property
	def hivel(self):
		return self._hivel

	@hivel.setter
	def hivel(self, value):
		self._hivel = value
		self.dirty = True

	@property
	def volume(self):
		return self._volume

	@volume.setter
	def volume(self, value):
		self._volume = value
		self.dirty = True

	@property
	def vtpoints(self):
		return self._vtpoints

	@vtpoints.setter
	def vtpoints(self, value):
		self._vtpoints = value
		self.dirty = True

	def write(self, stream):
		stream.write('<region>\n')
		stream.write(f'sample={self.path}\n')
		if self._volume != 0.0:
			stream.write(f'volume={self._volume:.2f}\n')
		if self._lovel > 0:
			stream.write(f'lovel={self._lovel}\n')
		if self._hivel < 127:
			stream.write(f'hivel={self._hivel}\n')
		for point in self._vtpoints:
			stream.write(f'amp_velcurve_{point.velocity}={point.amplitude:.1f}\n')
		stream.write("\n")


#  end kitbash/drumkits.py
