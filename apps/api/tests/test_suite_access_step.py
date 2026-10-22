"""Bulk Setup access step: plan validation, ops, policy, workbook duplicates, column mapping."""
from app import suite_changeset as sc
from app import suite_import as si
from app import suite_setup as ss


def test_access_step_type_registered():
    assert "access" in ss.STEP_TYPES
    assert ss.REVERSIBILITY["access"] == "remove"
    assert ss.CS_OP["access"] == "access.create"


def test_access_op_carries_group_so_policy_allows_it():
    step = {"id": "a1", "type": "access", "cs_op": "access.create",
            "inputs": {"role": "Clerks", "model": "res.partner", "can": {"read": True}}}
    ops = sc.step_ops(step)
    assert ops[0]["params"]["group"] == "Clerks"
    from app.changeset import policy
    assert policy.policy_for_op(ops[0], "staging").get("deny") is not True


def test_prefixed_header_maps_to_name():
    fmeta = {"name": {"string": "Name", "type": "char"}, "list_price": {"string": "Sales Price", "type": "float"}}
    mapping, questions = si.map_columns(["Product Name", "Sales Price"], fmeta)
    assert mapping == {"Product Name": "name", "Sales Price": "list_price"} and not questions
