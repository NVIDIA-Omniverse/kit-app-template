# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# from pathlib import Path
# from typing import Dict, List

# import carb.events
# import carb.tokens
# import omni.kit.app
# from omni.kit.test import AsyncTestCase
# # from omni.kit.test_suite.helpers import wait_stage_loading


# class MessagingTest(AsyncTestCase):
#     async def setUp(self):
#         self._app = omni.kit.app.get_app()
#         self._message_bus = self._app.get_message_bus_event_stream()

#         # Capture extension root path
#         extension = "{{ extension_name }}"
#         ext_root = Path(carb.tokens.get_tokens_interface().resolve({% raw %}f"${{{extension}}}"{% endraw %}))
#         self._data_path = ext_root / "data"

    # async def test_stage_loading_incoming(self):
    #     """
    #     Simulate incoming events of the stage loading messaging system
    #     """
    #     import omni.kit.livestream.messaging as messaging

    #     def on_message_event(event: carb.events.IEvent) -> None:
    #         if event.type == carb.events.type_from_string("updateProgressAmount"):
    #                 outgoing["updateProgressAmount"] = True
    #         elif event.type == carb.events.type_from_string("updateProgressActivity"):
    #                 outgoing["updateProgressActivity"] = True


    #     # Register the open stage request type
    #     messaging.register_event_type_to_send("openStageRequest")

    #     outgoing: Dict[str, bool] = {
    #         "updateProgressAmount": False,  # Status bar event denoting progress
    #         "updateProgressActivity": False  # Status bar event denoting current activity
    #     }

    #     subscriptions: List[int] = []
    #     for event in outgoing.keys():
    #         subscriptions.append(
    #             self._message_bus.create_subscription_to_pop(
    #                 on_message_event,
    #                 name=event
    #             )
    #         )
    #         await self._app.next_update_async()

    #     # Send the openStageRequest event
    #     event_type = carb.events.type_from_string("openStageRequest")
    #     url = self._data_path / "testing.usd"
    #     self._message_bus.dispatch(event_type, payload={"url": url.as_posix()})

    #     await wait_stage_loading(wait_frames=300)
    #     self.assertTrue(all(outgoing.values()))


    # async def test_stage_management_incoming(self):
    #     """
    #     Simulate incoming events of the stage management messaging system
    #     """
    #     import omni.kit.livestream.messaging as messaging

    #     subscriptions: List[int] = []

    #     outgoing: Dict[str, bool] = {
    #         "stageSelectionChanged": False,     # notify when user selects something in the viewport.
    #         "getChildrenResponse": False,       # response to request for children of a prim
    #         "makePrimsPickableResponse": False, # response to request for primitive being pickable.
    #         "resetStageResponse": False,        # response to the request to reset camera attributes
    #     }

    #     def on_message_event(event: carb.events.IEvent) -> None:
    #         if event.type == carb.events.type_from_string("stageSelectionChanged"):
    #             outgoing["stageSelectionChanged"] = True
    #         elif event.type == carb.events.type_from_string("getChildrenResponse"):
    #             outgoing["getChildrenResponse"] = True
    #         elif event.type == carb.events.type_from_string("makePrimsPickableResponse"):
    #             outgoing["makePrimsPickableResponse"] = True
    #         elif event.type == carb.events.type_from_string("resetStageResponse"):
    #             outgoing["resetStageResponse"] = True

    #     incoming: List[str] = [
    #         'getChildrenRequest',
    #         'selectPrimsRequest',
    #         'makePrimsPickable',
    #         'resetStage'
    #     ]

    #     # Register outgoing event
    #     # Subscribe to messaging events
    #     # Send event to validate
    #     for event in outgoing.keys():
    #         subscriptions.append(self._message_bus.create_subscription_to_pop(
    #             on_message_event,
    #             name=event
    #         ))

    #         event_type = carb.events.type_from_string(event)
    #         self._message_bus.dispatch(event_type, payload={})

    #         await self._app.next_update_async()

    #     # Send the openStageRequest event
    #     event_type = carb.events.type_from_string("openStageRequest")
    #     url = self._data_path / "testing.usd"
    #     self._message_bus.dispatch(event_type, payload={"url": url.as_posix()})

    #     # Wait for the stage to load
    #     await wait_stage_loading(wait_frames=30)

    #     # Get children of root
    #     event_type = carb.events.type_from_string("getChildrenRequest")
    #     self._message_bus.dispatch(event_type, payload={"prim_path": "/World"})
    #     await self._app.next_update_async()

    #     # Select Prims Request
    #     event_type = carb.events.type_from_string("selectPrimsRequest")
    #     self._message_bus.dispatch(event_type, payload={"paths": ["/World/Cube"]})
    #     await self._app.next_update_async()

    #     # Make Prims Pickable Request
    #     event_type = carb.events.type_from_string("makePrimsPickable")
    #     self._message_bus.dispatch(event_type, payload={"paths": ["/World/Cube", "/World/Sphere"]})
    #     await self._app.next_update_async()

    #     # Reset Stage Request
    #     event_type = carb.events.type_from_string("resetStage")
    #     self._message_bus.dispatch(event_type)
    #     await self._app.next_update_async()

    #     self.assertTrue(all(outgoing.values()))
