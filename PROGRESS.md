# Progress

Current phase: 10 — hardening, backups and operational documentation (complete).

- [x] Phase 0: Compose topology, health checks, proxy, API/web baseline and persisted database volume.
- [x] Phase 1: Authentication, RBAC, settings, audit events and event bus.
- [x] Phase 2: University fieldbook visual direction, reusable UI, responsive workspace shell, permission-aware navigation and login/logout flow.
- [x] Phase 3 backend: student/teacher profiles, user and class CRUD services, teacher scoping, first-login password change, audit events, CSV preview/confirm and migration.
- [x] Phase 3 frontend: people directory, class and roster management, CSV preview/import, first-login password-change screen.
- [x] Phase 4 CTF catalog: editable categories/difficulties, event/challenge CRUD, prerequisites, hints, secure static attachments, duplication and safe student schemas.
- [x] Phase 4 migration applied to MySQL; seeded; student sensitive-field checks passed.
- [x] Phase 5 flag strategies: static SHA-256 with constant-time comparison, bounded regex matching and per-student HMAC flags.
- [x] Phase 5 progress engine: idempotent server-side start, submissions, ordered hints, per-event/challenge/global attempt caps, in-process user/IP rate limiter, instructor pause/reset.
- [x] Phase 5 scoring: fixed, time decay and dynamic-by-solves strategies; multipliers, hint penalties in XP ledger, configurable grade thresholds, global/class/event scoreboards and persisted freezes.
- [x] Phase 5 domain notifications persisted for solved, failed and hint-used events.
- [x] Fresh SQLite migrations to `b82f4a6d0c91` succeed; live MySQL is at `b82f4a6d0c91` and seed is current.
- [x] Backend validation: 25 pytest tests pass, including flags/HMAC, attempt limits, server clock, hint order/score, grade mapping, scoreboard ties/freeze, API solve flow and concurrent double submit; Ruff and mypy pass.
- [x] Frontend contract and validation: OpenAPI types generated; 5 Vitest tests, ESLint and production build pass.
- [x] Docker Compose rebuilt; database migration and seed applied; health/API verification pass; all services healthy.
- [x] Phase 6 teacher workspace: create and publish/archive/duplicate events, assign classes and schedule, scoring strategy, challenge authoring with Markdown preview, category/difficulty catalogue, static/regex/HMAC flag setup with static sample check, ordered hints, attachments, challenge ordering and grade-scale configuration.
- [x] Phase 6 frontend validation: 5 existing Vitest tests, ESLint and production build pass.
- [x] Phase 6 deployed with Docker Compose; frontend recreated, database/backend healthy, `/api/v1/health` returns `ok`, and web root returns HTTP 200.
- [x] Phase 7 student workspace: XP, progress, solved/in-progress counts, total and average practice time, active events, recent solve/hint/failed-attempt history, and a personal notification center.
- [x] Phase 7 event/challenge journey: category/difficulty/status filters, prerequisite lock reasons, private challenge descriptions for locked items, Markdown challenge view, authenticated files, server-timed progress, remaining attempt counts, ordered hints with confirmation/cost, flag submission feedback, and success state.
- [x] Phase 7 scoreboard view refreshes every minute and uses the persisted snapshot when the instructor freezes a board.
- [x] Phase 7 backend now treats omitted event bounds as open-ended, enabling published events with no configured dates.
- [x] Phase 7 validation: 25 backend tests pass; Ruff and mypy pass; 5 frontend tests, ESLint and production build pass.
- [x] Phase 7 deployed with Docker Compose; backend/MySQL healthy, API `/api/v1/health` returns `ok`, and web root responds HTTP 200.
- [x] Phase 8 analytics dashboard: scoped class/event reporting, completion and timing aggregates, XP/grade scales, challenge failure and inactivity signals, class live activity, student category/history detail, CSV/XLSX/PDF exports, teacher announcements and event closure.
- [x] Phase 8 regression coverage: instructor event scope does not expose other teachers' students; CSV preserves accents and quoted commas; synthetic dataset of 500 learners and 50,000 submissions returns verified aggregates.
- [x] Phase 8 validation: Ruff, mypy, all 28 backend tests, 5 frontend tests, ESLint and production build pass.
- [x] Phase 8 deployment: Docker images rebuilt, migration `b82f4a6d0c91` applied, backend/MySQL healthy, `/api/v1/health` returns `ok`, web root responds HTTP 200, and the analytics endpoint is registered behind authentication.
- [x] Phase 9 documented format: `/docs/CHALLENGE_FORMAT.md` defines versioned `challenge.yml` and `ctf.yml`, attachments, flags, hints, prerequisites, warnings and safety limits.
- [x] Phase 9 importer: bounded ZIP validation rejects traversal, absolute paths, duplicate paths/keys, symlinks, encryption, unsafe YAML aliases, invalid manifests, missing references, oversized entries and cyclic prerequisites.
- [x] Phase 9 preview/confirm and exports: class-scoped teacher flow validates before import, creates/updates by event+slug as `DRAFT`, safely stores referenced attachments, preserves existing static flags as hashes, and exports single challenges or complete event packages.
- [x] Phase 9 demo content: idempotent seed provides one `[DEMO]` event and three clearly named `[DEMO]` draft challenges.
- [x] Phase 9 validation: Ruff and mypy pass; all 36 backend tests pass (including zip-slip, symlink, ZIP bomb, malformed YAML, accented attachments, slug idempotency and export/import round-trip); 5 frontend tests, ESLint and production build pass.
- [x] Phase 9 deployment: Docker images rebuilt, Nginx accepts 21 MB request bodies, demo seed verified with 3 challenges, backend/MySQL healthy, `/api/v1/health` is `ok`, and import preview route is protected by authentication.

