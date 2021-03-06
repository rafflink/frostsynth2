from .pitch import ftom, mtof
from .sampling import sampled, trange


class Note(object):
    def __init__(self, pitch, duration, time=None, velocity=0.75):
        self.pitch = pitch
        self.duration = duration
        self.time = time
        self.velocity = velocity

    def __hash__(self):
        return hash((self.pitch, self.duration, self.time, self.velocity))

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self.pitch,
            self.duration,
            self.time,
            self.velocity,
        )

    def __eq__(self, other):
        return (
            self.pitch == other.pitch and
            self.duration == other.duration and
            self.time == other.time and
            self.velocity == other.velocity
        )

    @property
    def freq(self):
        if self.pitch is None:
            return None
        return mtof(self.pitch)

    @freq.setter
    def freq(self, value):
        if value is None:
            self.pitch = None
        self.pitch = ftom(value)

    @property
    def off_time(self):
        if self.duration is None:
            return self.time
        return self.time + self.duration

    @sampled
    def get_phase(self, duration):
        return trange(duration) * self.freq

    def copy(self):
        return self.__class__(self.pitch, self.duration, self.time, self.velocity)


class NonPitched(Note):
    def __init__(self, time=None, velocity=0.75):
        super(NonPitched, self).__init__(pitch=None, duration=None, time=time, velocity=velocity)

    # TODO: repr and copy


class Sheet(object):
    def __init__(self, notes=None, duration=None):
        self.notes = [] if notes is None else notes
        self._duration = duration

    def __repr__(self):
        return "{}({!r}, duration={!r})".format(self.__class__.__name__, self.notes, self.duration)

    def __iter__(self):
        return iter(self.notes)

    def __add__(self, other):
        first_part = self.copy()
        second_part = other.copy()
        second_part.shift(self.duration)

        first_part.notes.extend(second_part.notes)
        return first_part

    def __mul__(self, times):
        if times == 0:
            return self.__class__([])
        result = self.copy()
        for _ in range(times - 1):
            result = self + result
        return result

    @property
    def off_time(self):
        return max([n.off_time for n in self.notes])

    @property
    def duration(self):
        if self._duration is None:
            return self.off_time
        return self._duration

    @duration.setter
    def duration(self, value):
        self._duration = value

    def copy(self):
        return self.__class__([n.copy() for n in self.notes], self._duration)

    def shift(self, duration):
        for note in self.notes:
            note.time += duration
        return self

    def transpose(self, interval):
        for note in self.notes:
            note.pitch += interval
        return self

    def dilate(self, amount):
        for note in self.notes:
            note.duration *= amount
            note.time *= amount
        if self. _duration is not None:
            self._duration *= amount
        return self

    def append(self, note):
        self.notes.append(note)
