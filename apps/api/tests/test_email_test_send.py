from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.view_engine_reports2 import own_address


class DB:
    def __init__(self, user):
        self.user = user

    def get(self, _model, _id):
        return self.user


def test_only_own_address():
    assert own_address(DB(SimpleNamespace(email="tope@example.ng")), SimpleNamespace(user_id="u1")) == "tope@example.ng"


def test_signed_out_refused():
    with pytest.raises(HTTPException):
        own_address(DB(None), SimpleNamespace(user_id=None))
