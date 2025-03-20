# Overview

An example C++ extension that can be used as a reference/template for creating new extensions.

Demonstrates how to reflect C++ code using pybind11 so that it can be called from Python code.

The {{ interface_name }} located in `include/{{ python_module_path }}/{{ interface_name }}.h` is:
- Implemented in `plugins/{{ extension_name }}/ExamplePybindExtension.cpp`.
- Reflected in `bindings/python/{{ extension_name }}/ExamplePybindBindings.cpp`.
- Accessed from Python in `python/tests/test_pybind_example.py` via `python/impl/example_pybind_extension.py`.


# C++ Usage Examples


## Defining Pybind Module


```
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
```
