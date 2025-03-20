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

#include <carb/ObjectUtils.h>

#include <omni/String.h>

namespace {{ extension_namespace }}
{

/**
 * Helper base class for bound object implementations.
 */
class {{ object_name }} : public {{ object_interface_name }}
{
    CARB_IOBJECT_IMPL

public:
    /**
     * Constructor.
     *
     * @param id Id of the bound object.
     */
    {{ object_name }}(const char* id)
        : m_id(id ? id : "")
    {
    }

    /**
     * @ref {{ object_interface_name }}::getId
     */
    const char* getId() const override
    {
        return m_id.c_str();
    }

protected:
    const omni::string m_id; //!< Id of the bound object.
};

}
