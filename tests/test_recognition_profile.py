from collections import Counter
from src.studio.recognition_profile import mixed_note_sizes, recognition_flags


def test_cue_detection_requires_two_repeated_sizes():
    assert mixed_note_sizes(Counter({18: 20, 12: 4}))
    assert not mixed_note_sizes(Counter({18: 20, 12: 1}))
    assert not mixed_note_sizes(Counter({18: 20, 17: 12}))
    assert not mixed_note_sizes(Counter({12: 20}))


def test_raster_auto_leaves_engine_defaults_and_user_can_override():
    assert recognition_flags("auto", b"", ".png", []) == []
    assert recognition_flags("on", b"", ".png", [1])[-1].endswith("smallHeads=true")
    assert recognition_flags("off", b"", ".png", [1])[-1].endswith("smallHeads=false")
