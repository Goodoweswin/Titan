# Titan WB Open Source Release Plan

> **For agentic workers:** Use executing-plans to complete the release in the current session. User requested all project sources and Mac/Windows packages be published as an open source project, and selected MIT.

**Goal:** Complete main with source, public documentation, MIT licensing, CI and a dual-platform prerelease.
**Architecture:** Preserve application behavior; extend repository metadata and existing native packaging. Dependencies and license text become bundled resources. Version tag drives native platform builds and a prerelease with checksums.
**Tech Stack:** Existing React/TypeScript, Tauri/Rust, Python; GitHub Actions and Releases.
**Spec:** User authorization in this conversation: 全部上传，按照开源项目; MIT selected explicitly.

## Constraints
- Keep source and history documents; exclude virtualenv, caches, generated executables and user projects from Git. Distribute binaries as release assets.
- Include only synthetic sample data. Remove machine-specific personal paths from public docs/examples.
- Publish macOS 14+ Apple Silicon and Windows 10/11 x64. No Intel/Linux support claim.
- Label beta status and distinguish automated checks from real WB/native GUI acceptance.

## Tasks
- [x] Inspect current local/remote differences and synthetic data; obtain license choice.
- [x] Add README, LICENSE, contribution/security documents, changelog, issue/PR templates and validation roadmap.
- [x] Add CI and native release workflows, third-party resource inclusion and platform notice archives.
- [x] Verify local suites, documentation links, file selection and fresh release review.
- [ ] Publish complete snapshot to main, tag v0.1.0-beta.1 and follow builds until successful.
- [ ] Download/check release assets, verify public main/release links and record results.

## Decisions
- MIT was selected by the user. Copyright holder is Titan WB contributors.
- Existing app version stays 0.1.0; prerelease tag beta.1 communicates validation status.
- Main is currently only an initial README. Integrate the existing Windows build branch by fast-forward from its full-source descendant, preserving remote history.
- Native packages are rebuilt to include the exact source snapshot and dependency notices. Existing binaries remain historical local outputs.

## Verification and review
- Local suites: 39 Vitest + 74 Python + 2 Rust + 16 browser tests all passed; TypeScript/Vite build passed. Public documentation links and file/path scan passed.
- Fresh release review found two P2 issues: contributor quickstart omitted ignored-resource generation; license collection missed LICENCE spelling. Both fixed before publication. Actual plist inventory regression failed before fix and passed after regenerating notices.
