import numpy as np

from .. import tau


def sine(phase):
    return np.sin(tau * phase)


def cosine(phase):
    return np.cos(tau * phase)