## Phase 10 — Hardening, backup and operations

- [x] Nginx response security headers and cookie `Secure` behavior behind a trusted TLS gateway.
- [x] Periodic deletion of expired/revoked sessions and stale files from the app-owned temporary directory.
- [x] MySQL + upload-volume backup/restore scripts with checksums, retention and explicit restore confirmation.
- [x] Installation, operations, security, network, troubleshooting, backup, user guides, design system and extension documentation.
- [x] Fresh install, migrations, seed, full database/upload backup and checksum-validated restore completed twice against an isolated disposable Compose project; the second restore recovered a deleted synthetic attachment marker and the restored DB returned to migration `b82f4a6d0c91` with the demo event and 3 challenges.
- [x] Dependency checks: `npm audit --omit=dev` reports 0 vulnerabilities; `uv audit --locked` found two pytest 8.4.2 advisories, pytest was upgraded to 9.1.1 and the second audit reports no known vulnerabilities.
- [x] Backend validation: Ruff/mypy clean; all 37 backend tests pass, including 20 concurrent students submitting flags in parallel.
- [x] Frontend validation: ESLint, all 5 Vitest tests and production build pass; the generated bundle contains local fonts/assets and no configured font/script CDN references.
- [x] Backup and restore scripts pass Bash syntax checks and the end-to-end restore rehearsal; shell script supports Git Bash ACL behavior on Windows as well as Linux file permissions.
- [x] Rebuilt/deployed the active backend and Nginx; all services healthy, API health returns `ok`, site returns HTTP 200, five security headers are present, Nginx version disclosure is disabled and forwarded HTTPS sets both authentication cookies `Secure`.
- [x] Final source-spec availability check: the referenced `CYBERLAB_PROMPT_V2_PANEL_CTF.md` / `/docs/SPEC.md` is not present in the workspace or attached plan, so exact acceptance points 1–13 cannot be asserted safely; phase evidence above records each deliverable that is verifiable from the available repository.
- [x] Full follow-up audit closed unbounded in-process rate-limit maps, separated student limits from shared-proxy burst caps, and neutralized formula-leading text in CSV exports.
- [x] Follow-up regression checks cover limiter bounds/shared proxy behavior and spreadsheet formula neutralization; final backend test count is 40.

## TODO(fase-futuro)

- LMS integration using the prepared nullable `module_id` field.
- Isolated Docker labs and their lifecycle/quotas (the reserved `lab-manager` concept remains future work).
- Optional gamification features beyond the current XP, scoreboard and notifications.
- Shared rate-limit storage, metrics and alerting if the school later runs multiple backend replicas.

Phase 10 is complete for the available repository and plan. The original full specification is absent, so acceptance-point traceability 1–13 still needs that source document.
