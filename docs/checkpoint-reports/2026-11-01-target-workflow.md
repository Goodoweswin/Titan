# Titan target workflow parity and rotation guides

User-reported issues: rotation lacked useful alignment guides; target placement drifted for differently cropped images and target handles were less usable than reference handles.

- Rotation preview now has fixed, independently draggable horizontal/vertical guides, keyboard movement, center reset and visibility. Faint grid stays behind the visible axes.
- Target template transfer uses selected protein regions for different images; same-image x remains absolute. Copied target columns occupy the selected target y interval. Legacy full-height layouts show handles inside the visible analysis region.
- No-lane states enter region-selection mode, including a new target on the same image. Lane-list selection focuses the canvas for keyboard nudging. Group translation clamps at valid boundaries.
- Added explicit target image import with newly imported image auto-selection. Target actions distinguish reuse of reference positions from detecting positions in the target. Detection requires a complete explicit one-to-one mapping to reference identities, preserving missing slots; mismatched counts do not silently renumber lanes.
- Re-identification preserves adjusted target x coordinates while applying the newly selected protein window. Switching the corresponding reference rebuilds from the selected reference, rather than silently retaining the old linkage. Reference-choice changes are undoable and old geometry is disabled until re-identification.

Verification results are recorded in `artifacts/target-parity/` after final checks. No real experimental project is modified by browser tests; test libraries and fixtures are isolated.

Final verification: 58 frontend unit tests, 182 Python tests plus 5 subtests, 6 Rust tests, all 34 browser tests, and a final rerun of all 11 affected lane/rotation workflows passed. Desktop app built successfully and codesign deep/strict verification passed. Rendered guide and target-control screenshots were inspected. The running user window is left open; reopening Titan loads the new bundle.
