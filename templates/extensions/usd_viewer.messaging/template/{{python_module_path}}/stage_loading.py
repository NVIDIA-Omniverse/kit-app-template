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
import os

import carb
import carb.events
import carb.tokens
from carb.eventdispatcher import get_eventdispatcher

import omni.client
import omni.kit.app
import omni.kit.livestream.messaging as messaging
import omni.usd


class LoadingManager:
    """Manages the loading of USD stages and sends messages to the client"""
    def __init__(self):
        self._subscriptions = []  # Holds subscription pointers

        # -- state variables
        # URL of stage load request. Can be used in messaging with client.
        self._requested_stage_url: str = ""
        self._stage_is_opening: bool = False

        # URL of loaded stage. Should not be used in messaging with client
        # because it may reveal directory paths in environment where
        # application runs.
        self._opened_stage_url: str = ""
        self._stage_has_opened = False
        self._streaming_manager_is_busy: bool = False

        # States if opened stage is opened from storage as in not a
        # new unsaved stage
        self._persisted_stage: bool = False
        self._is_evaluating_loading_status: bool = False

        # -- register outgoing events/messages
        outgoing = [
            "openedStageResult",  # notify when USD Stage has loaded.
            "updateProgressAmount",  # Status bar event denoting progress
            "updateProgressActivity",  # Status bar event denoting activity
            "loadingStateResponse",  # Response to loadingStateQuery
        ]

        for o in outgoing:
            messaging.register_event_type_to_send(o)
            omni.kit.app.register_event_alias(
                carb.events.type_from_string(o),
                o,
            )

        # -- register incoming events/messages
        incoming = {
            'openStageRequest': self._on_open_stage,  # request to open a stage
            # internal event to capture progress status
            "omni.kit.window.status_bar@progress": self._on_progress,
            # internal event to capture progress activity
            "omni.kit.window.status_bar@activity": self._on_activity,
            "loadingStateQuery": self._on_load_state_query,
        }
        ed = get_eventdispatcher()
        for event_type, handler in incoming.items():
            # Registering event aliases for incoming events that now leverage Events 2.0
            # TODO: Remove this when all clients have migrated to Events 2.0
            # This is a temporary solution to ensure compatibility with existing clients
            omni.kit.app.register_event_alias(
                carb.events.type_from_string(event_type),
                event_type,
            )
            self._subscriptions.append(
                ed.observe_event(
                    observer_name=f"LoadingManager:{event_type}",
                    event_name=event_type,
                    on_event=handler
                )
            )
        usd_context = omni.usd.get_context()
        # -- subscribe to stage events
        self._subscriptions.extend([
            ed.observe_event(
                observer_name="LoadingManager:stage:opening",
                event_name=usd_context.stage_event_name(omni.usd.StageEventType.OPENING),
                on_event=self._on_stage_event_opening,
            ),
            ed.observe_event(
                observer_name="LoadingManager:stage:assets_loaded",
                event_name=usd_context.stage_event_name(omni.usd.StageEventType.ASSETS_LOADED),
                on_event=self._on_stage_event_assets_loaded,
            ),
        ])

        self._subscriptions.append(
            ed.observe_event(
                observer_name="LoadingManager:stage:streaming_status",
                event_name="omni.streamingstatus:streaming_status",
                on_event=self._on_rxt_streaming_event,
            )
        )

    def _on_load_state_query(self, event: carb.events.IEvent) -> None:
        payload = {"loading_state": "idle", "url": self._opened_stage_url}
        if self._stage_is_opening:
            payload = { "loading_state": "busy", "url": self._requested_stage_url }
        elif self._stage_has_opened:
            payload = { "loading_state": "idle", "url": self._requested_stage_url }

        get_eventdispatcher().dispatch_event("loadingStateResponse", payload=payload)


    def _on_open_stage(self, event: carb.events.IEvent) -> None:
        """
        Handler for `openStageRequest` event.

        Starts loading a given URL, will send success if the layer is already
        loaded, and an error on any failure.
        """

        if "url" not in event.payload:
            carb.log_error(
                f"Unexpected message payload: missing \"url\" key. Payload: '{event.payload}'")
            return

        self._requested_stage_url = event.payload["url"]
        carb.log_info(
            f"Received message to load '{self._requested_stage_url}'"
        )

        def process_url(url):
            # Using a single leading `.` to signify that the path is relative to the ${app} token's parent directory
            # Because we've moved the samples out of the app directory, we need to check for that here
            # in the samples extension directory.
            # If that doesn't exist (using older version of the extension), we fall back to old behavior.
            if url.startswith(("./", ".\\")):
                if url.startswith(("./samples", ".\\samples")):
                    sample_url = carb.tokens.acquire_tokens_interface().resolve(
                        "${omni.usd_viewer.samples}/" + url[1:].replace("samples", "samples_data")
                    )
                    if os.path.exists(sample_url):
                        return sample_url
                return carb.tokens.acquire_tokens_interface().resolve(
                    "${app}/.." + url[1:]
                )
            return carb.tokens.acquire_tokens_interface().resolve(url)

        # Check to see if we've already loaded the current stage.
        url = process_url(self._requested_stage_url)

        stage = omni.usd.get_context().get_stage()
        current_stage = stage.GetRootLayer().identifier if stage else ''

        # If we are, we don't need to reload the file, instead we'll just send the success message.
        if omni.client.utils.equal_urls(url, current_stage):
            carb.log_info(f'Client requested to open a stage that is already open: {url}')
            payload = {"url": self._requested_stage_url, "result": "success", "error": ''}
            get_eventdispatcher().dispatch_event("openedStageResult", payload=payload)
            self._reset_state()
            return

        # Asynchronously load the incoming stage
        async def open_stage():
            carb.log_info(f'Opening stage per client request: {url}')
            usd_context = omni.usd.get_context()
            if url:
                result, error = await usd_context.open_stage_async(url, omni.usd.UsdContextInitialLoadSet.LOAD_ALL)
            else:
                result, error = await usd_context.new_stage_async()

            if result is not True:
                # Send message to client that loading failed.
                carb.log_warn(f'The file that the client requested failed to load: {url} (error: {error})')
                payload = {"url": url, "result": "error", "error": error}
                get_eventdispatcher().dispatch_event("openedStageResult", payload=payload)
                self._reset_state()
                return

        asyncio.ensure_future(open_stage())

    def _on_stage_event_opening(self, event) -> None:
        """Manage extension state via the stage event stream.
        When a new stage is open we reload the data model and
        set the state for the UI.

        Args:
            event (carb.events.IEvent): Event type
        """
        self._stage_is_opening = True
        payload: dict = dict(event.payload)
        if 'val' in payload.keys():
            self._opened_stage_url = payload['val']
        else:
            self._opened_stage_url = ''
        self._persisted_stage = True if self._opened_stage_url else False
        return

    def _on_stage_event_assets_loaded(self, event) -> None:
        """Manage extension state via the stage event stream.
        When a new stage is open we reload the data model and
        set the state for the UI.

        Args:
            event (carb.events.IEvent): Event type
        """
        # Check that a stage is opening. Assets can load after stage has opened.
        if not self._stage_is_opening:
            return
        self._stage_is_opening = False
        self._stage_has_opened = True

        # Async call to evaluate opened state
        asyncio.ensure_future(self._evaluate_load_status())
        return

    def _on_rxt_streaming_event(self, event) -> None:
        """
        Notes streaming manager's busy state

        Args:
            event (carb.events.IEvent): Contains payload sender and type -
            https://docs.omniverse.nvidia.com/kit/docs/kit-manual/105.0/carb.events/carb.events.IEvent.html
        """
        self._streaming_manager_is_busy = event.payload['isBusy']

    async def _evaluate_load_status(self):
        """
        If streaming manager is not busy and the stage is loaded from storage,
        notify the client.
        """
        # Only evaluate for stage loaded from storage.
        if not self._persisted_stage:
            return

        if self._is_evaluating_loading_status:
            return
        self._is_evaluating_loading_status = True

        # Wait until all dependencies have loaded by streaming manager
        while self._streaming_manager_is_busy or not self._stage_has_opened:
            await omni.kit.app.get_app().next_update_async()

        for _ in range(2):
            await omni.kit.app.get_app().next_update_async()

        # Stage has loaded with all dependencies. Send message to client.
        url = self._requested_stage_url if self._requested_stage_url  else '[obfuscated]'
        carb.log_info(
            f'Sending message to client that stage has loaded: {url}'
        )
        payload = {"url": url, "result": "success", "error": ''}
        get_eventdispatcher().dispatch_event("openedStageResult", payload=payload)

        # reset
        self._is_evaluating_loading_status = False
        self._reset_state()

    def _on_progress(self, event: carb.events.IEvent):
        """
        Handler for `omni.kit.window.status_bar@progress` event.
        This forwards the statusbar progress events to the streaming client.
        """
        # Only notify for stage loaded from storage.
        if not self._persisted_stage:
            return

        # Send progress message
        carb.log_info('Sending message to client about loading progress.')
        get_eventdispatcher().dispatch_event("updateProgressAmount", payload=dict(event.payload))

    def _on_activity(self, event: carb.events.IEvent):
        """
        Handler for `omni.kit.window.status_bar@activity` event.
        This forwards the statusbar activity events to the streaming client.
        """
        # Only notify for stage loaded from storage.
        if not self._persisted_stage:
            return

        carb.log_info('Storing message about loading activity.')
        # Send activity message
        carb.log_info('Sending message to client about loading activity.')
        get_eventdispatcher().dispatch_event("updateProgressActivity", payload=dict(event.payload))

    def on_shutdown(self) -> None:
        """
        Clean up subscriptions
        """
        if self._subscriptions:
            self._subscriptions.clear()

    def _reset_state(self):
        """
        Reset the internal state - ready for new stage to be loaded
        """
        stage = omni.usd.get_context().get_stage()
        self._requested_stage_url = ""
        self._opened_stage_url = stage.GetRootLayer().identifier if stage else ""
        self._stage_has_opened = False
        self._streaming_manager_is_busy = False
        self._persisted_stage = False
