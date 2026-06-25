// Copyright (c) 2022, NVIDIA CORPORATION. All rights reserved.
//
// NVIDIA CORPORATION and its licensors retain all intellectual property
// and proprietary rights in and to this software, related documentation
// and any modifications thereto.  Any use, reproduction, disclosure or
// distribution of this software and related documentation without an express
// license agreement from NVIDIA CORPORATION is strictly prohibited.
//

#define CARB_EXPORTS

#include <carb/PluginUtils.h>

#include <omni/ext/IExt.h>

#include <{{ python_module_path }}/{{ interface_name }}.h>

#include <unordered_map>

const struct carb::PluginImplDesc pluginImplDesc = { "{{ extension_name }}.plugin",
                                                     "An example C++ extension.", "NVIDIA",
                                                     carb::PluginHotReload::eEnabled, "dev" };

namespace {{ extension_namespace }}
{

class ExampleBoundImplementation : public {{ interface_name }}
{
public:
    void register{{object_name}}(carb::ObjectPtr<{{ object_interface_name }}>& object) override
    {
        if (object)
        {
            m_registeredObjectsById[object->getId()] = object;
        }
    }

    void deregister{{object_name}}(carb::ObjectPtr<{{ object_interface_name }}>& object) override
    {
        if (object)
        {
            const auto& it = m_registeredObjectsById.find(object->getId());
            if (it != m_registeredObjectsById.end())
            {
                m_registeredObjectsById.erase(it);
            }
        }
    }

    carb::ObjectPtr<{{ object_interface_name }}> find{{object_name}}(const char* id) const override
    {
        const auto& it = m_registeredObjectsById.find(id);
        if (it != m_registeredObjectsById.end())
        {
            return it->second;
        }

        return carb::ObjectPtr<{{ object_interface_name }}>();
    }

private:
    std::unordered_map<std::string, carb::ObjectPtr<{{ object_interface_name }}>> m_registeredObjectsById;
};

}

CARB_PLUGIN_IMPL(pluginImplDesc, {{ extension_namespace }}::ExampleBoundImplementation)

void fillInterface({{ extension_namespace }}::ExampleBoundImplementation& iface)
{
}
