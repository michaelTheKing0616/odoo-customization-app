from app.bridge.export import PREPARED_FOOTER, prepared_footer


def test_free_always_shows():
    assert prepared_footer(plan_id="free_solo", white_label=False, hide=True) == PREPARED_FOOTER


def test_paid_can_remove():
    assert prepared_footer(plan_id="pro", white_label=False, hide=True) is None
    assert prepared_footer(plan_id="pro", white_label=False, hide=False) == PREPARED_FOOTER


def test_white_label_never_shows_ingenium():
    assert prepared_footer(plan_id="agency", white_label=True, hide=False) is None
