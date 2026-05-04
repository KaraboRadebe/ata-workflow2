# Implementation Plan: Projects and Milestones

## Overview

Implement Phase 2 of the ATA Workflow Manager as a new `projects` Django app. A Django signal on `TRFRequest.post_save` atomically creates a `Project` and its `Milestone` records. A service layer (`ProjectService`, `MilestoneService`, `ProjectAuditService`) enforces all business rules. An immutable `ProjectAuditEvent` table is protected by a PostgreSQL trigger applied via `RunSQL` migration.

## Tasks

- [x] 1. Create the `projects` Django app and register it
  - Run `python manage.py startapp projects` and add `"projects"` to `INSTALLED_APPS`
  - Create `projects/urls.py` with all URL patterns from the design and wire it into the root `urls.py` under the `projects/` prefix
  - Create `projects/exceptions.py` defining `ProjectTransitionError` and `MilestoneDeletionError`
  - _Requirements: 1.1_

- [ ] 2. Implement data models
  - [x] 2.1 Implement `Project`, `Milestone`, and `ProjectAuditEvent` models in `projects/models.py`
    - `Project`: `OneToOneField` to `TRFRequest`, `Status` choices, `sales_user`, `trf_approved_at`, timestamps
    - `Milestone`: editable fields + `original_*` snapshot fields + `is_trf_expense` + `created_by`/`updated_by` + `has_cost_variance` property
    - `ProjectAuditEvent`: `Action` choices, `detail` JSONField, `auto_now_add` timestamp, `ordering = ["timestamp"]`
    - _Requirements: 1.2, 1.3, 1.6, 2.2, 2.3, 2.4, 2.5, 9.1, 9.2, 9.4_

  - [x] 2.2 Create and run initial migration for all three models
    - Generate migration with `makemigrations projects`
    - _Requirements: 1.6_

  - [x] 2.3 Create a second migration that applies the PostgreSQL immutability trigger via `RunSQL`
    - Define `prevent_audit_event_mutation()` function and `trg_audit_event_immutable` trigger on `projects_projectauditevent`
    - Include a `reverse_sql` that drops the trigger and function for rollback safety
    - _Requirements: 9.5_

  - [ ]* 2.4 Write property test for `has_cost_variance`
    - **Property 1: Variance is detected iff `cost_amount != original_cost_amount` OR `currency != original_currency` when `is_trf_expense=True` and `original_cost_amount` is not None**
    - **Validates: Requirements 7.5**

- [ ] 3. Implement permission helpers and role-based access
  - [x] 3.1 Implement `projects/permissions.py` with `PROJECT_MANAGER_ROLES`, `is_project_manager()`, `is_sales_user()`, and `require_project_manager` decorator
    - Decorator returns 403 if `user.userprofile.role` not in `PROJECT_MANAGER_ROLES`
    - `PROJECT_MANAGER_ROLES = {"PC", "PDR", "CDR", "Ops_Manager"}`
    - _Requirements: 3.5, 5.5, 6.6, 8.1_

  - [ ]* 3.2 Write unit tests for permission helpers
    - Test each role: Sales → denied, PC/PDR/CDR/Ops_Manager → allowed, Finance → denied for mutation
    - _Requirements: 3.5, 5.5, 6.6_

- [ ] 4. Implement `ProjectAuditService`
  - [x] 4.1 Implement `projects/services.py` — `ProjectAuditService.record()` as INSERT-only
    - Method signature: `record(project, actor, action, detail=None) -> ProjectAuditEvent`
    - Never calls `.save()` on an existing instance; always creates a new record
    - _Requirements: 9.1, 9.2, 9.5_

  - [ ]* 4.2 Write unit test for `ProjectAuditService.record()`
    - Assert a new `ProjectAuditEvent` row is created with correct fields on each call
    - _Requirements: 9.1, 9.2_

