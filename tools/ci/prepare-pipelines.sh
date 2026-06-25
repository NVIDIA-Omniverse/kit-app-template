#!/bin/bash
set -e

echo "Preparing container publishing pipeline based on checkbox selection..."

# Source the checkbox environment variables
if [[ -f "CHECKBOXES.env" ]]; then
    echo "Loading checkbox configuration..."
    source CHECKBOXES.env
else
    echo "No CHECKBOXES.env found, using defaults"
fi

# Determine if container publishing should run
publish_containers=false

# Check if NGC publishing is enabled
if [[ "${CB_PUBLISH_NGC:-0}" == "1" ]]; then
    publish_containers=true
    echo "NGC container publishing is ENABLED via checkbox"
else
    echo "NGC container publishing is DISABLED (checkbox not checked)"
fi

# Generate MR tag for containers
mr_tag=""
if [[ -n "$CI_MERGE_REQUEST_IID" ]]; then
    mr_tag="mr${CI_MERGE_REQUEST_IID}"
    echo "Using MR tag: $mr_tag"
else
    echo "Warning: Not an MR pipeline, no MR tag will be generated"
fi

# Create directory for generated pipeline configs
mkdir -p generated-pipelines

# Generate container publishing pipeline config
if [[ "$publish_containers" == "true" ]]; then
    cat > generated-pipelines/container-publish.yml << EOF
# Container publishing pipeline for NGC
build-containers:
  stage: build
  extends:
    - .omni_nvks_runner_with_docker
    - .osec:vault:v3:prod_token_job
  parallel:
    matrix:
      - APP:
        - usd_explorer
        - usd_composer
  before_script:
    - touch .omniverse_eula_accepted.txt # for eula acceptance
  script:
    - ./repo.sh ci container_builder
  artifacts:
    when: always
    expire_in: 2 weeks
    paths:
      - _containers/*.tar
      - _repo/repo.log
  rules:
    - if: \$CI_PIPELINE_SOURCE == "merge_request_event"

publish-containers-to-ngc:
  stage: deploy
  extends:
    - .omni_nvks_runner_with_docker
    - .osec:vault:v3:prod_token_job
  needs: ["build-containers"]
  parallel:
    matrix:
      - APP:
        - usd_explorer
        - usd_composer
  variables:
    NGC_REGISTRY_NAME: "nvcr.io/0596158927327413"
    CONTAINER_TAG: "${mr_tag}"
  script:
    - ./tools/packman/python.sh -m pip install ngcsdk
    - ./repo.sh ci container_publisher
  artifacts:
    when: always
    expire_in: 2 weeks
    paths:
      - _repo/repo.log
  rules:
    - if: \$CI_PIPELINE_SOURCE == "merge_request_event"
EOF
    echo "Generated container publishing pipeline configuration"
else
    cat > generated-pipelines/container-publish.yml << EOF
# Container publishing is disabled
skip-container-publish:
  stage: build
  script:
    - echo "Container publishing to NGC is disabled (checkbox not checked)"
  rules:
    - when: always
EOF
    echo "Generated skip configuration for container publishing"
fi

# Create summary
echo "Container Publishing Summary:"
echo "- Publish to NGC: $publish_containers"
echo "- MR Tag: ${mr_tag:-'N/A'}"

# Export for use in other jobs
{
    echo "PUBLISH_CONTAINERS=$publish_containers"
    echo "MR_TAG=$mr_tag"
    echo "NGC_REGISTRY_NAME=nvcr.io/0596158927327413"
} >> PIPELINE_CONFIG.env 