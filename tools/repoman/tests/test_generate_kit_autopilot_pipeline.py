import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tools" / "ci"))

import generate_kit_autopilot_pipeline as gkap

BASE_ENV = {
    "PUBLISH_NGC_VERSION": "107.0.0-stage.4",
    "PUBLISH_NGC_VERSION_QUALIFIER": "stage",
    "KIT_KERNEL_VERSION": "107.0.0",
    "PUBLISH_NGC_ORG": "nvidia",
    "PUBLISH_NGC_TEAM": "omniverse",
    "CI_COMMIT_SHA": "deadbeef",
    "CI_COMMIT_REF_NAME": "release/107.0",
    "CI_PIPELINE_URL": "https://gitlab/pipe/42",
    "CI_COMMIT_TITLE": "chore: release it's time",
    "GITLAB_USER_LOGIN": "vshastri",
}


def make_env(**overrides):
    env = dict(BASE_ENV)
    env.update(overrides)
    return env


def generate(tmp_path, **overrides):
    """Run the generator against an isolated root and return the written text."""
    child = gkap.generate_pipeline(env=make_env(**overrides), root=tmp_path)
    assert child == tmp_path / gkap.DEFAULT_CHILD_PIPELINE
    assert child.exists()
    return child.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# yaml_quote
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("nvidia", "'nvidia'"),
        ("", "''"),
        (None, "''"),
        ("it's time", "'it''s time'"),
        ("a'b'c", "'a''b''c'"),
    ],
)
def test_yaml_quote_escapes_single_quotes(value, expected):
    assert gkap.yaml_quote(value) == expected


# ---------------------------------------------------------------------------
# stage / rc trigger generation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("qualifier", ["stage", "rc"])
def test_stage_or_rc_generates_kit_autopilot_trigger(tmp_path, qualifier):
    text = generate(tmp_path, PUBLISH_NGC_VERSION_QUALIFIER=qualifier)
    assert "trigger-kit-autopilot:" in text
    assert "project: omniverse/qa/kit-autopilot" in text
    assert "branch: main" in text
    assert "strategy: depend" in text
    assert "skip-kit-autopilot-dev" not in text


@pytest.mark.parametrize("qualifier", ["stage", "rc"])
def test_stage_or_rc_is_a_trigger_not_a_noop(tmp_path, qualifier):
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(generate(tmp_path, PUBLISH_NGC_VERSION_QUALIFIER=qualifier))
    assert set(doc) == {"stages", "trigger-kit-autopilot"}
    trigger = doc["trigger-kit-autopilot"]["trigger"]
    assert trigger["project"] == "omniverse/qa/kit-autopilot"
    assert trigger["branch"] == "main"
    assert trigger["strategy"] == "depend"


# ---------------------------------------------------------------------------
# dev no-op
# ---------------------------------------------------------------------------


def test_dev_generates_green_noop(tmp_path):
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load(generate(tmp_path, PUBLISH_NGC_VERSION="107.0.0-dev.9", PUBLISH_NGC_VERSION_QUALIFIER="dev"))
    assert "trigger-kit-autopilot" not in doc
    assert "skip-kit-autopilot-dev" in doc
    job = doc["skip-kit-autopilot-dev"]
    assert job["stage"] == "qa-automation"
    assert job["extends"] == [".omni_nvks_micro_runner"]
    # The no-op still needs a runner: the child must include the runners template.
    assert doc["include"][0]["project"] == "omniverse/devplat/gitlab/templates/runners"


def test_dev_noop_echoes_resolved_version(tmp_path):
    text = generate(tmp_path, PUBLISH_NGC_VERSION="107.0.0-dev.9", PUBLISH_NGC_VERSION_QUALIFIER="dev")
    assert 'echo "Skipping kit-autopilot for dev publish 107.0.0-dev.9"' in text


# ---------------------------------------------------------------------------
# invalid qualifiers
# ---------------------------------------------------------------------------