- [ ] 5. Implement `ProjectService`
  - [x] 5.1 Implement `ProjectService.create_from_trf()` in `projects/services.py`
    - Wrap entire operation in `transaction.atomic()`
    - Create `Project` from TRF fields (`name`, `sales_user`, `trf_approved_at`)
    - Iterate `trf.expenses.all()` to create `Milestone` records with `original_*` snapshot fields set once
    - Set `is_trf_expense=True` when `expense.amount` is non-null
    - Catch `IntegrityError` (duplicate) and all other exceptions; log with TRF id + timestamp; do NOT re-raise
    - Call `ProjectAuditService.record(... action=PROJECT_CREATED ...)`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 5.2 Write unit tests for `ProjectService.create_from_trf()`
    - Test: project created with correct fields; milestones created per expense; `is_trf_expense` set correctly; `original_*` fields populated; duplicate TRF does not raise; exception logged without re-raising
    - _Requirements: 1.1–1.6, 2.1–2.5_

  - [x] 5.3 Implement `ProjectService.transition_status()` in `projects/services.py`
    - Enforce transition table: Active→On_Hold/Completed/Cancelled, On_Hold→Active; all others raise `ProjectTransitionError`
    - For Active→Completed: return incomplete milestone list without transitioning if `confirmed` flag is False
    - Write audit event `STATUS_CHANGED` with `from_status`, `to_status`, `reason`
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 5.4 Write property test for project status transitions
    - **Property 2: Any transition not in the allowed transition table always raises `ProjectTransitionError`**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [ ]* 5.5 Write unit tests for `ProjectService.transition_status()`
    - Test each valid transition; test each invalid transition raises `ProjectTransitionError`; test completion warning returns incomplete milestones; test `confirmed=True` bypasses warning
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 6. Implement `MilestoneService`
  - [x] 6.1 Implement `MilestoneService.create()` in `projects/services.py`
    - Validate project is Active; validate name and target_date present; validate cost_amount + currency present when `is_trf_expense=True`
    - Set `status=Pending`, `created_by=user`, `created_at` (auto)
    - Call `ProjectAuditService.record(... action=MILESTONE_CREATED ...)`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 6.2 Implement `MilestoneService.update()` in `projects/services.py`
    - Validate project is Active; validate name and target_date present; validate cost/currency when `is_trf_expense=True`
    - Clear `cost_amount`/`currency` when `is_trf_expense` flipped to False
    - Explicitly exclude `original_*` fields from the update
    - Set `updated_by=user`, `updated_at` (auto)
    - Call `ProjectAuditService.record(... action=MILESTONE_UPDATED ...)`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

  - [x] 6.3 Implement `MilestoneService.delete()` in `projects/services.py`
    - Raise `MilestoneDeletionError` with specific messages for `In_Progress` and `Completed` statuses
    - `Pending` and `Cancelled` are deletable
    - Call `ProjectAuditService.record(... action=MILESTONE_DELETED ...)` before deletion
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [ ]* 6.4 Write property test for milestone status delete guard
    - **Property 3: `MilestoneService.delete()` raises `MilestoneDeletionError` for every status value that is not `Pending` or `Cancelled`**
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [ ]* 6.5 Write unit tests for `MilestoneService`
    - Test create validation (missing name, missing target_date, TRF_Expense without cost); test update clears cost on flag flip; test `original_*` fields unchanged after update; test delete guard for each status
    - _Requirements: 3.1–3.4, 5.1–5.6, 6.1–6.3, 6.5_

- [ ] 7. Checkpoint — ensure all tests pass
  - Run the test suite; confirm all service-layer and model tests pass. Ask the user if questions arise.

- [ ] 8. Connect the Django signal
  - [x] 8.1 Create `projects/signals.py` with `trf_fully_approved` receiver on `TRFRequest.post_save`
    - Check `instance.status == TRFRequest.Status.APPROVED` and `created == False`
    - Call `ProjectService.create_from_trf(instance)` — failure is already handled inside the service
    - _Requirements: 1.1, 1.5_

  - [x] 8.2 Wire the signal in `projects/apps.py` `ready()` method
    - Import `projects.signals` inside `ready()` to ensure the receiver is registered
    - _Requirements: 1.1_

  - [ ]* 8.3 Write integration test for the signal
    - Create a `TRFRequest` with expenses, transition status to `APPROVED`, assert `Project` and `Milestone` records exist
    - Assert duplicate signal does not create a second project
    - _Requirements: 1.1, 1.6_

- [x] 9. Implement Django forms
  - [x] 9.1 Create `projects/forms.py` with `MilestoneForm`
    - Fields: `name`, `target_date`, `description`, `status`, `is_trf_expense`, `cost_amount`, `currency`
    - `clean()` method: require `cost_amount` + `currency` when `is_trf_expense=True`
    - _Requirements: 3.1, 3.2, 3.3, 5.1, 5.2_

  - [x] 9.2 Add `ProjectStatusForm` to `projects/forms.py`
    - Fields: `new_status`, `reason` (optional text), `confirmed` (hidden BooleanField for two-step completion)
    - _Requirements: 8.1, 8.5_

