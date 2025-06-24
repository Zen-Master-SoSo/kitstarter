#  kitbash/drumkits.py
#
#  Copyright 2025 liyang <liyang@veronica>
#
#
"""
Provides Drumkit SFZ wrapper which allows import / copy operations.
"""
from os.path import abspath, basename
from midi_notes import Note, MIDI_DRUM_IDS, MIDI_DRUM_NAMES
from sfzen.drumkits import pitch_id_tuple

# -----------------------------------------------------------------
# StarterKit classes

class StarterKit:
	"""
	Allows you to construct an sfz file from a basic drumkit structure.
	"""

	def __init__(self):
		self.instruments = { pitch:StarterInstrument(pitch) \
			for pitch in MIDI_DRUM_IDS }

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
loop_mode=no_loop
ampeg_attack=0.001

""")
		for instrument in self.instruments.values():
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
		path = abspath(path)
		return path in self.samples

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
		stream.write(f'<group>\nkey={self.pitch}\n\n')
		for sample in self.samples.values():
			sample.write(stream)
		stream.write("\n")


class StarterSample:

	lovel = None
	hivel = None
	volume = None
	vtpoints = []

	def __init__(self, path, pitch):
		self.path = abspath(path)
		self.pitch = pitch

	def __str__(self):
		return basename(self.path)

	def write(self, stream):
		stream.write('<region>\n')
		stream.write(f'sample={self.path}\n')
		if self.volume != 0.0:
			stream.write(f'volume={self.volume:.2f}\n')
		if self.lovel > 0:
			stream.write(f'lovel={self.lovel}\n')
		if self.hivel < 127:
			stream.write(f'hivel={self.hivel}\n')
		for point in self.vtpoints:
			stream.write(f'amp_velcurve_{point.velocity}={point.amplitude:.1f}\n')
		stream.write("\n")


#  end kitbash/drumkits.py
