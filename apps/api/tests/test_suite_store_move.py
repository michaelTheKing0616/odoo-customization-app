"""Suite plans/batches persist in the shared changeset store; old saved plans migrate with their ids."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import suite_store
from app import view_engine_store as vs
from app.changeset import store as cs
from app.db_models import Base, PlanCardRecord


def _db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_old_plans_migrate_with_same_id_and_old_row_kept_as_undo():
    db = _db()
    old = vs.save_item(db, connection_id="c1", kind="suite_plan", key="plan:setup", name="Old plan",
                       payload={"kind": "setup", "steps": [{"id": "a"}], "check": {"plan_hash": "h"}})
    batch = vs.save_item(db, connection_id="c1", kind="suite_batch", key="batch:x", name="B", payload={"tool": "x"})
    got = suite_store.get_item(db, "c1", old.id)
    assert isinstance(got, cs.SuiteItem) and got.id == old.id and got.name == "Old plan"
    assert suite_store.item_out(got)["payload"]["check"] == {"plan_hash": "h"}
    assert [r.id for r in suite_store.list_items(db, "c1", "suite_batch")] == [batch.id]
    kinds = {r.kind for r in db.query(vs.ViewBuilderItem).all()}
    assert kinds == {"m:suite_plan", "m:suite_batch"}
    assert cs.migrate_suite_items(db) == 0  # idempotent


def test_suite_rows_never_enter_engine_inbox_or_card_list():
    db = _db()
    item = suite_store.save_item(db, connection_id="c1", kind="suite_plan", key="k", name="P", payload={"steps": [1]})
    assert db.get(PlanCardRecord, item.id).status == "suite_plan"
    assert db.get(PlanCardRecord, item.id).plan_hash.startswith("s")
    assert cs.list_plans(db, "c1") == []
    try:
        cs._pending_card(db, db.get(PlanCardRecord, item.id).plan_hash, "c1")
        raise AssertionError("suite row must not be an engine card")
    except Exception as exc:  # InboxError
        assert "not found" in str(exc)


def test_update_and_runs_stay_on_builder_store():
    db = _db()
    item = suite_store.save_item(db, connection_id="c1", kind="suite_plan", key="k", name="P", payload={"steps": [1]})
    item.name = "Renamed"
    suite_store.update_item(db, item, {"steps": [1, 2]})
    again = suite_store.get_item(db, "c1", item.id)
    assert again.name == "Renamed" and again.payload == {"steps": [1, 2]}
    run = suite_store.save_item(db, connection_id="c1", kind="suite_run", key="run:x", name="R", payload={"state": "queued"})
    assert isinstance(run, vs.ViewBuilderItem)
    assert suite_store.get_item(db, "c1", run.id).id == run.id
