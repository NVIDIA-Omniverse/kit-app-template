/*
 * SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES.
 * All rights reserved.
 * SPDX-License-Identifier: LicenseRef-NvidiaProprietary
 *
 * NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
 * property and proprietary rights in and to this material, related
 * documentation and any modifications thereto. Any use, reproduction,
 * disclosure or distribution of this material and related documentation
 * without an express license agreement from NVIDIA CORPORATION or
 * its affiliates is strictly prohibited.
 */

#define CARB_EXPORTS

#include <carb/PluginUtils.h>
#include <carb/logging/Log.h>
#include <carb/eventdispatcher/IEventDispatcher.h>
#include <carb/events/IEvents.h>
#include <carb/events/EventsUtils.h>

#include <omni/ext/IExt.h>
#include <omni/kit/IApp.h>

#include <memory>


#define EXTENSION_NAME "{{ extension_name }}.plugin"

using namespace carb;

// Plugin Implementation Descriptor
const struct carb::PluginImplDesc kPluginImpl = {
    EXTENSION_NAME,  // Name of the plugin (e.g. "carb.dictionary.plugin"). Must be globally unique.
    "Example of a native plugin extension.",  // Helpful text describing the plugin.  Used for debugging/tools.
    "NVIDIA",  // Author
    carb::PluginHotReload::eDisabled,
    "dev"  // Build version of the plugin.
};

// List dependencies for this plugin
CARB_PLUGIN_IMPL_DEPS(omni::kit::IApp, carb::logging::ILogging)


class NativeExtensionExample : public omni::ext::IExt
{
public:
    void onStartup(const char* extId) override
    {
        printf(EXTENSION_NAME ": in onStartup\n");
        // Get event dispatch interface using Carbonite Framework
        auto ed = carb::getCachedInterface<carb::eventdispatcher::IEventDispatcher>();
        m_subscription = ed->observeEvent(
            carb::RStringKey("cpp.example.update"),
            0,
            omni::kit::kGlobalEventUpdate,
            [this](const carb::eventdispatcher::Event& e) {
                if (m_counter % 100 == 0)
                {
                    printf(EXTENSION_NAME ": %d updates passed.\n", m_counter);
                    CARB_LOG_INFO(EXTENSION_NAME ": %d updates passed.\n", m_counter);
                }
                m_counter++;
            });
    }

    void onShutdown() override
    {
        // Unsubscribes from the event stream
        m_subscription.reset();
    }

private:
    int m_counter = 0;
    carb::eventdispatcher::ObserverGuard m_subscription;
};


// Generate boilerplate code
CARB_PLUGIN_IMPL(kPluginImpl, NativeExtensionExample)

// There must be a fillInterface(InterfaceType&) function for each interface type that is exported by this plugin.
void fillInterface(NativeExtensionExample& iface)
{
}
