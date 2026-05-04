# Implementation Plan: TRF Approval System

## Overview

Implement the TRF Approval System as a Django app with PostgreSQL, Django Templates, and Alpine.js. Tasks follow the state machine defined in the design: Draft → Pending_L2 → Pending_L3 → Approved / Rejected, with remediation, notifications, and an immutable audit trail.

## Tasks

- [x] 1. Django app scaffold and data models
  - [x] 1.1 Create the `trf` Django app and register it in `INSTALLED_APPS`
    - Run `startapp trf`, add to settings, create `trf/urls.py` and wire into root `urls.py`
    - _Requirements: 1.1_

  - [x] 1.2 Implement `TRFRequest` model
    - Define `Status` TextChoices (DRAFT, PENDING_L2, PENDING_L3, APPROVED, REJECTED, REMEDIATION)
    - Fields: `project_name`, `training_start`, `status`, `submitted_by` (FK User), `submitted_at`, `remediated_at`, `previous_snapshot` (JSONField), `created_at`, `updated_at`
    - _Requirements: 1.1, 1.2, 5.3, 5.5_

  - [x] 1.3 Implement `Milestone` and `Expense` models
    - `Milestone`: FK to TRFRequest, `name`, `target_date`
    - `Expense`: FK to TRFRequest, `description`, `amount` (DecimalField), `currency` (ISO 4217)
    - _Requirements: 1.1_

  - [x] 1.4 Implement `TRFApproval` model
    - `Level` IntegerChoices (L2=2, L3=3), `Action` TextChoices (APPROVED, REJECTED)
    - Fields: FK to TRFRequest (PROTECT), `level`, `action`, `actor` (FK User PROTECT), `reason` (TextField blank=True), `acted_at` (auto_now_add)
    - _Requirements: 2.2, 2.3, 2.4, 3.2, 3.3, 3.4_

  - [x] 1.5 Implement `AuditEvent` model
    - Fields: FK to TRFRequest (PROTECT), `actor` (FK User PROTECT), `action` (CharField), `from_status`, `to_status`, `reason` (blank=True), `timestamp` (auto_now_add)
    - Add `Meta: ordering = ["timestamp"]`
    - Do NOT grant update/delete permissions at ORM level (no custom `save`/`delete` overrides that allow mutation)
    - _Requirements: 7.1, 7.3, 7.4_

  - [x] 1.6 Implement `ApproverProfile` model
    - OneToOne to User, `level` IntegerChoices (L2=2, L3=3), `is_available` (BooleanField default=True), `delegate` (self-FK nullable)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 1.7 Implement `NotificationLog` model
    - `Channel` choices (EMAIL, SLACK, IN_APP), `Result` choices (SUCCESS, FAILURE)
    - Fields: FK to TRFRequest (PROTECT), `channel`, `recipient`, `result`, `error_msg` (blank=True), `sent_at` (auto_now_add)
    - _Requirements: 4.4, 4.5_

  - [x] 1.8 Generate and apply migrations; write a data migration to seed the 6 named approvers (Aidan, Trevor, Tasneem at L2; Sharona, Melisa, Andre at L3)
    - _Requirements: 2.1, 3.1_

  - [ ]* 1.9 Write unit tests for model field constraints
    - Verify `reason` is required when `TRFApproval.action == REJECTED` at the service layer
    - Verify `AuditEvent` records cannot be deleted via ORM
    - _Requirements: 2.3, 3.3, 7.4_

- [x] 2. TRF submission form and creation view
  - [x] 2.1 Create `TRFForm` (ModelForm) with inline formsets for Milestones and Expenses
    - Validate all required fields; return field-level errors on missing values
    - _Requirements: 1.1, 1.3_

  - [x] 2.2 Implement `trf_create` view (GET/POST, Sales user only)
    - On valid POST: save TRF as DRAFT, then call `ApprovalService.submit()` to transition to PENDING_L2
    - On invalid POST: re-render form with field-level errors
    - _Requirements: 1.2, 1.3_

  - [x] 2.3 Build `trf/create.html` template with Alpine.js for dynamic milestone/expense rows
    - Add/remove milestone and expense rows client-side without page reload
    - _Requirements: 1.1_

  - [ ]* 2.4 Write unit tests for `trf_create` view
    - Valid submission → status PENDING_L2, `submitted_at` set, audit event written
    - Missing required field → 200 with field error, status stays DRAFT
    - _Requirements: 1.2, 1.3_

