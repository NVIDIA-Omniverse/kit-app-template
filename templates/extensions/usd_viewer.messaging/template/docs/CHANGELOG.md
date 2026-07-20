# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.1.2] - 2026-05-11
### Fixed
- `makePrimsPickable` handler raised `UnboundLocalError` when the WebSocket
  payload was empty or missing the `paths` key, and the broad `except` then
  leaked the raw Python exception message (including internal variable names)
  to the streaming client. The handler now initializes `paths` to an empty
  list before the conditional so an empty payload is a clean no-op, and
  unexpected exceptions are logged server-side via `carb.log_error` while
  only a generic error string is returned to the client
  (OMPE-90584, NVBug 6100326).

### Added
- Regression test `test_make_prims_pickable_empty_payload` covering empty
  payload, missing-`paths` key, and explicit-empty-list cases.

## [0.1.1] - 2025-02-13
### Removed
- Redundant openedStageResult event dispatch

## [0.1.0] - 2024-04-26
- Initial version of basic python extension template