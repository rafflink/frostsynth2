import itertools
from fractions import Fraction
import re

from .key import PITCHES
from ..note import Note


class Bar(object):
    def __init__(self, kind, time=None):
        self.kind = kind
        self.time = time

    def __repr__(self):
        return "{}({!r}, {!r})".format(self.__class__.__name__, self.kind, self.time)

    def __lt__(self, other):
        return self.time < other.time

    def copy(self):
        return self.__class__(self.kind, self.time)


HEADER_SPECS = [
    ("UNIT_LENGTH", r'\s*L: *(\d+(/\d+)?)\n'),
    ("TEMPO", r'\s*Q: *((\d+(/\d+)?)=)?(\d+)\n'),
    ("KEY", r'\s*K: *([A-G](#|b)?m?)\n'),
    ("ID", r'\s*X: *\d+'),
    ("TITLE", r'\s*T:.*\n'),
    ("NOTES", r'\s*N:.*\n'),
    ("PARTS", r'\s*P:.*\n'),
    ("INSTRUCTION", r'\s*I:.*\n'),
    ("TRANSCRIPTION", r'\s*Z:.*\n'),
    ("AREA", r'\s*A:.*\n'),
    ("ORIGIN", r'\s*O:.*\n'),
    ("RYTHM", r'\s*R:.*\n'),
    ("BOOK", r'\s*B:.*\n'),
    ("DISCOGRAPHY", r'\s*D:.*\n'),
    ("HISTORY", r'\s*H:.*\n'),
    ("FILE", r'\s*F:.*\n'),
    ("SOURCE", r'\s*S:.*\n'),
    ("GROUP", r'\s*G:.*\n'),
    ("METER", r'\s*M:.*\n'),
    ("COMPOSER", r'\s*C:.*\n'),
    ("NEWLINE", r'\s*\n'),
    ("BODY", r'.'),
]


NOTE_SPECS = [
    ("NOTE", r'(|\^|_|=)([A-Ga-g]|z)'),
    ("GROUP", r'\[([A-Ga-d]|\d+)*?\]'),
    ("THIN_THICK_BAR", r'\|\]'),
    ("THIN_THIN_BAR", r'\|\|'),
    ("THICK_THIN_BAR", r'\[\|'),
    ("START_REPEAT", r'\|:'),
    ("END_REPEAT", r':\|'),
    ("START_END_REPEAT", r'\::'),
    ("FIRST_REPEAT", r'\[1'),
    ("SECOND_REPEAT", r'\[2'),
    ("BAR", r'\|'),
    ("CHORD_SYMBOL", r'".*?"'),
    ("DURATION", r'\d+'),
    ("INVERT_DURATION", r'/'),
    ("OCTAVE_UP", r"'"),
    ("OCTAVE_DOWN", r','),
    ("MISMATCH", r'.'),
]


BARS = ("BAR", "THICK_THIN_BAR", "THIN_THIN_BAR", "THIN_THICK_BAR", "START_REPEAT", "END_REPEAT", "START_END_REPEAT")


HEADER_REGEX = '|'.join('(?P<{}>{})'.format(*pair) for pair in HEADER_SPECS)
NOTE_REGEX = '|'.join('(?P<{}>{})'.format(*pair) for pair in NOTE_SPECS)


def score_to_notes(score, as_floats=True):
    unit_length = Fraction(1)
    tempo_multiplier = Fraction(1)
    key = "C"
    for mo in re.finditer(HEADER_REGEX, score):
        kind = mo.lastgroup
        value = mo.group(kind)
        if kind == "UNIT_LENGTH":
            unit_length = Fraction(mo.groups()[1])
        elif kind == "TEMPO":
            unit = mo.groups()[5] or "1/4"
            bpm = mo.groups()[7]
            tempo_multiplier = Fraction(60, int(bpm)) / Fraction(unit)
        elif kind == "KEY":
            key = mo.groups()[9]
            if key not in PITCHES.keys():
                raise NotImplementedError("Key signature {} not implemented yet".format(key))
        elif kind == "BODY":
            pitches = PITCHES[key]
            tempo_multiplier *= unit_length
            for note in score_body_to_notes(score[mo.start():], pitches, as_floats):
                note.duration *= tempo_multiplier
                note.time *= tempo_multiplier
                yield note
            return


def score_body_to_notes(score, pitches, as_floats=True):
    elements = list(score_body_to_elements(score, pitches))
    for note in unravel_bars(elements):
        if as_floats:
            note.duration = float(note.duration)
            note.time = float(note.time)
        yield note


def unravel_bars(elements):
    bars = [e for e in elements if isinstance(e, Bar)]
    repeat_starts = [Bar("START", 0)]
    for bar in bars:
        if bar.kind in ("THICK_THIN_BAR", "THIN_THIN_BAR", "THIN_THICK_BAR", "START_REPEAT", "END_REPEAT", "START_END_REPEAT"):
            repeat_starts.append(bar)
    for bar in bars:
        if bar.kind in ("END_REPEAT", "START_END_REPEAT"):
            repeat_start = max([b for b in repeat_starts if b < bar]).time
            repeat_end = bar.time
            duration = repeat_end - repeat_start
            bar.kind = "THIN_THIN_BAR"
            for element in elements[:]:
                if repeat_start <= element.time < repeat_end:
                    clone = element.copy()
                    clone.time += duration
                    elements.append(clone)
                elif element.time >= repeat_end:
                    element.time += duration
            return unravel_bars(elements)

    return [e for e in elements if isinstance(e, Note)]


def score_body_to_elements(score, pitches):
    time = Fraction(0)
    current_note = None
    current_bar = None
    duration_inverted = False

    class Sentinel(object):
        lastgroup = "NOTE"
        @classmethod
        def group(cls, kind):
            return "z"

    for mo in itertools.chain(re.finditer(NOTE_REGEX, score), [Sentinel]):
        kind = mo.lastgroup
        value = mo.group(kind)
        if kind == "NOTE":
            if current_note is not None:
                if duration_inverted:
                    current_note.duration /= 2
                time += current_note.duration
                if current_note.pitch is not None:
                    yield current_note
            current_note = Note(pitches[value], Fraction(1), time)

            if current_bar is not None:
                current_bar.time = time
                yield current_bar

            current_bar = None
            duration_inverted = False
        elif kind == "DURATION":
            value = int(value)
            if duration_inverted:
                current_note.duration /= value
            else:
                current_note.duration *= value
            duration_inverted = False
        elif kind == "INVERT_DURATION":
            duration_inverted = True
        elif kind == "OCTAVE_UP":
            current_note.pitch += 12
        elif kind == "OCTAVE_DOWN":
            current_note.pitch -= 12
        elif kind in BARS:
            current_bar = Bar(kind)
