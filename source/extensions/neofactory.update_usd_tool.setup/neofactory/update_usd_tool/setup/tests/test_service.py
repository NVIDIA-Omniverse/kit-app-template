# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# NOTE:
#   omni.kit.test - std python's unittest module with additional wrapping to add support for async/await tests
#   For most things refer to unittest docs: https://docs.python.org/3/library/unittest.html
# Import extension python module we are testing with absolute import path, as if we are an external user (other extension)
import neofactory.update_usd_tool.setup
from neofactory.update_usd_tool.setup.service import router
import omni.kit.test


# Having a test class derived from omni.kit.test.AsyncTestCase declared on the root of the module
# will make it auto-discoverable by omni.kit.test
class Test(omni.kit.test.AsyncTestCaseFailOnLogError):
    # Before running each test
    async def setUp(self):
        pass

    # After running each test
    async def tearDown(self):
        pass

    # Test to ensure that the router is properly initialized and not None
    async def test_router_initialization(self):
        # Check that router is not None
        self.assertIsNotNone(router, "Router should be initialized")

        # Optionally, check that router has the endpoint registered (by checking its routes)
        # This step assumes that the route '/generate_cube' should be one of the registered routes
        routes = [route for route in router.routes if route.path == "/generate_cube"]
        self.assertTrue(len(routes) > 0, "The generate_cube endpoint should be registered in the router")
