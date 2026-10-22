from app.ai_domain_packs import curated_pack_has
from app.ai_generate_ir import GenerateIR, Proposal, proposal_allowed


def _ir() -> GenerateIR:
    from app.ai_generate_ir import build_ir
    return build_ir({"models": []}, constraint_ast=None)


def test_curated_pack_model_admitted_by_code():
    p = Proposal(kind="model", name="x_lib_book", payload={"pack_provenance": {"pack": "library_management", "curated": True}},
                 source_cue="lib_book", rationale="", proposer="domain_pack", confidence=0.9)
    assert proposal_allowed(p, ir=_ir()) == (True, "curated_pack")


def test_forged_provenance_rejected():
    for pack, name in [("library_management", "x_invented_thing"), ("restaurant", "x_dining_table"), ("made_up", "x_lib_book")]:
        p = Proposal(kind="model", name=name, payload={"pack_provenance": {"pack": pack, "curated": True}},
                     source_cue="zzz", rationale="", proposer="domain_pack", confidence=0.9)
        ok, why = proposal_allowed(p, ir=_ir())
        assert not (ok and why == "curated_pack"), (pack, name)
    assert not curated_pack_has("library_management", "x_lib_book", "x_not_a_field")
