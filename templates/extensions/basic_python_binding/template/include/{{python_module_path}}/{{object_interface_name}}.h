// Copyright (c) 2022, NVIDIA CORPORATION. All rights reserved.
//
// NVIDIA CORPORATION and its licensors retain all intellectual property
// and proprietary rights in and to this software, related documentation
// and any modifications thereto.  Any use, reproduction, disclosure or
// distribution of this software and related documentation without an express
// license agreement from NVIDIA CORPORATION is strictly prohibited.
//
#pragma once

#include <carb/IObject.h>

namespace {{ extension_namespace }}
{

/**
 * Pure virtual bound object interface.
 */
class {{ object_interface_name }} : public carb::IObject
{
public:
    /**
     * Get the id of this object.
     *
     * @return Id of this object.
     */
    virtual const char* getId() const = 0;
};

/**
 * Implement the equality operator so these can be used in std containers.
 */
inline bool operator==(const carb::ObjectPtr<{{ object_interface_name }}>& left,
                       const carb::ObjectPtr<{{ object_interface_name }}>& right) noexcept
{
    return (left.get() == right.get());
}

}
