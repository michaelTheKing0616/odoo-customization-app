import copy
import random

from app.ai_conversation.app_design import AppDesign, DesignField, DesignModel, StockExtension
from app.ai_conversation.model_authorizer import apply_calls, authorize_models, dangling_refs

F = DesignField


def M(name, label, fields, **kw):
    ev = kw.pop("evidence", None)
    m = DesignModel(name=name, label=label, fields=[F(name="x_name", string="Name"), *fields], **kw)
    if ev is not None:  # DesignModel.evidence lands with the step-3 schema change
        object.__setattr__(m, "evidence", ev)
    return m


def verdicts(design, brief):
    return {c.model: c.verdict for c in authorize_models(design, brief=brief).calls}


SALON = "so like the salon, uh, appointments, which stylist, which service, the time, and um if the person no show we mark it. also future we fit do loyalty points but later."


def salon_design():
    return AppDesign(new_models=[
        M("x_salon_service", "Salon Service", [F(name="x_category", string="Category", ttype="selection", selection=[["a", "Hair"], ["b", "Nails"]]),
                                               F(name="x_duration", string="Standard Duration in Minutes", ttype="integer"),
                                               F(name="x_price", string="Price", ttype="monetary")]),
        M("x_stylist_schedule", "Stylist Schedule", [F(name="x_day", string="Day of Week", ttype="selection"),
                                                     F(name="x_start", string="Shift Start Time", ttype="float")]),
        M("x_salon_appointment", "Salon Appointment", [
            F(name="x_customer_id", string="Customer", ttype="many2one", relation="res.partner"),
            F(name="x_stylist_id", string="Stylist", ttype="many2one", relation="res.users"),
            F(name="x_service_id", string="Service", ttype="many2one", relation="x_salon_service", required=True),
            F(name="x_time", string="Appointment Time", ttype="datetime"),
            F(name="x_no_show", string="No Show", ttype="boolean")]),
        M("x_loyalty_account", "Loyalty Account", [F(name="x_points", string="Points", ttype="integer")]),
    ], left_out=[{"id": "l1", "item": "loyalty points", "quote": "future we fit do loyalty points but later"}],
        menus=["Salon Service", "Salon Appointment"])


def test_salon_fold_drop_suggest_keep():
    v = verdicts(salon_design(), SALON)
    assert v == {"x_salon_service": "fold", "x_stylist_schedule": "drop", "x_salon_appointment": "keep", "x_loyalty_account": "suggest"}


def test_apply_rewrites_refs_and_notes():
    d = salon_design()
    notes = apply_calls(d, authorize_models(d, brief=SALON))
    appt = d.new_models[0]
    svc = next(f for f in appt.fields if f.string == "Service")
    assert [m.name for m in d.new_models] == ["x_salon_appointment"] and svc.ttype == "char" and svc.required
    assert svc.name == "x_service" and not dangling_refs(d) and d.menus == ["Salon Appointment"] and d.model_budget == 1
    assert any("Salon Service" in n for n in notes) and any("Loyalty" in n for n in notes)


def test_keep_service_history_and_service_catalogue():
    brief = "for every client we keep a service history: each service done, the date, the price, notes"
    d = AppDesign(new_models=[M("x_service_record", "Service Record", [F(name="x_date", string="Date", ttype="date"),
                                                                       F(name="x_price", string="Price", ttype="monetary"),
                                                                       F(name="x_notes", string="Notes", ttype="text")])])
    assert verdicts(d, brief) == {"x_service_record": "keep"}
    brief2 = "We have a list of our services, each with a price and how long it takes"
    d2 = AppDesign(new_models=[M("x_service", "Service", [F(name="x_price", string="Price", ttype="monetary"),
                                                          F(name="x_duration", string="How long it takes (minutes)", ttype="integer")]),
                               M("x_booking", "Booking", [F(name="x_service_id", string="Service", ttype="many2one", relation="x_service")])])
    assert verdicts(d2, brief2)["x_service"] == "keep"


NGO = ("we are an NGO distributing food packs, um, each beneficiary household, how many people, community, and each distribution day "
       "what they collected. donors want report per community monthly. we will maybe integrate with UN system someday.")


def test_ngo_pack_type_and_community_fold():
    d = AppDesign(new_models=[
        M("x_household", "Beneficiary Household", [F(name="x_people", string="How many people", ttype="integer"),
                                                    F(name="x_community_id", string="Community", ttype="many2one", relation="x_community")]),
        M("x_community", "Community", [F(name="x_region", string="Region")]),
        M("x_food_pack_type", "Food Pack Type", [F(name="x_desc", string="Description", ttype="text"),
                                                 F(name="x_contents", string="Standard Contents", ttype="text")]),
        M("x_distribution", "Distribution Day", [F(name="x_date", string="Distribution day", ttype="date"),
                                                 F(name="x_household_id", string="Household", ttype="many2one", relation="x_household"),
                                                 F(name="x_pack_id", string="Food Pack Type", ttype="many2one", relation="x_food_pack_type"),
                                                 F(name="x_collected", string="What they collected", ttype="text")])])
    v = verdicts(d, NGO)
    assert v["x_community"] == "fold" and v["x_food_pack_type"] == "fold"
    assert v["x_household"] == "keep" and v["x_distribution"] in ("keep", "keep_line")


GEN = "Our estate shares one diesel generator. Track fuel purchases (litres, cost, date) and who paid. The generator is serviced by an outside company, we don't track that."


