from __future__ import division
import numpy as np
from scipy.interpolate import interp1d

from . import tau
from . import analysis
from . import chunk
from . import window
from .sampling import sampled, differentiate, integrate, get_sample_rate
from .pitch import ftom, mtof
from .scale import scale_round


def fast_hilbert(data, window_size=1024):
    w = window.pad(window.cosine(window_size), window_size // 2)
    chunks = chunk.chunkify(data, window=w, overlap=4)

    chunks = map(analysis.hilbert, chunks)

    return 4 * chunk.dechunkify(chunks, overlap=4)


def decompose_phase(data, window_size=1024):
    data = fast_hilbert(data, window_size=window_size)

    phase = np.unwrap(np.angle(data)) / tau
    amplitude = abs(data)

    return phase, amplitude


def steps_since_one(phase):
    """
    Find the number of steps since last rotation.
    """
    result = []
    step = 0
    for i, x in enumerate(phase):
        while phase[step] + 1 < x:
            step += 1
        if step == 0:
            result.append(float("inf"))
        else:
            prev = x - phase[step - 1] - 1
            cur = x - phase[step] - 1
            mu = prev / (prev - cur)
            result.append(i - (step - 1 + mu))
    return np.array(result, dtype=float)


@sampled
def decompose_period(data, window_size=1024):
    phase, amplitude = decompose_phase(data, window_size)
    period = steps_since_one(phase)
    # Fill out unknown periods
    for x in period:
        if x != float("inf"):
            period[period == float("inf")] = x
            break
    # Average energy over period
    cumulative_energy = np.cumsum(amplitude ** 2)
    x = np.arange(len(period), dtype=float)
    f = interp1d(x, cumulative_energy, fill_value="extrapolate", bounds_error=False)
    energy = (f(x + 0.5 * period) - f(x - 0.5 * period)) / period
    return period / get_sample_rate(), np.sqrt(energy)


@sampled
def decompose_frequency(data, window_size=1024):
    phase, amplitude = decompose_phase(data, window_size)
    frequency = differentiate(phase)
    return frequency, amplitude


def clean_frequency(frequency, amplitude, window_size=1024):
    w = window.cosine(window_size)
    weighted_frequency = np.convolve(frequency * amplitude, w)
    average_weight = np.convolve(amplitude, w)
    return (
        weighted_frequency / (average_weight + (average_weight == 0)),
        average_weight / w.sum()
    )


@sampled
def recompose_frequency(frequency, amplitude):
    phase = integrate(frequency)
    return np.sin(tau * phase) * amplitude


def fillnan(data):
    """
    Fills out nan gaps in the data half way forward and backward
    """
    nans = np.isnan(data)

    i = 0
    while nans[i]:
        i += 1
        last = data[i]
        run_length = 2 * i

    run_length = 0
    for i, value, isnan in zip(range(len(data)), data, nans):
        if isnan:
            data[i] = last
            run_length += 1
        else:
            if run_length:
                data[i-run_length//2:i] = value
                run_length = 0
            last = value


def run_lengths(data):
    result = []
    last = float("nan")
    length = 0
    for value in data:
        if value == last:
            length += 1
        else:
            result.extend([length] * length)
            length = 1
        last = value
    result.extend([length] * length)
    return np.array(result)


def autotune(frequency, amplitude, threshold, scale=None, min_duration=None):
    frequency = frequency.copy()
    frequency[amplitude < threshold] = float("nan")
    pitch = scale_round(ftom(frequency), scale)

    if min_duration:
        pitch[run_lengths(pitch) < min_duration] = float("nan")

    fillnan(pitch)

    return mtof(pitch)
