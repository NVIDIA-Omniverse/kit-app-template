// Copyright (c) 2022, NVIDIA CORPORATION. All rights reserved.
//
// NVIDIA CORPORATION and its licensors retain all intellectual property
// and proprietary rights in and to this software, related documentation
// and any modifications thereto.  Any use, reproduction, disclosure or
// distribution of this software and related documentation without an express
// license agreement from NVIDIA CORPORATION is strictly prohibited.
//
#pragma once

#include <{{ python_module_path }}/{{ object_interface_name }}.h>

#include <carb/Interface.h>

namespace {{ extension_namespace }}
{

/**
 * An example interface to demonstrate reflection using pybind.
 */
class {{ interface_name }}
{
public:
    /// @private
    CARB_PLUGIN_INTERFACE("{{ extension_namespace }}::{{ interface_name }}", 1, 0);

    /**
     * Register a bound object.
     *
     * @param object The bound object to register.
     */
    virtual void register{{object_name}}(carb::ObjectPtr<{{ object_interface_name }}>& object) = 0;

    /**
     * Deregister a bound object.
     *
     * @param object The bound object to deregister.
     */
    virtual void deregister{{object_name}}(carb::ObjectPtr<{{ object_interface_name }}>& object) = 0;

    /**
     * Find a bound object.
     *
     * @param id Id of the bound object.
     *
     * @return The bound object if it exists, an empty ObjectPtr otherwise.
     */
    virtual carb::ObjectPtr<{{ object_interface_name }}> find{{object_name}}(const char* id) const = 0;
};

}
