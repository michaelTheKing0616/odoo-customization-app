from app.routers.live_demo_copilot import get_disclosure


def test_disclosure_lists_delivery_with_private_panel_default_only() -> None:
    d = {x["id"]: x for x in get_disclosure()["delivery"]}
    assert d["private_whisper"]["available"] and d["private_whisper"]["default"]
    for key in ("meeting_chat", "speak_aloud"):
        assert d[key]["default"] is False
