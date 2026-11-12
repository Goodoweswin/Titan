# Native CI prerequisite correction — 2026-11-12

Base `f1aa960`. Owned changes: `.github/workflows/accounts.yml`, durable `docs/checkpoint-reports/accounts/implementation-verification.md`, and this report. No subagents, product/science code changes, dependency lock edits, installed local dependencies, service starts, GUI actions, remote CI runs or pushes.

## Correction

`native-tests` previously called `npm test` and native engine-worker tests without creating their required repository-root scientific `.venv`. Added Python 3.11 x64 via `actions/setup-python@v5`, then platform-specific locked scientific dependency installation before those tests:

- Linux Bash: `python -m venv .venv`; `.venv/bin/python -m pip install -r requirements.lock`; explicit `set -euo pipefail`.
- Windows PowerShell: `python -m venv .venv`; `.venv/Scripts/python.exe -m pip install -r requirements.lock`; `$ErrorActionPreference = 'Stop'` and an explicit `$LASTEXITCODE` check after each external command.
- Shared native test/build block now uses Bash with `set -euo pipefail` on both runner platforms so test failure cannot be masked by a later successful build. Added `PYTHONUTF8=1`, consistent with Windows packaging conventions.

No dependency installation command was executed locally. Existing `ci.yml` and `packaging/build_windows.ps1` were read as conventions; neither was changed.

## Offline validation

Using already available Python/PyYAML, parsed workflow YAML; verified the two-OS matrix, Python version/architecture, platform guards, exact `.venv` interpreter paths, placement before `npm test`, PowerShell external-exit checks and Bash failure handling. Ran `bash -n` on Linux setup/shared native command blocks. `git diff --check` passed. These are configuration checks only; no app/scientific/native suite was repeated and no remote execution is claimed. PowerShell was structurally inspected, not executed on Windows.

The durable report records the prerequisite correction and keeps remote GitHub CI/Windows installer/native acceptance pending. The seventh `Ruling:` line was copied verbatim from the execution ledger; all seven remain in original order and the prior six are unchanged. Per controller confirmation, final-startup scoped review closed the local product findings; only controller final review summary and the already recorded external/platform acceptance gates remain.

Commit: recorded in implementer final handoff/git history; this report is included in the same scoped commit.
