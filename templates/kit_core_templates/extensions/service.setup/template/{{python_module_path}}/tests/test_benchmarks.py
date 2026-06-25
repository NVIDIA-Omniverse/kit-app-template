# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import asyncio

from omni.kit.test import AsyncTestCase, BenchmarkTestCase


class TestBenchmarks(BenchmarkTestCase):
    """
    Example Benchmark class with custom metrics.
    * To use custom metrics one has to derive from  `BenchmarkTestCase`.
    * Benchmark methods have to start with the 'benchmark' prefix.
    * The runtime of the benchmark methods and their skip state
      belong to the default metrics which are always reported.
    """

    def setUp(self):
        pass

    async def benchmark_sleepy_with_custom_metrics(self):
        """
        Benchmark method using custom metrics.
        """
        # sample for custom metric 'sleep_time' is set to 0.1s
        self.set_metric_sample(name="sleep_time", value=0.1, unit="s")
        await asyncio.sleep(0.1)
        # sample for custom metric 'runs' is set to 1
        self.set_metric_sample(name="runs", value=1)

    async def benchmark_sleepy_with_custom_metrics_array(self):
        """
        Another benchmark method using custom metrics to demonstrate setting
        arrays for a metric, and to show that there's no crosstalk of metrics
        between benchmarks.
        """
        # array of samples for custom metric 'my_other_metric' is set to
        # [1.2ms, 0.9ms, 1.1ms]
        self.set_metric_sample_array(
            name="my_other_metric", values=[1.2, 0.9, 1.1], unit="ms"
        )
        await asyncio.sleep(0.01)


class TestBenchmarksNoCustomMetric(AsyncTestCase):
    """
    Example Benchmark class without custom metrics.
    * If you are not planning to use custom metrics you can derive
      from `AsyncTestCase`.
    * Benchmark methods have to start with the 'benchmark' prefix.
    * The runtime of the benchmark methods and their skip state
      belong to the default metrics which are always reported.
    """

    def setUp(self):
        pass

    async def benchmark_sleepy_no_custom(self):
        await asyncio.sleep(0.1)
