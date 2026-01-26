# Configuring Kit App Template for DGXC Deployment

This document covers Kit App Template specific configuration for deploying to NVIDIA DGX Cloud. For complete deployment instructions, see the [public DGXC documentation](https://docs.omniverse.nvidia.com/omniverse-dgxc/latest/).

## Streaming Layer Selection

When creating your application with `./repo.sh template new`, select the appropriate streaming layer for DGXC:

| Kit Version | Layer to Select | Generated File |
|-------------|-----------------|----------------|
| 108.x+ | `nvcf_streaming` | `{app_name}_nvcf.kit` |
| 107.x | `ovc_streaming` | `{app_name}_ovc.kit` |
| 106.x | `ovc_streaming` | `{app_name}_ovc.kit` |

### Selection Process

1. Run `./repo.sh template new`
2. Select **Application** and your desired template
3. When prompted "Do you want to add application layers?", select **Yes**
4. Select the streaming layer for your Kit version

## What the NVCF Streaming Layer Adds

The streaming layer creates a separate `.kit` file that inherits from your base application and adds:

```toml
[dependencies]
"your_company.your_app" = {}               # Your base application
"omni.services.livestream.session" = {}    # NVCF streaming (brings in `omni.kit.livestream.webrtc` and other streaming dependencies)
"omni.ujitso.client" = {}                  # Geometry caching for faster load times
"omni.cloud.open_stage" = {}               # Nucleus server connection support
```

**Extension Details:**

- **`omni.ujitso.client`**: Enables [geometry streaming/caching](https://docs.omniverse.nvidia.com/materials-and-rendering/latest/rtx-renderer_common.html#rtx-common-gpu-resources-management) to improve scene load times for large USD scenes.

- **`omni.cloud.open_stage`**: Provides Nucleus server connectivity for cloud deployments. For connecting your Enterprise Nucleus to DGXC, see [Nucleus Connectivity](https://docs.omniverse.nvidia.com/omniverse-dgxc/latest/integration-with-dgxc/nucleus-connectivity.html).

The [`omni.services.livestream.session`](https://docs.omniverse.nvidia.com/kit/docs/omni.services.livestream.session/latest/Overview.html) extension:
- Implements NVCF health check endpoints (`/v1/streaming/ready`)
- Manages session lifecycle with NVCF
- Supports session resume on reconnection
- Automatically includes `omni.kit.livestream.webrtc` and other streaming dependencies

## What the NVCF Streaming Layer Modifies
In addition to adding extension dependencies the streaming layer changes settings for existing extensions:

```toml
[settings.exts."omni.kit.window.filepicker"]
show_only_collections.6 = ""                        # Hides the "My Computer" connection from the file picker.

[settings.exts."omni.kit.window.content_browser"]
show_only_collections.6 = ""                        # Hides the "My Computer" connection from the content browser.
```

## Containerization

After building (`./repo.sh build`), create a container:

```bash
./repo.sh package_container --image-tag myapp:v1.0
```

When prompted, select the streaming `.kit` file (`*_ovc.kit` or `*_nvcf.kit`).

## Next Steps

For deployment to DGXC (container upload, NVCF function creation, portal registration), see:

- [Containerization Guide](https://docs.omniverse.nvidia.com/omniverse-dgxc/latest/develop-ov-dgxc/containerization.html) - Building and packaging
- [Deploying Kit Apps](https://docs.omniverse.nvidia.com/omniverse-dgxc/latest/develop-ov-dgxc/deploying.html) - NGC upload and NVCF deployment
- [Troubleshooting](https://docs.omniverse.nvidia.com/omniverse-dgxc/latest/faqs.html) - Common issues and FAQs

## Version-Specific Notes

### Kit 108.x+ (`main` branch)

Select `nvcf_streaming` during template creation. Streaming dependencies are automatically configured.

### Kit 107.x (`production/107.3` branch)

Select `ovc_streaming` during template creation. No manual edits required.

### Kit 106.x (`production/106.5` branch)

The streaming layer may require manual edits. See the [public containerization guide](https://docs.omniverse.nvidia.com/omniverse-dgxc/latest/develop-ov-dgxc/containerization.html#replace-streaming-extension) for the "Replace Streaming Extension" section.

## Troubleshooting

For deployment issues, log analysis, and common errors, see the [DGXC FAQs and Troubleshooting](https://docs.omniverse.nvidia.com/omniverse-dgxc/latest/faqs.html).
