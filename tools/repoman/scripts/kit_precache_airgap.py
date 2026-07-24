import asyncio
import json
import logging
import os

import omni.client
import omni.ext
import omni.kit.app
from omni.kit.registry.nucleus import get_registry_url_by_ext_dict

logger = logging.getLogger(__name__)


def get_extension_metadata_possible_urls(ext_dict):
    # TODO(anov): temp copy it here, until I fix in Kit SDK
    registry_url = get_registry_url_by_ext_dict(ext_dict)
    if not registry_url:
        return []

    package_dict = archive_path = ext_dict.get("package", {})
    # Same as archive path, but extension is `.json`:
    archive_path = package_dict.get("archivePath", None)
    if archive_path:
        # build url relative to the registry url
        archive_path = archive_path.replace("\\", "/")
        archive_path = omni.client.combine_urls(registry_url + "/index.zip", archive_path)
        archive_path = omni.client.normalize_url(archive_path)
        archive_path = os.path.splitext(archive_path)[0] + ".json"

        paths = []
        # if archive is on the same host as registry (usually on nucleus), try archive path first. Metadata would be
        # next to it
        if omni.client.break_url(archive_path).host == omni.client.break_url(registry_url).host:
            paths.append(archive_path)

        # If archive path is on different host (like packman). Do the best guess using registry url.
        # Old format is one big folder, new format is a subfolder for each extension
        data_filename = os.path.basename(archive_path)
        ext_name = package_dict.get("name", "")
        package_id = package_dict.get("packageId", "")
        for path in (
            f"{registry_url}/archives/{ext_name}/{package_id}.json",
            f"{registry_url}/archives/{package_id}.json",
            "{}/archives/{}/{}".format(registry_url, ext_name, data_filename),
            "{}/archives/{}".format(registry_url, data_filename),
        ):
            if path not in paths:
                paths.append(path)
        return paths

    return []


async def fetch_metadata(ext_remote):
    json_data_urls = get_extension_metadata_possible_urls(ext_remote)
    if json_data_urls:
        for json_data_url in json_data_urls:
            result, _, content = await omni.client.read_file_async(json_data_url)
            if result == omni.client.Result.OK:
                try:
                    content = memoryview(content).tobytes().decode("utf-8")
                    return json.loads(content)
                except Exception as e:  # noqa
                    pass

    return None


async def precache_extensions():
    manager = omni.kit.app.get_app().get_extension_manager()

    success = True

    pulled_extensions = set()
    for summary in manager.fetch_extension_summaries():
        ext_id = summary["latest_version"]["id"]
        ext_local = manager.get_extension_dict(ext_id)

        # If we already have it included into kit-sdk-public, skip:
        if ext_local:
            continue

        ext_remote = manager.get_registry_extension_dict(ext_id)
        if not ext_remote:
            # there is no compatible package for this extension on this platform
            print(f"Skipping {ext_id} as it is not compatible with this platform")
            continue

        # skip non-kit-sdk extensions
        if ext_remote["registryProviderName"] != "kit/sdk":
            continue

        # We need metadata (from a separate json file ) to read "support_level" field
        metadata = await fetch_metadata(ext_remote)
        if not metadata:
            success = False
            logger.error(f"Failed to fetch metadata for {ext_id}")
            continue

        # Skip internal extensions
        support_level = metadata.get("package", {}).get("support_level", "").lower()
        if support_level == "internal":
            continue

        # Start async installation and add to the set of extensions to wait for
        print(f"Installing {ext_id} with support level: {support_level}")
        manager.pull_extension_async(ext_id)
        pulled_extensions.add(ext_id)

    # Wait for all extensions to be installed by checking if they are locally available
    while len(pulled_extensions) > 0:
        await asyncio.sleep(1)

        for ext_id in set(pulled_extensions):
            ext_local = manager.get_extension_dict(ext_id)
            if ext_local:
                pulled_extensions.remove(ext_id)

    omni.kit.app.get_app().post_quit(0 if success else 1)


asyncio.ensure_future(precache_extensions())