- [x] 3. ApprovalService — state machine core
  - [x] 3.1 Implement `TransitionError` custom exception in `trf/exceptions.py`
    - _Requirements: 2.5, 3.5, 3.6_

  - [x] 3.2 Implement `ApprovalService.submit(trf, user)`
    - Guard: TRF owner, status == DRAFT, all required fields present
    - Transition: DRAFT → PENDING_L2, set `submitted_at`, write `AuditEvent`
    - _Requirements: 1.2, 1.4_

  - [x] 3.3 Implement `ApprovalService.approve(trf, user)`
    - Guard: user has `ApproverProfile` at the correct level (L2 for PENDING_L2, L3 for PENDING_L3) and `is_available` or is active delegate
    - L3 guard: user must NOT be the same person who approved at L2 on this TRF (Req 3.6)
    - Transitions: PENDING_L2 → PENDING_L3 or PENDING_L3 → APPROVED
    - Write `TRFApproval` record and `AuditEvent`
    - _Requirements: 2.2, 2.5, 3.2, 3.5, 3.6_

  - [x] 3.4 Implement `ApprovalService.reject(trf, user, reason)`
    - Guard: same level/availability guards as approve; `reason` must be non-empty
    - Transition: PENDING_L2 or PENDING_L3 → REJECTED
    - Write `TRFApproval` record and `AuditEvent`
    - _Requirements: 2.3, 2.4, 3.3, 3.4, 3.5_

  - [x] 3.5 Implement `ApprovalService.remediate(trf, user, cleaned_data)`
    - Guard: TRF owner, status == REJECTED, at least one field differs from `previous_snapshot`
    - Snapshot current field values into `previous_snapshot` before applying changes
    - Transition: REJECTED → PENDING_L2, set `remediated_at`, write `AuditEvent`
    - _Requirements: 5.3, 5.4, 5.5_

  - [ ]* 3.6 Write property test for state machine transition validity
    - **Property 1: Only valid transitions are accepted — no sequence of actions can move a TRF to a state not reachable from its current state**
    - **Validates: Requirements 1.2, 2.2, 2.4, 3.2, 3.4, 5.3**

  - [ ]* 3.7 Write property test for approval permission exclusivity
    - **Property 2: A user who approved at L2 on a given TRF can never approve at L3 on the same TRF**
    - **Validates: Requirements 3.6**

  - [ ]* 3.8 Write unit tests for `ApprovalService`
    - Each valid transition succeeds and writes an `AuditEvent`
    - Each invalid transition raises `TransitionError`
    - Non-approver attempting approve/reject raises `PermissionError`
    - Remediation with no field changes raises `ValidationError`
    - _Requirements: 2.5, 3.5, 3.6, 5.5_

- [ ] 4. Checkpoint — ensure all model and service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Approval queue views (Level 2 and Level 3)
  - [ ] 5.1 Implement `trf_list` view
    - Sales users: see their own TRFs
    - L2 approvers (and active delegates): see TRFs with status PENDING_L2
    - L3 approvers (and active delegates): see TRFs with status PENDING_L3
    - _Requirements: 2.1, 3.1, 6.3_

  - [ ] 5.2 Build `trf/list.html` template
    - Separate queue sections for L2 and L3 approvers; show TRF project name, status badge, submission date
    - _Requirements: 2.1, 3.1_

  - [ ] 5.3 Implement `trf_approve` view (POST, level-appropriate approver)
    - Call `ApprovalService.approve()`; catch `TransitionError` → 400; catch `PermissionError` → 403
    - _Requirements: 2.2, 2.5, 3.2, 3.5_

  - [ ] 5.4 Implement `trf_reject` view (POST, level-appropriate approver)
    - Render rejection reason form on GET; call `ApprovalService.reject()` on POST
    - Validate reason non-empty before calling service
    - _Requirements: 2.3, 2.4, 3.3, 3.4_

  - [ ] 5.5 Implement `trf_detail` view and `trf/detail.html` template
    - Display all TRF fields, milestones, expenses, and full audit trail in chronological order
    - Show approve/reject buttons only to the correct approver level
    - Show "Remediate TRF" action only to TRF owner when status == REJECTED
    - _Requirements: 2.1, 3.1, 5.1, 7.2_

  - [ ]* 5.6 Write unit tests for approval queue views
    - L2 approver sees only PENDING_L2 TRFs; L3 approver sees only PENDING_L3 TRFs
    - Non-approver POSTing to approve → 403
    - Rejection without reason → form error, status unchanged
    - _Requirements: 2.1, 2.5, 3.1, 3.5_

