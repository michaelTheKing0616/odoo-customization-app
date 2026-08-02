"""Power Ops mastery packs present (M4)."""

from app.power_ops_recipes import get_recipe, list_recipes, probe_recipe


def test_m4_pack_recipes_registered() -> None:
    ids = {r["id"] for r in list_recipes()}
    assert "mass_archive_partners" in ids
    assert "drop_mail_activities_done" in ids
    assert "reset_sequences_next" in ids
    assert "unpublish_website_pages" in ids
    assert "mass_archive_project_tasks" in ids
    partners = get_recipe("mass_archive_partners")
    assert partners is not None
    assert "pack" in partners.tags
    assert partners.min_major == 16
    assert partners.model == "res.partner"
    assert partners.destructive is True
    assert any(s.kind == "write" for s in partners.steps)


def test_m4_mail_pack_requires_mail_module() -> None:
    recipe = get_recipe("drop_mail_activities_done")
    assert recipe is not None
    assert "mail" in recipe.requires_modules
    assert recipe.min_major == 16
    mail_msg = get_recipe("drop_mail_messages")
    assert mail_msg is not None
    assert "mail" in mail_msg.requires_modules


def test_m4_p1_website_project_requires_modules() -> None:
    web = get_recipe("unpublish_website_pages")
    assert web is not None
    assert web.requires_modules == ["website"]
    assert web.model == "website.page"
    proj = get_recipe("mass_archive_project_tasks")
    assert proj is not None
    assert proj.requires_modules == ["project"]
    assert proj.model == "project.task"


def test_m4_sequence_pack_risks_documented() -> None:
    recipe = get_recipe("reset_sequences_next")
    assert recipe is not None
    assert recipe.destructive is True
    assert any("numbering" in r.lower() or "production" in r.lower() for r in recipe.risks)


def test_probe_recipe_respects_min_major_on_pack() -> None:
    class Caps:
        major = 15

    class Client:
        capabilities = Caps()

        def model_exists(self, _m: str) -> bool:
            return True

        def execute_kw(self, *a, **k):
            return [{"state": "installed"}]

    recipe = get_recipe("mass_archive_partners")
    assert recipe is not None
    ok, reason = probe_recipe(Client(), recipe, "res.partner")  # type: ignore[arg-type]
    assert ok is False
    assert "16" in reason


def test_probe_recipe_unavailable_when_website_missing() -> None:
    class Caps:
        major = 19

    class Client:
        capabilities = Caps()

        def model_exists(self, m: str) -> bool:
            return m == "website.page"

        def execute_kw(self, model, method, args, kwargs=None):
            if model == "ir.module.module":
                return [{"name": "website", "state": "uninstalled"}]
            return True

    recipe = get_recipe("unpublish_website_pages")
    assert recipe is not None
    ok, reason = probe_recipe(Client(), recipe, "website.page")  # type: ignore[arg-type]
    assert ok is False
    assert "website" in reason.lower() or "not installed" in reason.lower()


def test_probe_recipe_unavailable_when_project_missing() -> None:
    class Caps:
        major = 19

    class Client:
        capabilities = Caps()

        def model_exists(self, m: str) -> bool:
            return m == "project.task"

        def execute_kw(self, model, method, args, kwargs=None):
            if model == "ir.module.module":
                return [{"name": "project", "state": "uninstalled"}]
            return True

    recipe = get_recipe("mass_archive_project_tasks")
    assert recipe is not None
    ok, reason = probe_recipe(Client(), recipe, "project.task")  # type: ignore[arg-type]
    assert ok is False
    assert "project" in reason.lower() or "not installed" in reason.lower()
