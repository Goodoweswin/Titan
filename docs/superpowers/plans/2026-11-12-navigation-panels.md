# Titan navigation and panel controls

> Implementation in this session follows the user's request to add ChatGPT-style back/forward and left/right panel controls.

**Goal:** Keep one fixed navigation bar across the app, restore visited workspace locations, and let users collapse either sidebar.

**Architecture:** Store navigation locations separately from analysis edits. Restore locations through the existing save/leave guards and each module's view API. Keep inspector components mounted when collapsed so display changes cannot discard their inputs.

**Stack:** Existing React, TypeScript, CSS and Tauri; no new dependencies.

## Requirements

- Fixed bar: back, forward, left sidebar toggle, current location, right inspector toggle.
- Back/forward includes Home, project, tool, analysis, analysis steps, IF fields, statistics tables/snapshots and saved WB figures. It never restores an old data revision.
- A successful new navigation after going back removes forward history. Failed or cancelled navigation leaves the history cursor unchanged. Rapid repeated navigation cannot overlap.
- Reuse save/leave guards. Disable navigation while processing, importing or showing a modal. Support Alt+Left/Right and Cmd+[/] outside text inputs.
- Left collapse remembers both the preference and existing sidebar width. The restore button remains visible.
- Right controls are available only when the current view has a contextual inspector; Home/project/plain table views have no right panel. A manually collapsed inspector stays collapsed across navigation and reloads.
- Collapsing keeps form state and editor components mounted and gives the content the freed space. Preserve light/dark palettes and small-window usability.
- Native installation keeps the existing app and library backup and records exact source/build hashes.

## Implementation

- [x] Add location/history types and pure history operations in `src/workspace-navigation.ts`, with tests for duplicate locations, cursor movement and branching.
- [x] Add history and panel preference hooks plus `WorkspaceNavigation.tsx` and shared CSS.
- [x] Extend IF/statistics view reports and register guarded restoration of steps and resources, preserving data edits.
- [x] Connect App's screen, WB step/figure state and existing navigation guards to the shared controls.
- [x] Exercise cross-module navigation, collapse persistence, contextual availability, cancelled leave prompts and source identity through browser tests. Run production build and the frontend test suite.
- [x] Build the Mac app, back up and install, exercise actual navigation and panel controls, and update the version registry.

The navigation build was exercised in the native app. The compact-font build was installed and its sidebar was visible. After the user completed macOS account verification, the old library loaded and the saved WB analysis reopened. Restoration of the unconfirmed TIFF chooser is tracked in the successor sidebar-appearance verification report. The full final-source GitHub suite passed (83 browser, 88 frontend unit, 346 Python tests and 5 subtests).

## Review focus

- A rename or autosave must not create history entries; switching a project must not record a temporary previous-module report.
- Back inside a statistics project must preserve its edited values and undo stack; frozen snapshots must restore their own dataset/run.
- An unavailable project, table or saved figure must report failure without advancing the cursor or silently opening a different resource.
- Closing an inspector must also remove its keyboard targets; restoring the left sidebar must recover its saved width.
- A failed save or rejected draft-discard prompt must preserve the current view and forward history.
