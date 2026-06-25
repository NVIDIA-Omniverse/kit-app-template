/*
 * SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: LicenseRef-NvidiaProprietary
 *
 * NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
 * property and proprietary rights in and to this material, related
 * documentation and any modifications thereto. Any use, reproduction,
 * disclosure or distribution of this material and related documentation
 * without an express license agreement from NVIDIA CORPORATION or
 * its affiliates is strictly prohibited.
 */

#include <carb/BindingsUtils.h>
#include <doctest/doctest.h>

CARB_BINDINGS("{{ extension_name }}.tests")

TEST_SUITE("{{ extension_name }}.tests Test Suite") {
    TEST_CASE("Sample Test Case") {
        CHECK(5 == 5);
    }
}