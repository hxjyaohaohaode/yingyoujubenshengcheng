# System Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate current stability faults that block reliable long-script generation and establish a measurable hardening baseline for deeper optimization.

**Architecture:** Focus the first wave on deterministic failures already present in the running system: broken runtime config access, pipeline state serialization drift, volatile task progress tracking, and mismatched WebSocket protocol events. Add regression tests around the new helpers so later performance work has a stable base.

**Tech Stack:** FastAPI, SQLAlchemy async, Celery, Redis, React, TypeScript, unittest

---

### Task 1: Runtime Config Unification

**Files:**
- Create: `backend/services/project_runtime.py`
- Modify: `backend/api/ai.py`
- Modify: `backend/api/export.py`
- Test: `backend/tests/test_project_runtime.py`

**Step 1: Write the failing test**
- Cover missing `Project.genre/style/target_word_count/current_phase/core_truth` access through a runtime view abstraction.

**Step 2: Run test to verify it fails**
- Run: `python -m unittest backend.tests.test_project_runtime -v`
- Expected: FAIL because runtime helper does not exist.

**Step 3: Write minimal implementation**
- Add a runtime loader that combines `Project` and `ProjectConfig`.
- Replace direct broken `project.<missing_field>` reads in AI and export endpoints.

**Step 4: Run test to verify it passes**
- Run: `python -m unittest backend.tests.test_project_runtime -v`
- Expected: PASS

**Step 5: Commit**
- Commit after endpoint regressions are fixed.

### Task 2: Pipeline State Durability

**Files:**
- Modify: `backend/core/pipeline/state_machine.py`
- Test: `backend/tests/test_pipeline_state_machine.py`

**Step 1: Write the failing test**
- Cover JSON string payloads coming back from raw SQL and verify state coercion returns dict/list containers.

**Step 2: Run test to verify it fails**
- Run: `python -m unittest backend.tests.test_pipeline_state_machine -v`
- Expected: FAIL because serialized strings are not normalized.

**Step 3: Write minimal implementation**
- Add JSON container coercion helpers for `result_data`, `task_results`, and `config`.
- Normalize malformed payloads instead of propagating strings.

**Step 4: Run test to verify it passes**
- Run: `python -m unittest backend.tests.test_pipeline_state_machine -v`
- Expected: PASS

**Step 5: Commit**
- Commit after pipeline API reads render correctly.

### Task 3: Persistent Task Progress

**Files:**
- Modify: `backend/tasks/__init__.py`
- Test: `backend/tests/test_task_progress.py`

**Step 1: Write the failing test**
- Cover persistence fallback rules: Redis first, in-memory fallback if Redis is unavailable.

**Step 2: Run test to verify it fails**
- Run: `python -m unittest backend.tests.test_task_progress -v`
- Expected: FAIL because progress only exists in process memory.

**Step 3: Write minimal implementation**
- Persist progress records to Redis with TTL.
- Keep in-memory fallback for local/dev resilience.

**Step 4: Run test to verify it passes**
- Run: `python -m unittest backend.tests.test_task_progress -v`
- Expected: PASS

**Step 5: Commit**
- Commit after task progress endpoint still returns the expected schema.

### Task 4: Realtime Protocol Compatibility

**Files:**
- Modify: `backend/websocket/manager.py`
- Modify: `frontend/src/hooks/useWebSocket.ts`
- Modify: `backend/Dockerfile`

**Step 1: Write the failing test**
- Manual contract: frontend should update on both `agent_status` and legacy `agent_update`, and should not ignore `task_progress` without `agent_name`.

**Step 2: Run manual verification**
- Build frontend and inspect generated type-safe output.

**Step 3: Write minimal implementation**
- Emit `agent_status` from backend while keeping payload backward-compatible.
- Relax frontend event parsing for task progress.
- Fix Dockerfile copy list so container builds from current repo layout.

**Step 4: Run verification**
- Run: `npm run build`
- Expected: PASS

**Step 5: Commit**
- Commit after backend compile and frontend build succeed.

### Task 5: Whitepaper Baseline

**Files:**
- Create: `docs/极致优化白皮书.md`

**Step 1: Capture verified findings**
- List current defects, hardening scope, deletions still pending, and the metrics that cannot be claimed without benchmark data.

**Step 2: Add rollout and rollback**
- Document first-wave rollback points and next benchmark gates for long-script workloads.

**Step 3: Final verification**
- Ensure the document only states measured or directly verified facts.
