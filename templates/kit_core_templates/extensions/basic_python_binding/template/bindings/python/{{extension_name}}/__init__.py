## Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
##
## NVIDIA CORPORATION and its licensors retain all intellectual property
## and proprietary rights in and to this software, related documentation
## and any modifications thereto.  Any use, reproduction, disclosure or
## distribution of this software and related documentation without an express
## license agreement from NVIDIA CORPORATION is strictly prohibited.
##

# Necessary so we can link to the Python source instead of copying it.
__all__ = ['"{{object_name}}"', '{{ interface_name }}', '{{ object_interface_name }}', 'acquire_bound_interface', 'release_bound_interface']
from .impl import *
