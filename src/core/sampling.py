"""Numerical audit policy, separate from the official radio/flight equations.

Phase-wise equal subdivisions are not nested when their ceil counts differ.
Keep both the original 1 s grid and the 0.5 s replay grid; a caller may add a
finer grid but cannot remove either mandatory acceptance grid. This is still
sampled evidence, not a certificate of continuous-time coverage.
"""

from src.core.communication import sample_states
from src.core.numeric import positive


def audit_steps(step_s=1.0):
    positive(step_s, "communication step_s")
    if step_s > 1.0:
        raise ValueError("Q3 final communication audit must use a step <= 1 s")
    return tuple(sorted({1.0, 0.5, float(step_s)}, reverse=True))


def sample_audit_states(profile, physics, step_s=1.0):
    """Chronological exact union, retaining every state from every audit grid."""
    states = {
        state
        for step in audit_steps(step_s)
        for state in sample_states(profile, physics, step)
    }
    yield from sorted(states)
