# KitStarter

kitstarter is a Qt -based program you can use to "sketch in" a drumkit SFZ file.

Its strongest feature is the samples widget, which allows you to use your
mouse to adjust what range of velocities each sample plays at, and
automatically adjust at what proportion multiple samples play at when their
velocity traigger ranges overlap. More on this below.

## The user interface

<img width="967" height="647" alt="kitstarter-main-window" src="https://github.com/user-attachments/assets/b3f13e1d-dae3-431a-9cfe-41c42b05c0b4" />

### Instrument list

You are presented with a window with a list of dumkkit instruments on the left
panel. Once an instrument has been defined, it is indicated on the instrument
list with a check mark.

> "Instrument" here refers to a single piece of the drumkit being assembled,
i.e. "Low-Mid-Tom", or "Crash Cymbal 1".

Selecting an instrument on the instrument list places it in focus. All the
samples which are assigned to that instrument list will show up in the samples
widget.

### Samples widget

The samples widget allows you to adjust the range of velocities which each
sample responds to. You may delete a sample, Adjust the relative volume of that
sample, adjust it's tuning in semitones and cents, and adjust the pan of the
entire group of samples, which comprises an "instrument".

If multiple samples have been assigned to a single instrument, they will be
shown stacked one above the other. Clicking on the button labeled "Spread" will
adjust the velocity range of each sample, so that the sample at the top of the
widget responds to the lowest velocities, the sample at the bottom of the
widget responds to the highest velocities, with each sample taking up an equal
range of MIDI velocities which to respond.

You can use the up/down arrows at the right side of each sample entry to change
the order in which they appear, placing the sample for the quietest parts at
the top, and the samples for the loudest parts at the bottom.

Each sample's velocity range is shown with a graph. The blue area represents
the range at which the sample responds. Clicking on the left side of the range
will set the lowest velocity ("lovel") that the sample is triggered by, and
clicking on the right side of the blue area will set the higest velocity
("hivel").

Checking the box labeled "Snap" causes all the samples' velocity ranges to
be respond to the mouse. If the mouse position in the X axis is near either
bound of any of the sample velocity range graphs, they will be adjusted as the
mouse moves.

The "Cross fade" checkbox allows you to automatically create overlapping
amplitude velocity envelopes for each sample. What a velocity envelope does is
causes the sample to be played at a volume which varies depending on the
incoming MIDI velocity.

#### For instance

Let's say you have three samples of a bass drum. One quiet, one hit with a medium
velocity, and one really loud. These samples are named "bass-drum-low.wav",
"bass-drum-mid.wav", and "bass-drum-high.wav"

You want them to play a these velocities:

| sample           | velocity range |
| ---------------- | -------------- |
| "bass-drum-low"  | 0 - 43         |
| "bass-drum-mid"  | 44 - 86        |
| "bass-drum-high" | 87 - 127       |

But instead of switching abruptly from one to the other, you want to mix them,
so that at velocities near where you transition from one sample to the other,
both are played, but at a different ratio.

That's where the "amplitude velocity envelopes" come in. By overlapping the
highest velocity of one sample with the lowest velocity of the next louder
sample, and introducing an amplitude velocity envelope, you can do just that.

Here's the updated velocity ranges:

| sample           | velocity range |
| ---------------- | -------------- |
| "bass-drum-low"  | 0 - 53         |
| "bass-drum-mid"  | 34 - 96        |
| "bass-drum-high" | 77 - 127       |

You can see, between MIDI velocity 34 - 53, both "bass-drum-low" and
"bass-drum-mid" play. But you don't want them to play at full volume all the
way through the overlap. At the lowest velocity in the overlap, you want
"bass-drum-low" to play at almost its normal volume (just a little less), and
you want "bass-drum-mid" to play very quietly. Together, they should combine to
produce a volume at almost the same level as if either one was played with no
overlap.

As you go up the scale, "bass-drum-mid" should progressively get louder
(relative to its normal volume) until it plays at its normal volume for the
incoming velocity, while "bass-drum-low" does the opposite.

Note that there's no real-time "cross fade" ocurring. That may be a little
misleading. All we're doing is adjusting the *effective* velocity of the sample
when it is triggered, based on where in the overlapping range the incoming MIDI
velocity appears.

### Files and samples

At the bottom of the window, you have the file explorer and the sample
explorer.

The file explorer allows you to select an sfz file. When you have
selected a file, its samples appear in the sample explorer. You can filter the
samples displayed to only show the samples which are triggered by the currently
selected instrument, by checking the "Filter <instrument>" check box.

The samples explorer shows you the currently selected samples. If the
samplerate of the file is the same as the samplerate of the JACK server, it
shows as okay. If the samplerate of the sample differs from that of the JACK
server, it shows a warning symbol. This is relevant because during playback
it's impossible (or at least, very difficult), to change the rate when it gets
sent to the JACK server. So what you hear may not be exactly what you get!

Clicking on a sample in the samples explorer plays the sample. Releasing the
mouse button stops it from playing. Right clicking on the sample brings up a
context menu, with the following commands:

1. Pin
2. Use "<sample>" for "<instrument>"
3. Copy path to clipboard

#### "Pinning" samples

"Pinning" samples makes them available in the samples explorer, regardless
which SFZ or audio file, if any, is selected in the files explorer. You can
choose whether or not to display pinned samples using the "Show pinned"
checkbox. Deselecting the "Show selected" checkbox causes *only* pinned samples
to be displayed.

Pinned samples persist between uses, so you can use this feature to keep a list
of your favorite samples on disk.

## Saving files

When you're satisfied with the sound of your kit (or just need to take a break
for awhile), clicking on "File" -> "Save as.." in the main menu brings up a
file dialog which allows you to choose where to save your newly created SFZ.

The newly saved SFZ points to the *original samples* that you used to construct
it with. If you would like to gather all the samples in a single folder, the
best option, at the moment, is to use the "**sfz-copy**" script which comes as
part of the [sfzen](https://pypi.org/project/sfzen/) package.

"sfz-copy" allows you to copy an SFZ to another location along with its
samples. The help text for sfz-copy shows which options are available:

```bash
--copy, -c      Copy samples to the target samples folder (default).
--symlink, -s   Create symlinks in the target samples folder.
--hardlink, -l  Hardlink samples in the target samples folder.
--abspath, -a   Point to the original samples - absolute path.
--relative, -r  Point to the original samples - relative path.
```

Obviously, only the first option will truly make a *copy* of the source
samples. All the other options either create links to the originals, or point
to the originals using the sample path.

##

That's a quick rundown. If you have questions or feedback, please use the issue
tracker at [github.com](https://github.com/Zen-Master-SoSo/kitstarter/), where this project is hosted.





