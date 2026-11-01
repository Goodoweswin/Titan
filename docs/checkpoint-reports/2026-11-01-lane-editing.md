# Titan 0.3.0 canvas editing follow-up

- Separate region selection from lane manipulation. Green overlays route lane gestures; selected handles render above overlays, both boundaries editable. Keyboard movement uses original coordinate pixels and clamps to analysis window and neighboring lanes.
- Confirmed measurements create editable drafts directly. Moving/resizing a lane transforms only that lane's existing peaks/backgrounds; other manually checked candidates remain unchanged. Confirmation remains atomic.
- Canvas drafts have local undo/redo, prioritized by the existing header and shortcuts. Restoring history cancels outstanding requests; redo restarts an unfinished peak proposal. Global history retains saved original paths.
- Rotation creates a separate asset sharing the immutable verified source, with an explicit angle and source identity. Quarter turns permute pixels exactly. Fine rotation resamples detection/preview only; quantitative band/background membership maps corrected rectangles to original pixel centers. Background union and source clipping use the existing measurement contract. Corrected reference replacement requires explicit candidate-to-lane mapping.
- Original file, page and transform remain portable through project save/open and export metadata. The existing beta boundary remains: synthetic correctness checks do not establish performance on every real WB acquisition.

Verification results are recorded in `artifacts/lane-editing/` after the final checks.

Final verification: 56 frontend unit tests, 182 Python tests plus 5 subtests, 6 Rust tests, and all 31 browser tests passed. The affected 8 browser workflows were rerun after the final undo/view synchronization fix; all 5 new browser tests passed again after the final copy update. Production app built and signed; the packaged worker passed original-pixel rotation/profile/save-reopen checks and existing lane numerical/Excel export checks. Installed at `/Applications/Titan.app`, with prior app backed up. The running native window was deliberately left open for the user to save and reopen; no new native-window capture was taken.
