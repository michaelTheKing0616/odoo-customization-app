from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from app.dry_run_middleware import DryRunHashMiddleware, is_write_capable

PATH = "/api/ai/sessions/s1/install-apps"


def _client():
    async def ok(request):
        return JSONResponse({"wrote": True})
    app = Starlette(routes=[Route("/api/ai/sessions/{sid}/install-apps", ok, methods=["POST"]),
                            Route("/api/other", ok, methods=["POST"])])
    app.add_middleware(DryRunHashMiddleware)
    return TestClient(app)


def test_gated_route_rejects_form_and_bare_bodies():
    assert is_write_capable("POST", PATH)
    c = _client()
    for kw in ({"data": {"a": "1"}}, {"content": b"x", "headers": {"content-type": "text/plain"}}, {}):
        r = c.post(PATH, **kw)
        assert r.status_code == 403 and r.json()["detail"]["error"] == "dry_run_receipt_required"


def test_ungated_route_still_passes_without_json():
    assert _client().post("/api/other", data={"a": "1"}).json() == {"wrote": True}