def test_missing_qualifier_exits_nonzero(tmp_path):
    with pytest.raises(SystemExit) as exc:
        gkap.generate_pipeline(env=make_env(PUBLISH_NGC_VERSION_QUALIFIER=""), root=tmp_path)
    assert "missing" in str(exc.value)
    assert not (tmp_path / gkap.DEFAULT_CHILD_PIPELINE).exists()


def test_unknown_qualifier_exits_nonzero(tmp_path):
    with pytest.raises(SystemExit) as exc:
        gkap.generate_pipeline(env=make_env(PUBLISH_NGC_VERSION_QUALIFIER="beta"), root=tmp_path)
    assert "beta" in str(exc.value)
    assert not (tmp_path / gkap.DEFAULT_CHILD_PIPELINE).exists()


# ---------------------------------------------------------------------------
# NGC variable forwarding
# ---------------------------------------------------------------------------


def test_ngc_org_and_team_forwarded_to_downloader(tmp_path):
    yaml = pytest.importorskip("yaml")
    variables = yaml.safe_load(generate(tmp_path))["trigger-kit-autopilot"]["variables"]
    # kit-autopilot's downloader consumes NGC_ORG / NGC_TEAM (not the KIT_SDK_PUBLIC_* traceability fields).
    assert variables["NGC_ORG"] == "nvidia"
    assert variables["NGC_TEAM"] == "omniverse"
    assert variables["KIT_SDK_PUBLIC_NGC_ORG"] == "nvidia"
    assert variables["KIT_SDK_PUBLIC_NGC_TEAM"] == "omniverse"


def test_ngc_variables_track_publish_location(tmp_path):
    yaml = pytest.importorskip("yaml")
    variables = yaml.safe_load(generate(tmp_path, PUBLISH_NGC_ORG="other-org", PUBLISH_NGC_TEAM="other-team"))[
        "trigger-kit-autopilot"
    ]["variables"]
    assert variables["NGC_ORG"] == "other-org"
    assert variables["NGC_TEAM"] == "other-team"


# ---------------------------------------------------------------------------
# generated YAML parses correctly and preserves variable values
# ---------------------------------------------------------------------------


def test_generated_yaml_parses_and_preserves_values(tmp_path):
    yaml = pytest.importorskip("yaml")
    variables = yaml.safe_load(generate(tmp_path))["trigger-kit-autopilot"]["variables"]
    assert variables["KIT_VERSION"] == "107.0.0-stage.4"
    assert variables["KIT_KERNEL_VERSION"] == "107.0.0"
    assert variables["KIT_SDK_PUBLIC_NGC_VERSION"] == "107.0.0-stage.4"
    assert variables["KIT_SDK_PUBLIC_VERSION_QUALIFIER"] == "stage"
    assert variables["KIT_SDK_PUBLIC_KIT_KERNEL_VERSION"] == "107.0.0"
    assert variables["KIT_SDK_PUBLIC_SHA"] == "deadbeef"
    assert variables["KIT_SDK_PUBLIC_REF"] == "release/107.0"
    assert variables["KIT_SDK_PUBLIC_PIPELINE_URL"] == "https://gitlab/pipe/42"
    assert variables["KIT_SDK_PUBLIC_TRIGGERED_BY_LOGIN"] == "vshastri"
    assert variables["PRODUCTION_RUN"] == "true"
    # Values containing single quotes must survive the YAML round-trip verbatim.
    assert variables["KIT_SDK_PUBLIC_COMMIT_TITLE"] == "chore: release it's time"


def test_special_characters_preserved_through_yaml(tmp_path):
    yaml = pytest.importorskip("yaml")
    tricky = "title: with 'quotes' & : colons #hash"
    variables = yaml.safe_load(generate(tmp_path, CI_COMMIT_TITLE=tricky))["trigger-kit-autopilot"]["variables"]
    assert variables["KIT_SDK_PUBLIC_COMMIT_TITLE"] == tricky
