# Titan 0.4.2 beta.1 Desktop Release Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with one independent final review before publication.

**Goal:** Publish matching macOS arm64 DMG/App ZIP and Windows x64 EXE, checksums and dependency notices on GitHub.

**Architecture:** Integrate the current GitHub main (`ef2c409`) into the existing isolated account worktree, retaining its DirectMail preparation documentation. Build both desktop platforms from one immutable tag using GitHub Actions. Compile the public ECS issuer into both binaries and verify the resulting native artifacts before publication.

**Tech Stack:** Tauri 2, React/TypeScript, Python scientific sidecar, GitHub Actions, Rust native account bridge.

**Spec:** User instruction to package and publish the latest Mac and Windows Apps; existing account design and current managed-mode ECS deployment.

## Global Constraints

- Keep the original dirty Desktop source tree and existing worktrees intact.
- Display version `0.4.2`; prerelease tag `v0.4.2-beta.1`.
- Both native builds use `TITAN_ACCOUNTS_ISSUER=https://121.40.43.188`.
- Preserve `com.titan.wb`, existing projects and scientific modules.
- Managed login is live; self-service registration, verification/recovery delivery and Pilotus merging remain unavailable.
- macOS is Apple Silicon/macOS 14+; Windows is x64/Windows 10–11. Beta build does not imply commercial signing or full Windows native UI acceptance.
- No live ECS, DNS, account/password or installed-App mutation is required to publish these packages.

## Review Focus

- A clean CI runner must receive the compiled issuer; an environment variable set only on a developer Mac is insufficient.
- Version manifests and downloaded artifact names must agree across both platforms.
- Publication waits for all matrix builds and packaged-engine verification.
- Scientific resources and third-party notices remain bundled, with no test-only resource override in release packages.
- Release notes distinguish available managed login from unfinished mail and Windows interactive acceptance.

## Tasks

- [x] Integrate current remote main without modifying other checkouts; merge `c330d73`.
- [x] Bump the desktop manifests and scientific-engine version, set the release issuer, and add a native-artifact verification report plus Rust tests to both platform jobs. Add release notes and a pending registry entry.
- [x] Run frontend/science/native/account suites and a local Mac package build; verify embedded issuer, signature and versions. Obtain one read-only reviewer assessment and address material findings.
- [ ] Publish the reviewed source and immutable tag. Follow both Actions builds through completion, resolve failures without force-moving released tags, and verify actual release assets/checksums.
- [ ] Record the final source/workflow/assets evidence and report the two download links.

## Execution Decisions

- The user explicitly authorized publication; no separate merge/publish menu is needed.
- The existing linked worktree is clean and isolated; no additional checkout is created.
- GitHub main already contains the account implementation and latest menu work. The account-only branch differs by one mail-preparation documentation commit; both are retained.
- The connector supports repository inspection but not publishing tags. Existing Git authentication has the necessary repository/workflow access; native Git pushes and the repository's Actions publisher perform publication.
- Release metadata changes do not need tests that merely mirror field assignments. Existing suites and an actual native-binary issuer/version/hash report validate the resulting artifacts.
- Independent review of `ef2c409..6d3c525`: no Critical/Important/Minor findings. Interactive Windows acceptance and real scientific validity remain explicitly outside the beta's automated evidence; live managed HTTPS health is checked separately, and final downloaded asset integrity is still required.
- Actual bundled-engine verification found the retained `0.4.1` engine version after the desktop bump (canonical RED: packaged health and source-version assertion). Include the engine version in the source-manifest guard, set it to `0.4.2`, rebuild the sidecar and packages, and require full scientific tests plus packaged health/export/signature verification before push.
- Final corrective verification is GREEN: scientific source suite 346 +5 subtests, rebuilt sidecar, actual copied Mac bundle health/version/save/reopen/export/Excel/signature checks, native issuer/0.4.2 metadata, and notice inventory equality. Frontend140, Rust47 +2ignored, accounts191 and browser106 were also green; the engine follow-up changed version metadata and the release guard only.
- Local metadata collection initially raced the first package build. A completed sequential metadata/notices collection and subsequent rebundle produced an identical bundled notice inventory (818 records); CI already runs those commands sequentially.
