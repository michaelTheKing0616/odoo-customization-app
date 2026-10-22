from app.ai_client import ai_cache
from app.routers.suite_upkeep import answer_timing


def test_timing_flags_only_real_cache_hits():
    assert answer_timing(True, 0.041) == {"cached": True, "seconds": 0.04}
    assert answer_timing(False, 2.5)["cached"] is False
    assert answer_timing(None, -1)["seconds"] == 0.0


def test_note_hit_sets_context():
    ai_cache.LAST_HIT.set(None)
    ai_cache.note_hit(True)
    assert ai_cache.LAST_HIT.get() is True
