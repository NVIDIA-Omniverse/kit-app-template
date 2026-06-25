## Overview

The C++ with Python Bindings Extension Template is a starting point for developers who need the performance benefits of C++ while offering a Python-friendly interface through Pybind11. Designed for the NVIDIA Omniverse ecosystem, this template provides a best-practices structure to seamlessly integrate with the Omniverse Kit SDK and enable easy consumption of extension features from Python.

**Note for Windows C++ Developers**: This template requires that Visual Studio be installed on the host. Additionally, `"platform:windows-x86_64".enabled` and `link_host_toolchain` within the `repo.toml` file must be set to `true`.

### Use Cases

This template is ideal for developers looking to build:

- A reusable C++ extension that can be easily integrated with Omniverse Kit SDK applications.
- Performance-sensitive extensions that leverage C++ while still exposing a Python interface.
- Extensions that require direct access to the Omniverse Kit or Carbonite SDK C++ API, with the added ability for Python scripting.
- Integrations with existing C++ libraries or codebases while offering Python-friendly APIs for broader adoption.

### Key Features

- Structure well suited for the build, test, and packaging tooling within this repository.
- All required setup code for bridging C++ logic with Python using Pybind11.
- Best practices for organizing C++ source and Python binding code into a single extension.
- Smooth integration with the Omniverse Kit SDK for application deployment.