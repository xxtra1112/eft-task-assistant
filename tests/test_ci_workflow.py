from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def workflow():
    return yaml.load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_candidate_upload_uses_action_path_input():
    steps = workflow()["jobs"]["build"]["steps"]
    uploads = [step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1
    inputs = uploads[0]["with"]
    assert inputs["path"].strip()
    assert "files" not in inputs
    assert inputs["if-no-files-found"] == "error"


def test_manual_build_does_not_publish_release():
    definition = workflow()
    assert "workflow_dispatch" in definition["on"]
    assert "workflow_dispatch" in definition["jobs"]["build"]["if"]
    release = definition["jobs"]["release"]
    assert "github.event_name == 'push'" in release["if"]
    assert "refs/tags/v" in release["if"]
    assert release["needs"] == ["verify", "build"]


def test_smoke_uses_extracted_executable_and_isolated_default_root():
    steps = workflow()["jobs"]["build"]["steps"]
    smoke = next(step["run"] for step in steps if step.get("name", "").startswith("Verify checksums and smoke"))
    assert "Expand-Archive" in smoke
    assert 'Join-Path $extractRoot "$stem.exe"' in smoke
    assert 'EFT_TASK_ASSISTANT_CHANNEL = "qa-$qaId"' in smoke
    assert "--no-preload" in smoke
    assert "--data-dir" not in smoke
    assert "/api/save-data" in smoke


def test_release_checks_existing_release_and_downloaded_hashes():
    steps = workflow()["jobs"]["release"]["steps"]
    publish = next(step["run"] for step in steps if "run" in step)
    assert "$existing.StatusCode -eq 200" in publish
    assert "refusing to overwrite" in publish
    assert "Get-FileHash" in publish
    assert "gh release create" in publish
    assert "gh release upload" not in publish
    assert "--verify-tag" in publish


def test_windows_python_uses_available_pinned_conda_build():
    definition = workflow()
    assert definition["defaults"]["run"]["shell"] == "pwsh"
    for job_name in ("verify", "build"):
        steps = definition["jobs"][job_name]["steps"]
        setup = next(step for step in steps if step.get("uses", "").startswith("conda-incubator/setup-miniconda@"))
        assert setup["with"]["miniforge-version"] == "26.7.2-0"
        assert setup["with"]["environment-file"] == ".github/conda-release.yml"
        assert not any(step.get("uses", "").startswith("actions/setup-python@") for step in steps)
    environment = yaml.load((ROOT / ".github/conda-release.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert "python=3.11.17=hb12b558_2_cpython" in environment["dependencies"]


def test_verify_includes_dataset_and_history_ui_regressions():
    runs = "\n".join(step.get("run", "") for step in workflow()["jobs"]["verify"]["steps"])
    assert "node --test tests/test_ui_state.cjs" in runs
    assert "node --test tests/test_preference_sync.cjs" in runs
