from app.routers.accounts import clean_display_name


def test_clean_display_name():
    assert clean_display_name("  Tope  ") == "Tope"
    assert clean_display_name("Tope   O") == "Tope O"
    assert clean_display_name("   ") is None
    assert clean_display_name(None) is None
