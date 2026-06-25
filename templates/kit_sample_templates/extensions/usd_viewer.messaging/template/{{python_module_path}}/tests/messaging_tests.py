# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from pathlib import Path
from typing import Dict, List

import carb.events
import carb.tokens
import omni.kit.app
from carb.eventdispatcher import get_eventdispatcher, Event
from omni.kit.test import AsyncTestCase



async def wait_stage_loading(wait_frames: int = 2, usd_context=None, timeout=1000, timeout_error=True):
    """
    Waits for the USD stage to complete loading.

    Args:
        wait_frames (int): How many frames to wait after loading the stage if given (2 by default)
        usd_context (UsdContext): UsdContext to use (omni.usd.get_context() by default)
        timeout (int): How many frames to wait before reporting error & abort.
        timeout_error (bool): Report timeout as error (True by default)
    """
    context = usd_context if usd_context else omni.usd.get_context()
    stage_name = context.get_stage_url()

    # wait for get_stage_loading_status() files to be loaded.
    maxloops = timeout
    while True:
        _, files_loaded, total_files = context.get_stage_loading_status()
        if files_loaded or total_files:  # pragma: no cover
            await omni.kit.app.get_app().next_update_async()
            maxloops -= 1
            if maxloops == 0:
                if timeout_error:
                    carb.log_error(f"wait_stage_loading waiting for {files_loaded} vs {total_files} for {stage_name}")
                break
            continue
        break

    context.reset_renderer_accumulation()

    frame_count = 0
    while frame_count < wait_frames:
        await omni.kit.app.get_app().next_update_async()
        frame_count += 1
        continue


class MessagingTest(AsyncTestCase):
    async def setUp(self):
        self._app = omni.kit.app.get_app()
        self._ed = get_eventdispatcher()

        # Capture extension root path
        extension = "{{ extension_name }}"
        ext_root = Path(carb.tokens.get_tokens_interface().resolve({% raw %}f"${{{extension}}}"{% endraw %}))
        self._data_path = ext_root / "data"

    async def test_stage_loading_incoming(self):
        """
        Simulate incoming events of the stage loading messaging system
        """

        def on_message_event(event: Event) -> None:
            if event.event_name == "updateProgressAmount":
                outgoing["updateProgressAmount"] = True
            elif event.event_name == "updateProgressActivity":
                outgoing["updateProgressActivity"] = True

        outgoing: Dict[str, bool] = {
            "updateProgressAmount": False,   # Status bar event denoting progress
            "updateProgressActivity": False, # Status bar event denoting current activity
        }

        subscriptions: List[int] = []
        for event in outgoing.keys():
            subscriptions.append(
                self._ed.observe_event(
                    observer_name=f"MessagingTest:{event}",
                    event_name=event,
                    on_event=on_message_event,
                )
            )
            await self._app.next_update_async()

        # Send the openStageRequest event
        url = self._data_path / "testing.usd"
        self._ed.dispatch_event("openStageRequest", payload={"url": url.as_posix()})

        await wait_stage_loading(wait_frames=300)
        self.assertTrue(all(outgoing.values()))

    async def test_stage_management_incoming(self):
        """
        Simulate incoming events of the stage management messaging system
        """

        subscriptions: List[int] = []

        outgoing: Dict[str, bool] = {
            "stageSelectionChanged": False,     # notify when user selects something in the viewport.
            "getChildrenResponse": False,       # response to request for children of a prim
            "makePrimsPickableResponse": False, # response to request for primitive being pickable.
            "resetStageResponse": False,        # response to the request to reset camera attributes
        }

        def on_message_event(event: Event) -> None:
            if event.event_name == "stageSelectionChanged":
                outgoing["stageSelectionChanged"] = True
            elif event.event_name == "getChildrenResponse":
                outgoing["getChildrenResponse"] = True
            elif event.event_name == "makePrimsPickableResponse":
                outgoing["makePrimsPickableResponse"] = True
            elif event.event_name == "resetStageResponse":
                outgoing["resetStageResponse"] = True

        # Register outgoing event
        # Subscribe to messaging events
        # Send event to validate
        for event in outgoing.keys():
            subscriptions.append(
                self._ed.observe_event(
                    observer_name=f"MessagingTest:{event}",
                    event_name=event,
                    on_event=on_message_event,
                )
            )

            self._ed.dispatch_event(event, payload={})
            await self._app.next_update_async()

        # Send the openStageRequest event
        url = self._data_path / "testing.usd"
        self._ed.dispatch_event("openStageRequest", payload={"url": url.as_posix()})

        # Wait for the stage to load
        await wait_stage_loading(wait_frames=30)

        # Get children of root
        self._ed.dispatch_event("getChildrenRequest", payload={"prim_path": "/World", "filters": []})
        await self._app.next_update_async()

        # Select Prims Request
        self._ed.dispatch_event("selectPrimsRequest", payload={"paths": ["/World/Cube"]})
        await self._app.next_update_async()

        # Make Prims Pickable Request
        self._ed.dispatch_event("makePrimsPickable", payload={"paths": ["/World/Cube", "/World/Sphere"]})
        await self._app.next_update_async()

        # Reset Stage Request
        self._ed.dispatch_event("resetStage", payload={})
        await self._app.next_update_async()

        self.assertTrue(all(outgoing.values()))
