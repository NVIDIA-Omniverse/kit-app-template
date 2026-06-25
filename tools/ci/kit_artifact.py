"""
Helper to use kit from GitLab CI artifact instead of packman when triggered from kit pipeline.

Environment variables:
    KIT_GITLAB_PIPELINE_ID: Pipeline ID from kit CI
    KIT_GITLAB_PAT_TOKEN: GitLab Personal Access Token for kit repository (required)
                      Should be set in kit-app-template CI/CD variables
"""

import json
import os
import shutil
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import omni.repo.ci
import omni.repo.man
from omni.repo.man.utils import find_and_extract_package

_ROOT = Path(__file__).resolve().parents[2]


def get_job_id_from_pipeline(pipeline_id, project_id, token, platform, config):
    """Get the specific job ID from a pipeline based on platform and config."""
    # Job name pattern: kit-build-{config}-{platform}
    job_name = f"kit-build-{config}-{platform}"

    print(f"Looking for job '{job_name}' in pipeline {pipeline_id}...")

    # Fetch all jobs with pagination
    page = 1
    per_page = 100
    all_jobs = []

    while True:
        url = f"https://gitlab-master.nvidia.com/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs?per_page={per_page}&page={page}"

        req = Request(url, headers={"PRIVATE-TOKEN": token})
        try:
            with urlopen(req) as response:
                jobs = json.loads(response.read().decode())

                if not jobs:
                    break

                all_jobs.extend(jobs)

                # If we got fewer than per_page, we're done
                if len(jobs) < per_page:
                    break

                page += 1

        except Exception as e:
            raise RuntimeError(f"Failed to get jobs from pipeline {pipeline_id}: {e}")

    print(f"Total jobs in pipeline: {len(all_jobs)}")

    # Find the matching job
    for job in all_jobs:
        if job.get("name") == job_name and job.get("status") == "success":
            job_id = job["id"]
            print(f"Found job: {job_name} (ID: {job_id})")
            return job_id

    # Job not found - print available jobs and raise
    print(f"Available jobs:")
    for job in all_jobs:
        print(f"  - {job.get('name')} (status: {job.get('status')})")
    raise RuntimeError(f"Job '{job_name}' not found or not successful in pipeline {pipeline_id}")


def setup_kit_from_artifact():
    """
    Download and setup kit from GitLab artifact if KIT_GITLAB_PIPELINE_ID is set.
    Returns False if KIT_GITLAB_PIPELINE_ID is not set (use packman).
    Raises exception on any failure if KIT_GITLAB_PIPELINE_ID is set.
    """
    pipeline_id = os.getenv("KIT_GITLAB_PIPELINE_ID")
    if not pipeline_id:
        return False  # Use packman

    print(f"\n{'='*80}")
    print(f"Using Kit from GitLab Pipeline {pipeline_id}")
    print(f"{'='*80}\n")

    token = os.getenv("KIT_GITLAB_PAT_TOKEN")
    if not token:
        raise RuntimeError(
            "KIT_GITLAB_PAT_TOKEN required when using KIT_GITLAB_PIPELINE_ID. "
            "Set this as a CI/CD variable in kit-app-template project settings with a PAT from kit repository."
        )

    project_id = os.getenv("KIT_GITLAB_PROJECT_ID", "omniverse%2Fkit")
    is_windows = omni.repo.ci.is_windows()
    platform = omni.repo.man.get_host_platform()
    config = os.getenv("KIT_BUILD_CONFIG", "release")

    # Get the specific job ID from the pipeline (raises on failure)
    job_id = get_job_id_from_pipeline(pipeline_id, project_id, token, platform, config)

    # Download artifact
    kit_artifacts_dir = _ROOT / "_build" / "kit_artifacts"
    kit_artifacts_dir.mkdir(parents=True, exist_ok=True)
    zip_file = kit_artifacts_dir / f"kit-artifact-{job_id}.zip"
    extract_dir = kit_artifacts_dir / f"kit-artifact-{job_id}"

    # Check if artifact already downloaded
    if zip_file.exists():
        print(f"Kit artifact already downloaded: {zip_file}")
        print(f"Size: {zip_file.stat().st_size / 1024 / 1024:.1f} MB")
    else:
        # Download artifact
        url = f"https://gitlab-master.nvidia.com/api/v4/projects/{project_id}/jobs/{job_id}/artifacts"
        print(f"Downloading from: {url}")

        try:
            req = Request(url, headers={"PRIVATE-TOKEN": token})
            with urlopen(req) as response, open(zip_file, "wb") as f:
                f.write(response.read())
            print(f"Downloaded {zip_file.stat().st_size / 1024 / 1024:.1f} MB")
        except Exception as e:
            raise RuntimeError(f"Failed to download artifact from job {job_id}: {e}")

    # Extract artifacts.zip if not already extracted
    if not extract_dir.exists():
        print(f"Extracting artifacts.zip to {extract_dir}...")
        extract_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_file) as z:
                z.extractall(extract_dir)
        except Exception as e:
            raise RuntimeError(f"Failed to extract artifacts.zip: {e}")
    else:
        print(f"Artifacts already extracted: {extract_dir}")

    # Find and extract the omniverse-kit 7z file
    # Look in kit/_builtpackages directory for omniverse-kit package
    kit_pattern = f"{extract_dir}/kit/_builtpackages/omniverse-kit*.7z".replace("\\", "/")
    print(f"Looking for omniverse-kit package: {kit_pattern}")

    try:
        kit_extracted_dir, kit_archive = find_and_extract_package(kit_pattern, clean=False)
        print(f"Extracted kit from: {Path(kit_archive).name}")
        print(f"Kit extracted to: {kit_extracted_dir}")
    except Exception as e:
        raise RuntimeError(f"Failed to find/extract omniverse-kit package: {e}")

    # Kit is at known location inside the extracted 7z: _build/{platform}/{config}
    kit_extracted_path = Path(kit_extracted_dir)
    kit_source = kit_extracted_path / "_build" / platform / config

    if not kit_source.exists():
        raise RuntimeError(f"Kit not found at expected location: {kit_source}")

    if not (kit_source / "kit").exists() and not (kit_source / "kit.exe").exists():
        raise RuntimeError(f"Kit executable not found in: {kit_source}")

    print(f"Found kit at: {kit_source}")

    # Create packman .user file to override kit-sdk dependency
    packman_user_xml = _ROOT / "tools" / "deps" / "kit-sdk.packman.xml.user"

    # Write .user file pointing to extracted kit
    kit_path = kit_source
    user_content = f"""
<project toolsVersion="5.6">
  <dependency name="kit_sdk_${{config}}" linkPath="../../_build/${{platform_target}}/${{config}}/kit" tags="${{config}} non-redist">
    <source path="{kit_path.as_posix()}" />
  </dependency>
</project>
"""
    packman_user_xml.write_text(user_content)
    print(f"Created packman user override: {packman_user_xml}")

    return True
