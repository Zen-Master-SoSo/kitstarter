#  kitbash/drumkits.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
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
				for region in sfz.regions_for(key = pitch, lokey = pitch, hikey = pitch):
					opcodes = region.inherited_opcodes()
					if 'pan' in opcodes:
						instrument._pan = opcodes['pan'].value
					for region_sample in region.samples():
						starter_sample = StarterSample(region_sample.abspath, pitch)
						opcodes = region_sample.parent.inherited_opcodes()
						if 'lovel' in opcodes:
							starter_sample._lovel = opcodes['lovel'].value
						if 'hivel' in opcodes:
							starter_sample._hivel = opcodes['hivel'].value
						if 'volume' in opcodes:
							starter_sample._volume = opcodes['volume'].value
						if 'transpose' in opcodes:
							starter_sample._transpose = opcodes['transpose'].value
						if 'tune' in opcodes:
							starter_sample._tune = opcodes['tune'].value
						for code, opcode in region.opcodes.items():
							if code.startswith('amp_velcurve'):
								starter_sample._velcurves.append(Velcurve(int(code[13:]), float(opcode.value)))
						instrument.samples[starter_sample.path] = starter_sample

	def samples(self):
		for instrument in self.instruments:
			yield from instrument.samples.values()

	def is_dirty(self):
		return any(instrument.is_dirty() for instrument in self.instruments.values())

	def clear_dirty(self):
		for instrument in self.instruments.values():
			instrument.clear_dirty()

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
		self._pan = 0
		self._dirty = False

	def __str__(self):
		return self.name

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

	@property
	def pan(self):
		return self._pan

	@pan.setter
	def pan(self, value):
		self._pan = value
		self._dirty = True

	def is_dirty(self):
		return self._dirty or \
			any(sample.dirty for sample in self.samples.values())

	def clear_dirty(self):
		self._dirty = False
		for sample in self.samples.values():
			sample.dirty = False

	def write(self, stream):
		stream.write(f'// "{self.name}" ({self.note_name})\n')
		stream.write(f'<group>\nkey={self.pitch}\n')
		if PITCH_GROUPS[self.pitch] == 'high_hats':
			stream.write('group=88\n')
			stream.write('off_by=88\n')
		if self._pan != 0:
			stream.write(f'pan={self._pan}\n')
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
		self._transpose = 0
		self._tune = 0
		self._velcurves = []
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
	def transpose(self):
		return self._transpose

	@transpose.setter
	def transpose(self, value):
		self._transpose = value
		self.dirty = True

	@property
	def tune(self):
		return self._tune

	@tune.setter
	def tune(self, value):
		self._tune = value
		self.dirty = True

	@property
	def velcurves(self):
		return self._velcurves

	@velcurves.setter
	def velcurves(self, value):
		self._velcurves = value
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
		for point in self._velcurves:
			stream.write(f'amp_velcurve_{point.velocity}={point.amplitude:.1f}\n')
		if self._transpose != 0:
			stream.write(f'transpose={self._transpose}\n')
		if self._tune != 0:
			stream.write(f'tune={self._tune}\n')
		stream.write("\n")


#  end kitbash/drumkits.py
