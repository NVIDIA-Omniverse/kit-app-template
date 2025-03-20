## Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
##
## NVIDIA CORPORATION and its licensors retain all intellectual property
## and proprietary rights in and to this software, related documentation
## and any modifications thereto.  Any use, reproduction, disclosure or
## distribution of this software and related documentation without an express
## license agreement from NVIDIA CORPORATION is strictly prohibited.
##
import omni.ext
from ..{{ library_name }} import *

# Global public interface object.
_bound_interface = None

# Public API.
def get_bound_interface() -> {{ interface_name }}:
    return _bound_interface


# Use the extension entry points to acquire and release the interface.
class ExamplePybindExtension(omni.ext.IExt):
    def __init__(self):
        super().__init__()

        global _bound_interface
        _bound_interface = acquire_bound_interface()

    def on_shutdown(self):
        global _bound_interface
        release_bound_interface(_bound_interface)
        _bound_interface = None
