// Copyright (c) 2020-2021, NVIDIA CORPORATION. All rights reserved.
//
// NVIDIA CORPORATION and its licensors retain all intellectual property
// and proprietary rights in and to this software, related documentation
// and any modifications thereto.  Any use, reproduction, disclosure or
// distribution of this software and related documentation without an express
// license agreement from NVIDIA CORPORATION is strictly prohibited.
//

#include <{{ python_module_path }}/{{ interface_name }}.h>
#include <{{ python_module_path }}/{{ object_name }}.h>

#include <doctest/doctest.h>

#include <carb/BindingsUtils.h>

CARB_BINDINGS("{{ extension_name }}.tests")

namespace {{ extension_namespace }}
{

class ExampleCppObject : public {{ object_name }}
{
public:
    static carb::ObjectPtr<{{ object_interface_name }}> create(const char* id)
    {
        return carb::stealObject<{{ object_interface_name }}>(new ExampleCppObject(id));
    }

    ExampleCppObject(const char* id)
        : {{ object_name }}(id)
    {
    }
};

class ExamplePybindTestFixture
{
public:
    static constexpr const char* k_registeredObjectId = "example_bound_object";

    ExamplePybindTestFixture()
        : m_exampleBoundInterface(carb::getCachedInterface<{{ extension_namespace }}::{{ interface_name }}>())
        , m_{{ object_name }}(ExampleCppObject::create(k_registeredObjectId))
    {
        m_exampleBoundInterface->register{{object_name}}(m_{{ object_name }});
    }

    ~ExamplePybindTestFixture()
    {
        m_exampleBoundInterface->deregister{{object_name}}(m_{{ object_name }});
    }

protected:
    {{ interface_name }}* getExampleBoundInterface()
    {
        return m_exampleBoundInterface;
    }

    carb::ObjectPtr<{{ object_interface_name }}> get{{ object_name }}()
    {
        return m_{{ object_name }};
    }

private:
    {{ interface_name }}* m_exampleBoundInterface = nullptr;
    carb::ObjectPtr<{{ object_interface_name }}> m_{{ object_name }};
};

}

TEST_SUITE("{{ extension_name }}.tests")
{
    using namespace {{ extension_namespace }}
;

    TEST_CASE_FIXTURE(ExamplePybindTestFixture, "Get Example Bound Interface")
    {
        CHECK(getExampleBoundInterface() != nullptr);
    }

    TEST_CASE_FIXTURE(ExamplePybindTestFixture, "Get Example Bound Object")
    {
        CHECK(get{{ object_name }}().get() != nullptr);
    }

    TEST_CASE_FIXTURE(ExamplePybindTestFixture, "Find Example Bound Object")
    {
        SUBCASE("Registered")
        {
            carb::ObjectPtr<{{ object_interface_name }}> foundObject = getExampleBoundInterface()->find{{object_name}}(k_registeredObjectId);
            CHECK(foundObject.get() == get{{ object_name }}().get());
            CHECK(foundObject.get() != nullptr);
        }

        SUBCASE("Unregistered")
        {
            carb::ObjectPtr<{{ object_interface_name }}> foundObject = getExampleBoundInterface()->find{{object_name}}("unregistered_object_id");
            CHECK(foundObject.get() != get{{ object_name }}().get());
            CHECK(foundObject.get() == nullptr);
        }
    }
}
