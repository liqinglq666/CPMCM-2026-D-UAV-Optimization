from src.q4.partition import max_overlap


def test_max_overlap() -> None:
    intervals = [
        (0.0, 10.0),
        (2.0, 5.0),
        (5.0, 8.0),
        (10.0, 12.0),
    ]
    # End events are processed before start events at the same instant.
    assert max_overlap(intervals) == 2


def test_empty_overlap() -> None:
    assert max_overlap([]) == 0