def test_generator_inventions_dropped():
    d = AppDesign(new_models=[
        M("x_fuel_purchase", "Fuel Purchase", [F(name="x_litres", string="Litres", ttype="float"), F(name="x_cost", string="Cost", ttype="monetary"),
                                               F(name="x_date", string="Date", ttype="date"),
                                               F(name="x_paid_by", string="Who paid", ttype="many2one", relation="res.partner")]),
        M("x_generator_log", "Generator Log", [F(name="x_hours", string="Current Running Hours", ttype="float"),
                                               F(name="x_level", string="Current Fuel Level Estimate", ttype="float")]),
        M("x_resident_share", "Resident Share", [F(name="x_period", string="Billing Period"),
                                                 F(name="x_amount", string="Allocated Share Amount", ttype="monetary"),
                                                 F(name="x_status", string="Payment Status", ttype="selection")])])
    v = verdicts(d, GEN)
    assert v == {"x_fuel_purchase": "keep", "x_generator_log": "drop", "x_resident_share": "drop"}


def test_laundering_and_overclaim():
    brief = "We fix cars. Each job card has the car plate and the mechanic."
    laundered = M("x_part_catalog", "Part Catalog", [F(name="x_price", string="Price", ttype="monetary")],
                  evidence={"quote": "Each job card has the car plate", "owner_fields": ["the car plate"], "role": "own_records"})
    d = AppDesign(new_models=[laundered])
    assert verdicts(d, brief)["x_part_catalog"] == "drop"  # real quote, not bound to the label
    over = M("x_mechanic", "Mechanic", [F(name="x_skill", string="Skill")],
             evidence={"quote": "the mechanic", "owner_fields": [], "role": "main_record"})
    job = M("x_job_card", "Job Card", [F(name="x_plate", string="Car plate"), F(name="x_mech_id", string="Mechanic", ttype="many2one", relation="x_mechanic")],
            evidence={"quote": "Each job card has the car plate and the mechanic", "owner_fields": ["the car plate"], "role": "main_record"})
    d2 = AppDesign(new_models=[over, job])
    v = verdicts(d2, brief)
    assert v["x_mechanic"] == "fold"  # main_record claim without a contract record role falls to the own-attribute test
    assert v["x_job_card"] == "keep" or v["x_job_card"] == "drop"  # only the over-claim matters here


def test_contract_record_role_keeps():
    brief = "We fix cars. Each job card has the car plate and the mechanic."
    m = M("x_job_card", "Job Card", [F(name="x_plate", string="Car plate")], requirement_ids=["r1"],
          evidence={"quote": "Each job card", "owner_fields": ["the car plate"], "role": "main_record"})
    d = AppDesign(new_models=[m], intent_contract=[{"id": "r1", "role": "record", "evidence": {"quote": "Each job card has the car plate"}}])
    assert verdicts(d, brief) == {"x_job_card": "keep"}


def test_properties_idempotent_order_independent_never_adds():
    d = salon_design()
    first = verdicts(d, SALON)
    for _ in range(5):
        e = copy.deepcopy(d)
        random.shuffle(e.new_models)
        assert verdicts(e, SALON) == first
    apply_calls(d, authorize_models(d, brief=SALON))
    before = {m.name for m in d.new_models}
    assert apply_calls(d, authorize_models(d, brief=SALON)) == [] and {m.name for m in d.new_models} == before


def test_domain_swap_and_filler_do_not_change_verdicts():
    garage = SALON.replace("salon", "garage").replace("stylist", "mechanic").replace("service", "part")
    d = salon_design()
    for m in d.new_models:
        m.label = m.label.replace("Salon", "Garage").replace("Stylist", "Mechanic").replace("Service", "Part")
        for f in m.fields:
            f.string = f.string.replace("Stylist", "Mechanic").replace("Service", "Part")
    d.left_out = [{"id": "l1", "quote": "future we fit do loyalty points but later"}]
    assert list(verdicts(d, garage).values()) == list(verdicts(salon_design(), SALON).values())
    pidgin = SALON.replace("so like", "abeg so like, wetin I wan talk be say").replace("the time", "the time sha")
    assert verdicts(salon_design(), pidgin) == verdicts(salon_design(), SALON)


def test_line_model_kept_under_kept_parent():
    from app.ai_conversation.app_design import AppDesign
    from app.ai_conversation.model_authorizer import authorize_models
    booking = M("x_booking", "Booking", [F(name="x_date", string="Event date"), F(name="x_venue", string="Venue"),
                 F(name="x_line_ids", string="Items", ttype="one2many", relation="x_booking_line")])
    line = M("x_booking_line", "Booking Line", [F(name="x_booking_id", string="Booking", ttype="many2one", relation="x_booking"),
              F(name="x_qty", string="How many")], requirement_ids=["R2"])
    orphan = M("x_note_line", "Note Line", [F(name="x_booking_id", string="Booking", ttype="many2one", relation="x_booking"), F(name="x_txt", string="Text")])
    d = AppDesign(new_models=[booking, line, orphan], intent_contract=[{"id": "R2", "evidence": {"quote": "the items with how many"}, "role": "attribute"}])
    v = {c.model: c.verdict for c in authorize_models(d, brief="each booking has the event date the venue and the items with how many").calls}
    assert v["x_booking"] == "keep" and v["x_booking_line"] == "keep_line" and v["x_note_line"] != "keep_line"
