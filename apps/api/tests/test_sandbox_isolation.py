import pathlib

import pytest

import app.sandbox as sb


@pytest.mark.parametrize("major", [16, 17, 18, 19, 20])
def test_sandbox_target_never_a_dev_stack(major):
    st = sb.sandbox_stack_for_major(major)
    assert st.project == f"ingenium_sandbox_v{major}"
    assert st.project not in sb.DEV_PROJECTS
    assert st.odoo_container not in sb.DEV_CONTAINERS and st.db_container not in sb.DEV_CONTAINERS
    assert st.odoo_container.startswith("ingenium_sandbox_") and st.db_container.startswith("ingenium_sandbox_")
    assert st.port not in sb.DEV_PORTS and str(st.port) not in {"8069", "8070", "8071", "8073"}
    assert st.compose.name == "docker-compose.ingenium-sandbox.yml"
    assert pathlib.Path(st.addons).resolve() != sb.SANDBOX_ADDONS.resolve()  # never the shared dev addons dir
    dev_files = {"docker-compose.yml", "docker-compose.odoo16.yml", "docker-compose.odoo17.yml",
                 "docker-compose.odoo18.yml", "docker-compose.odoo20.yml"}
    assert st.compose.name not in dev_files
    assert sb.SANDBOX_DB.startswith("ingenium_sandbox_")


def test_all_majors_are_distinct():
    stacks = [sb.sandbox_stack_for_major(m) for m in (16, 17, 18, 19, 20)]
    assert len({s.project for s in stacks}) == 5 and len({s.port for s in stacks}) == 5


@pytest.mark.parametrize("bad", [
    dict(project="odoo20-custom-dev"), dict(odoo_container="odoo20"), dict(db_container="odoo20-db"),
    dict(port=8073), dict(compose=sb.REPO_ROOT / "docker" / "docker-compose.odoo20.yml"),
    dict(addons=sb.SANDBOX_ADDONS)])
def test_guard_refuses_anything_not_ours(bad):
    import dataclasses
    st = dataclasses.replace(sb.sandbox_stack_for_major(20), **bad)
    with pytest.raises(sb.SandboxGuardError):
        sb.assert_isolated(st)


def test_compose_compose_file_has_no_fixed_dev_names():
    text = sb.SANDBOX_COMPOSE.read_text()
    for dev in ("odoo20", "odoo-custom", "8073", "18069"):
        assert dev not in text


def test_docker_is_faked_in_tests():
    import subprocess
    with pytest.raises(RuntimeError):
        subprocess.run(["docker", "ps"])
