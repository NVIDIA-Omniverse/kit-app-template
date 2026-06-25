# CI/CD Pipeline Jobs for Container Management

This document provides an overview of the container-related jobs in our CI/CD pipeline, specifically focusing on the `build-container`, `publish-container`, `build-container-ovc2`, and `publish-container-ovc2` jobs. These jobs are designed to build and publish Docker containers for our applications.

## Job Descriptions

### 1. `build-container`
- **What it does**: Makes Docker containers for `usd_explorer` and `usd_composer`.
- **When it runs**: Automatically starts with certain triggers.
- **What it saves**: Keeps the container files and logs as artifacts.
- **How it works**: Runs `container_builder.py` to build the containers.

### 2. `publish-container`
- **What it does**: Sends the built containers to a registry.
- **When it runs**: Starts after `build-container` finishes.
- **What it saves**: Keeps logs of the publishing process.
- **How it works**: Installs tools and runs `container_publisher.py` to publish the containers.

### 3. `build-container-ovc2`
- Same as `build-container`, but for OVC2 builds.

### 4. `publish-container-ovc2`
- Same as `publish-container`, but for OVC2 builds.

## Logic for Updating Latest Tags

In the `container_publisher.py` file, there is a specific logic that controls when the latest tags for Docker images are updated. The condition is as follows:

```python
if MR_TRIGGER_BUILD == "false" and TRIGGER_BRANCH in ["master", "main"] and BUILD_FOR_OVC2 != "true":
    _push_latest_tags(images)
```

- **MR_TRIGGER_BUILD**: This variable should be `"false"` to proceed with updating the latest tags. This typically means that the build was not triggered by a merge request.
- **TRIGGER_BRANCH**: The branch must be either `master` or `main`. This ensures that only builds from these main branches can update the latest tags.
- **BUILD_FOR_OVC2**: The condition `BUILD_FOR_OVC2 != "true"` ensures that the latest tags are not updated for OVC2-specific builds.

This logic ensures that the latest tags are only updated under controlled conditions, preventing unintended updates from feature branches or OVC2-specific builds.

## How to Trigger Jobs

These jobs are configured to be triggered only by specific pipeline triggers. They cannot be manually started from the GitLab UI. To set up a trigger, you can configure a pipeline trigger in your GitLab project settings.

### Example
#### Setting Up a Pipeline Trigger

1. Navigate to your project's **Settings > CI/CD** in GitLab.
2. Expand the **Pipeline triggers** section.
3. Click on **Add trigger** to create a new trigger.
4. Use the generated token to trigger the pipeline via an API call or another automated process.

#### Setting Up a Pipeline Schedule

1. Navigate to your project's **CI / CD > Schedules** in GitLab.
2. Click on **New schedule** to create a new pipeline schedule.
3. Fill in the **Description** field with a name for your schedule.
4. Set the **Interval Pattern** using cron syntax to define when the pipeline should run.
5. Select the **Target Branch** that the schedule should run against.
6. Optionally, set any **Variables** that should be used during the scheduled pipeline run.
7. Click on **Save pipeline schedule** to save your new schedule.

By following these instructions, you can effectively manage the building and publishing of Docker containers for your applications through automated triggers. 