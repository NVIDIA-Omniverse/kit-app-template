// Copyright (c) 2022, NVIDIA CORPORATION. All rights reserved.
//
// NVIDIA CORPORATION and its licensors retain all intellectual property
// and proprietary rights in and to this software, related documentation
// and any modifications thereto.  Any use, reproduction, disclosure or
// distribution of this software and related documentation without an express
// license agreement from NVIDIA CORPORATION is strictly prohibited.
//

#include <carb/BindingsPythonUtils.h>

#include <{{ python_module_path }}/{{ object_name }}.h>
#include <{{ python_module_path }}/{{ interface_name }}.h>

#include <string>

CARB_BINDINGS("{{ extension_name }}.python")

DISABLE_PYBIND11_DYNAMIC_CAST({{ extension_namespace }}::{{ interface_name }})
DISABLE_PYBIND11_DYNAMIC_CAST({{ extension_namespace }}::{{ object_interface_name }})

namespace
{

/**
 * Concrete bound object class that will be reflected to Python.
 */
class Python{{object_name}} : public {{ extension_namespace }}::{{ object_name }}
{
public:
    /**
     * Factory.
     *
     * @param id Id of the bound action.
     *
     * @return The bound object that was created.
     */
    static carb::ObjectPtr<Python{{object_name}}> create(const char* id)
    {
        // Note: It is important to construct the handler using ObjectPtr<T>::InitPolicy::eSteal,
        // otherwise we end up incresing the reference count by one too many during construction,
        // resulting in carb::ObjectPtr<T> instance whose wrapped object will never be destroyed.
        return carb::stealObject<Python{{object_name}}>(new Python{{object_name}}(id));
    }

    /**
     * Constructor.
     *
     * @param id Id of the bound object.
     */
    Python{{object_name}}(const char* id)
        : {{ object_name }}(id)
        , m_memberInt(0)
        , m_memberBool(false)
        , m_memberString()
    {
    }

    // To deomnstrate binding a fuction that accepts an argument.
    void multiplyIntProperty(int value)
    {
        m_memberInt *= value;
    }

    // To deomnstrate binding a fuction that returns a value.
    bool toggleBoolProperty()
    {
        m_memberBool = !m_memberBool;
        return m_memberBool;
    }

    // To deomnstrate binding a fuction that accepts an argument and returns a value.
    const char* appendStringProperty(const char* value)
    {
        m_memberString += value;
        return m_memberString.c_str();
    }

    // To deomnstrate binding properties using accessors.
    const char* getMemberString() const
    {
        return m_memberString.c_str();
    }

    // To deomnstrate binding properties using accessors.
    void setMemberString(const char* value)
    {
        m_memberString = value;
    }

    // To deomnstrate binding properties directly.
    int m_memberInt;
    bool m_memberBool;

private:
    // To deomnstrate binding properties using accessors.
    std::string m_memberString;
};

// Define the pybind11 module using the same name specified in premake5.lua
PYBIND11_MODULE({{ library_name }}, m)
{
    using namespace {{ extension_namespace }}
;

    m.doc() = "pybind11 {{ extension_name }} bindings";

    carb::defineInterfaceClass<{{ interface_name }}>(
        m, "{{ interface_name }}", "acquire_bound_interface", "release_bound_interface")
        .def("register_bound_object", &{{ interface_name }}::register{{object_name}},
             R"(
             Register a bound object.

             Args:
                 object: The bound object to register.
             )",
             py::arg("object"))
        .def("deregister_bound_object", &{{ interface_name }}::deregister{{object_name}},
             R"(
             Deregister a bound object.

             Args:
                 object: The bound object to deregister.
             )",
             py::arg("object"))
        .def("find_bound_object", &{{ interface_name }}::find{{object_name}}, py::return_value_policy::reference,
             R"(
             Find a bound object.

             Args:
                 id: Id of the bound object.

             Return:
                 The bound object if it exists, an empty object otherwise.
             )",
             py::arg("id"))
        /**/;

    py::class_<{{ object_interface_name }}, carb::ObjectPtr<{{ object_interface_name }}>>(m, "{{ object_interface_name }}")
        .def_property_readonly("id", &{{ object_interface_name }}::getId, py::return_value_policy::reference,
            R"(
             Get the id of this bound object.

             Return:
                 The id of this bound object.
             )")
        /**/;

    py::class_<Python{{object_name}}, {{ object_interface_name }}, carb::ObjectPtr<Python{{object_name}}>>(m, "{{object_name}}")
        .def(py::init([](const char* id) { return Python{{object_name}}::create(id); }),
             R"(
             Create a bound object.

             Args:
                 id: Id of the bound object.

             Return:
                 The bound object that was created.
             )",
             py::arg("id"))
        .def_readwrite("property_int", &Python{{object_name}}::m_memberInt,
             R"(
             Int property bound directly.
             )")
        .def_readwrite("property_bool", &Python{{object_name}}::m_memberBool,
             R"(
             Bool property bound directly.
             )")
        .def_property("property_string", &Python{{object_name}}::getMemberString, &Python{{object_name}}::setMemberString, py::return_value_policy::reference,
             R"(
             String property bound using accessors.
             )")
        .def("multiply_int_property", &Python{{object_name}}::multiplyIntProperty,
             R"(
             Bound fuction that accepts an argument.

             Args:
                 value_to_multiply: The value to multiply by.
             )",
             py::arg("value_to_multiply"))
        .def("toggle_bool_property", &Python{{object_name}}::toggleBoolProperty,
             R"(
             Bound fuction that returns a value.

             Return:
                 The toggled bool value.
             )")
        .def("append_string_property", &Python{{object_name}}::appendStringProperty, py::return_value_policy::reference,
             R"(
             Bound fuction that accepts an argument and returns a value.

             Args:
                 value_to_append: The value to append.

             Return:
                 The new string value.
             )",
             py::arg("value_to_append"))
        /**/;
}
}
