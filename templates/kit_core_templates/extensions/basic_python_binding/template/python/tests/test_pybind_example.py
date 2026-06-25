## Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
##
## NVIDIA CORPORATION and its licensors retain all intellectual property
## and proprietary rights in and to this software, related documentation
## and any modifications thereto.  Any use, reproduction, disclosure or
## distribution of this software and related documentation without an express
## license agreement from NVIDIA CORPORATION is strictly prohibited.
##
import omni.kit.test

import {{ python_module }}


class TestPybindExample(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        # Cache the pybind interface.
        self.bound_interface = {{ python_module }}.get_bound_interface()

        # Create and register a bound object.
        self.bound_object = {{ python_module }}.{{ object_name }}("test_bound_object")
        self.bound_object.property_int = 9
        self.bound_object.property_bool = True
        self.bound_object.property_string = "Ninety-Nine"
        self.bound_interface.register_bound_object(self.bound_object)

    async def tearDown(self):
        # Deregister and clear the bound object.
        self.bound_interface.deregister_bound_object(self.bound_object)
        self.bound_object = None

        # Clear the pybind interface.
        self.bound_interface = None

    async def test_find_bound_object(self):
        found_object = self.bound_interface.find_bound_object("test_bound_object")
        self.assertIsNotNone(found_object)

    async def test_find_unregistered_bound_object(self):
        found_object = self.bound_interface.find_bound_object("unregistered_object")
        self.assertIsNone(found_object)

    async def test_access_bound_object_properties(self):
        self.assertEqual(self.bound_object.id, "test_bound_object")
        self.assertEqual(self.bound_object.property_int, 9)
        self.assertEqual(self.bound_object.property_bool, True)
        self.assertEqual(self.bound_object.property_string, "Ninety-Nine")

    async def test_call_bound_object_functions(self):
        # Test calling a bound function that accepts an argument.
        self.bound_object.multiply_int_property(9)
        self.assertEqual(self.bound_object.property_int, 81)

        # Test calling a bound function that returns a value.
        result = self.bound_object.toggle_bool_property()
        self.assertEqual(result, False)
        self.assertEqual(self.bound_object.property_bool, False)

        # Test calling a bound function that accepts an argument and returns a value.
        result = self.bound_object.append_string_property(" Red Balloons")
        self.assertEqual(result, "Ninety-Nine Red Balloons")
        self.assertEqual(self.bound_object.property_string, "Ninety-Nine Red Balloons")