- [ ] 6. TRF remediation view
  - [ ] 6.1 Implement `trf_remediate` view (GET/POST, TRF owner)
    - GET: render editable TRF form pre-populated with current values, display rejection reason prominently
    - POST: call `ApprovalService.remediate()`; on success redirect to detail; on no-change error re-render with message
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [ ] 6.2 Build `trf/remediate.html` template
    - Show rejection reason in a highlighted banner above the form
    - Reuse milestone/expense Alpine.js components from create template
    - _Requirements: 5.2_

  - [ ]* 6.3 Write unit tests for remediation view
    - Unchanged form → validation error, status stays REJECTED
    - Changed form → status transitions to PENDING_L2, `remediated_at` set, audit event written
    - Previous approval/rejection events preserved in audit trail
    - _Requirements: 5.3, 5.4, 5.5_

- [x] 7. NotificationService and email notifications
  - [x] 7.1 Implement `NotificationService` in `trf/notifications.py`
    - `notify_l2_approvers(trf)`: in-app notification (create `NotificationLog` IN_APP record) to all available L2 approvers (or their delegates)
    - `notify_l3_approvers(trf)`: same pattern for L3
    - `notify_submitter_rejected(trf)`: in-app notification to TRF owner
    - _Requirements: 1.4, 2.2, 2.4, 3.4_

  - [x] 7.2 Implement `notify_post_approval(trf)` in `NotificationService`
    - Send email to Finance team (project name, training start, milestones, total expenses) via `django.core.mail.send_mail`
    - Send email to Operations team (project name, training start, milestones)
    - Send Slack webhook POST to Operations channel (project name + TRF detail URL); catch all exceptions, log to `NotificationLog` with FAILURE result, do not re-raise
    - Log SUCCESS to `NotificationLog` for each successful send
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 7.3 Wire `NotificationService` calls into `ApprovalService` after each successful state transition
    - _Requirements: 1.4, 2.2, 2.4, 3.2, 3.4, 4.1, 4.2, 4.3_

  - [ ]* 7.4 Write property test for notification failure isolation
    - **Property 3: A Slack or email notification failure never rolls back a completed state transition — TRF status after a failed notification equals the status after a successful notification**
    - **Validates: Requirements 4.4, 4.5**

  - [ ]* 7.5 Write unit tests for `NotificationService`
    - Slack failure → `NotificationLog` FAILURE record created, TRF status unchanged
    - Finance email failure → `NotificationLog` FAILURE record created, TRF status unchanged
    - Successful post-approval → Finance and Ops emails sent, Slack message sent, all logged SUCCESS
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 8. Approver availability and delegation
  - [x] 8.1 Implement `set_availability` view (GET/POST, named approver only)
    - Toggle `ApproverProfile.is_available`; when marking unavailable, require selection of a delegate from the same level
    - When marking available again, clear `delegate` and restore standard routing
    - _Requirements: 6.1, 6.2, 6.6_

  - [x] 8.2 Build `trf/availability.html` template with Alpine.js toggle and delegate selector
    - _Requirements: 6.1_

  - [x] 8.3 Add all-unavailable guard in `ApprovalService`
    - If all L2 approvers are unavailable when a TRF transitions to PENDING_L2, notify L3 approvers via `NotificationService`
    - If all L3 approvers are unavailable when a TRF transitions to PENDING_L3, notify system admin
    - _Requirements: 6.4, 6.5_

  - [ ]* 8.4 Write unit tests for availability and delegation
    - Unavailable approver cannot approve; their delegate can
    - All-L2-unavailable triggers L3 warning notification
    - Approver marking themselves available clears delegate access
    - _Requirements: 6.2, 6.3, 6.4, 6.6_

- [x] 9. Audit trail display and immutability enforcement
  - [x] 9.1 Add database-level protection for `AuditEvent`
    - Create a PostgreSQL trigger (via a RunSQL migration) that raises an exception on UPDATE or DELETE of `trf_auditevent`
    - _Requirements: 7.3, 7.4_

  - [x] 9.2 Verify audit trail renders correctly on `trf_detail` view
    - Chronological list of all events: actor, action, from/to status, reason, timestamp
    - Covers remediated TRFs showing full history across multiple submission cycles
    - _Requirements: 7.1, 7.2, 5.4_

  - [ ]* 9.3 Write property test for audit trail completeness
    - **Property 4: For any sequence of valid TRF actions, the number of AuditEvent records equals the number of state transitions performed**
    - **Validates: Requirements 7.1**

  - [ ]* 9.4 Write unit tests for audit trail immutability
    - Attempting ORM delete of an `AuditEvent` raises an exception (via DB trigger)
    - Every `ApprovalService` method writes exactly one `AuditEvent`
    - _Requirements: 7.4_

- [x] 10. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use `hypothesis`; tag each test with `# Feature: trf-approval-system, Property N: ...`
- All `ApprovalService` methods must be called from views — views stay thin
- The 6 named approvers are seeded via data migration; do not hardcode names in business logic
- `previous_snapshot` on `TRFRequest` enables the remediation no-change guard (Req 5.5)