- [x] 10. Implement views
  - [x] 10.1 Implement `project_list` view in `projects/views.py`
    - Filter queryset by role: Sales sees only projects where `sales_user == request.user`; Finance sees all (read-only); PC/PDR/CDR/Ops_Manager see all
    - _Requirements: 4.1, 4.4_

  - [x] 10.2 Implement `project_detail` view
    - Fetch project + prefetch milestones ordered by `target_date` + audit events
    - Compute `total_trf_approved`, `total_current`, `variance` for TRF Expense Summary table
    - Pass `is_project_manager` flag to template context
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 7.2, 7.4, 9.3_

  - [x] 10.3 Implement `project_status` view
    - `@require_project_manager` decorator
    - First POST (no `confirmed`): call `transition_status(confirmed=False)`; if incomplete milestones returned, render warning template with milestone list
    - Second POST (`confirmed=true`): call `transition_status(confirmed=True)`; redirect to `project_detail`
    - Catch `ProjectTransitionError` and render 400 with message
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 10.4 Implement `milestone_create` view
    - `@require_project_manager` decorator
    - GET: render blank `MilestoneForm`; POST: call `MilestoneService.create()`; redirect to `project_detail`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 10.5 Implement `milestone_edit` view
    - `@require_project_manager` decorator
    - GET: render `MilestoneForm` pre-populated (exclude `original_*` fields); POST: call `MilestoneService.update()`; redirect to `project_detail`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 10.6 Implement `milestone_delete` view
    - `@require_project_manager` decorator
    - GET: render confirmation page; POST: call `MilestoneService.delete()`; on `MilestoneDeletionError` render inline error; on success redirect to `project_detail`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 10.7 Implement `milestone_detail` view (read-only)
    - Login required; display all milestone fields including `original_*` snapshot values and variance indicator
    - _Requirements: 4.1, 4.3, 7.5_

- [-] 11. Implement templates
  - [x] 11.1 Create `projects/templates/projects/project_list.html`
    - Table of projects with name, status, TRF link, created date
    - _Requirements: 4.4_

  - [-] 11.2 Create `projects/templates/projects/project_detail.html`
    - Milestone table ordered by `target_date`; TRF Expense Summary section with totals and variance; audit trail section; project status form (for Project_Managers); TRF link
    - Use Alpine.js `x-show` to toggle the audit trail section
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 7.2, 7.3, 7.4, 9.3_

  - [ ] 11.3 Create `projects/templates/projects/project_status_confirm.html`
    - Warning page listing incomplete milestones; hidden `confirmed=true` field; submit button to proceed
    - _Requirements: 8.5_

  - [ ] 11.4 Create `projects/templates/projects/milestone_form.html`
    - Shared create/edit form; Alpine.js `x-show` to conditionally reveal `cost_amount`/`currency` fields when `is_trf_expense` is checked
    - _Requirements: 3.1, 3.3, 5.1, 5.2_

  - [ ] 11.5 Create `projects/templates/projects/milestone_confirm_delete.html`
    - Confirmation page with milestone name; POST button; inline error display area
    - _Requirements: 6.4_

  - [ ] 11.6 Create `projects/templates/projects/milestone_detail.html`
    - Read-only view of all milestone fields; show `original_*` snapshot values; display variance indicator badge when `has_cost_variance` is True
    - _Requirements: 4.1, 4.3, 7.5_

- [ ] 12. Add TRF detail page link to Project (Phase 1 integration)
  - [ ] 12.1 Update the Phase 1 `trf_detail` template to display the linked Project name and a link to `project_detail` when `trf.project` exists
    - Use `{% if trf.project %}` guard to avoid errors on unapproved TRFs
    - _Requirements: 7.3_

- [ ] 13. Checkpoint — ensure all tests pass
  - Run the full test suite including signal integration tests. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- `original_*` fields on `Milestone` are written once in `ProjectService.create_from_trf()` and never exposed in edit forms
- The PostgreSQL immutability trigger (task 2.3) must be applied before any audit events are written in tests
- Property tests use `hypothesis`; run with `pytest --hypothesis-seed=0` for reproducibility
- The two-step project completion POST (tasks 5.3 and 10.3) uses a `confirmed` boolean to avoid a separate confirmation URL
