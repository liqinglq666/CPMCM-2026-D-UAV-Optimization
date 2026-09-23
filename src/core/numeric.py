"""Fail explicitly on invalid physical inputs instead of clipping them."""

import math


def finite(value: float, name: str, minimum=None, maximum=None) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite: {value}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}: {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}: {value}")
    return value


def positive(value: float, name: str) -> float:
    value = finite(value, name, 0)
    if value == 0:
        raise ValueError(f"{name} must be positive")
    return value


def lexicographic_less(candidate, incumbent, tolerances):
    """Compare objectives without letting summation noise outrank the next one."""
    for left, right, tolerance in zip(candidate, incumbent, tolerances, strict=True):
        if left < right - tolerance:
            return True
        if left > right + tolerance:
            return False
    return False
