# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.32] - 2023-11-02
### Changed
- OMFP-3224: Added regression test
- Added unit tests for state manager

## [1.0.31] - 2023-10-25
### Changed
- OMFP-3094: Restored Window/Viewport menu

## [1.0.30] - 2023-10-26
### Changed
- OMFP-2904: Show "Examples" by default in Layout mode

## [1.0.29] - 2023-10-25
### Changed
- OMFP-3224: Fix stage template light directions.

## [1.0.28] - 2023-10-23
### Changed
- OMFP-2654: Upgraded carb.imgui with omni.kit.imgui

## [1.0.27] - 2023-10-20
### Changed
- OMFP-2649: Missed the Layout item, it is now hidden as requested.

## [1.0.26] - 2023-10-20
### Changed
- Update embedded light rigs and textures

## [1.0.25] - 2023-10-19
### Changed
- Added regression test for OMFP-2304

## [1.0.24] - 2023-10-19
### Changed
- OMFP-1981: always load the default layout when startup the app

## [1.0.23] - 2023-10-18
### Changed
- OMFP-2649: Hiding menu entries.

## [1.0.22] - 2023-10-18
### Changed
- Updated About dialog PNG to match the new application icon.

## [1.0.21] - 2023-10-18
### Changed
- OMFP-2737: Do no rebuild menu (change menu layout) if layout is same

## [1.0.20] - 2023-10-18
### Changed
- make windows invisible which are not desired to be in Review mode, OMFP-2252 activity progress window and OMFP-1981 scene optimizer window.
- OMFP-1981: when user switch between modes, make sure the user defined layout in Layout mode is kept.

## [1.0.19] - 2023-10-17
### Changed
- OMFP-2547 - remove markup from modal list, markup window visibility is now handled in omni.kit.markup.core

## [1.0.18] - 2023-10-17
### Changed
- Fixed test

## [1.0.17] - 2023-10-16
### Changed
- Navigation bar visibility fixes

## [1.0.16] - 2023-10-13
### Changed
- Waypoint and markup visibilities are bound to their list windows

## [1.0.15] - 2023-10-12
### Changed
- OMFP-2417 - Rename 'comment' -> 'review' and 'modify' -> 'layout'

## [1.0.14] - 2023-10-12
### Changed
- Added more unit tests.

## [1.0.13] - 2023-10-11
### Changed
- OMFP-2328: Fix "Sunnysky" oriented incorrectly

## [1.0.12] - 2023-10-10
### Changed
- OMFP-2226 - Remove second Viewport menu item from layouts.

## [1.0.11] - 2023-10-11
### Changed
- Added UI state manager.

## [1.0.10] - 2023-10-10
### Changed
- Deactivate tools when app mode is changed.

## [1.0.9] - 2023-10-09
### Changed
- OMFP-2200 - Disabling the viewport expansion, this should keep us locked to a 16:9 aspect ratio.

## [1.0.8] - 2023-10-06
### Changed
- Added a new stage template and made it default

## [1.0.7] - 2023-10-06
### Changed
- Enable UI aware "expand_viewport" mode rather than lower-level fill_viewport mode

## [1.0.6] - 2023-10-05
### Changed
- Used allowlists for building main menu entries to guard against unexpected menus.

## [1.0.5] - 2023-10-05
### Fixed
- Regression in hiding viewport toolbar.

## [1.0.4] - 2023-10-04
### Changed
- Modify mode now shows selected menus on main menubar.

## [1.0.3] - 2023-10-04
- Hide Viewport top toolbar in Comment Mode

## [1.0.2] - 2023-10-03
- Navigation Toolbar hidden by default in Modify Mode

## [1.0.1] - 2023-09-27
- Renamed to omni.usd_explorer.setup


## [1.0.0] - 2021-04-26
- Initial version of extension UI template with a window
