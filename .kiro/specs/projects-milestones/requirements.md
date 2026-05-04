# Requirements Document

## Introduction

The Projects and Milestones feature is Phase 2 of the ATA Workflow Manager. When a TRF is fully approved, the system automatically creates a Project that tracks the delivery of the approved training engagement. Each Project contains Milestones derived from the TRF's Costing Sheet. Project managers and Operations staff can add, edit, and remove milestones over the project lifecycle. Milestones may be flagged as TRF Expenses, creating a traceable link back to the originating TRF cost items.

## Glossary

- **TRF**: Training Request Form — the Phase 1 document that, once fully approved, triggers Project creation.
- **Project**: A delivery record automatically created when a TRF reaches Approved status. Represents the active training engagement.
- **Milestone**: A named, dated deliverable or checkpoint within a Project. Sourced initially from the TRF Costing Sheet but editable after creation.
- **Costing_Sheet**: The itemised expense and milestone section of a TRF, containing milestone names, target dates, and cost line items.
- **TRF_Expense**: A flag on a Milestone indicating that it corresponds to a cost line item on the originating TRF's Costing Sheet.
- **Project_Manager**: A user (Operations or Finance role) responsible for managing a Project and its Milestones after TRF approval.
- **Sales_User**: A member of the Sales team who created the originating TRF. Has read-only access to the resulting Project.
- **Project_Status**: The current state of a Project — one of: Active, On_Hold, Completed, Cancelled.
- **Milestone_Status**: The current state of a Milestone — one of: Pending, In_Progress, Completed, Cancelled.
- **Project_System**: The Projects and Milestones subsystem of the ATA Workflow Manager.

---

## Preconditions (from Phase 1)

- TRF status `FullyApproved` triggers Project creation
- Roles existing: PC (Project Coordinator), PDR (Procurement), CDR (Costing), Ops_Manager
- Costing_Sheet has: `milestone_name`, `target_date`, `cost_amount`, `currency`, `line_item_id`

---

## Requirements

### Requirement 1: Automatic Project Creation on TRF Approval

**User Story:** As an Operations_Team member, I want a Project to be automatically created when a TRF is fully approved, so that delivery tracking begins immediately without manual data entry.

#### Acceptance Criteria

1. WHEN a TRF status transitions to Approved, THE Project_System SHALL automatically create a Project record linked to that TRF.
2. WHEN a Project is created from an approved TRF, THE Project_System SHALL populate the Project with: the TRF project name, the originating Sales_User, the TRF approval timestamp as the project start reference, and a link to the source TRF record.
3. WHEN a Project is created from an approved TRF, THE Project_System SHALL set the Project status to Active.
4. WHEN a Project is created from an approved TRF, THE Project_System SHALL create one Milestone for each milestone entry in the TRF's Costing_Sheet, preserving the milestone name and target date.
5. IF the Project creation process fails after a TRF is approved, THEN THE Project_System SHALL log the failure with the TRF identifier and timestamp, and SHALL NOT block or reverse the TRF Approved status.
6. THE Project_System SHALL ensure that exactly one Project exists per approved TRF — duplicate Project creation for the same TRF SHALL be prevented.

---

### Requirement 2: Milestone Initialisation from Costing Sheet

**User Story:** As a Project_Manager, I want milestones pre-populated from the TRF Costing Sheet when a project is created, so that I have a baseline delivery plan without re-entering data.

#### Acceptance Criteria

1. WHEN a Project is created, THE Project_System SHALL create a Milestone record for each line item in the TRF Costing_Sheet that has a milestone name and target date.
2. WHEN a Milestone is created from a Costing_Sheet line item that includes a cost amount, THE Project_System SHALL set the Milestone's TRF_Expense flag to true and store the linked cost amount and currency from the Costing_Sheet.
3. WHEN a Milestone is created from a Costing_Sheet line item that does not include a cost amount, THE Project_System SHALL set the Milestone's TRF_Expense flag to false.
4. THE Project_System SHALL set the initial Milestone_Status of every auto-created Milestone to Pending.
5. THE Project_System SHALL preserve the original Costing_Sheet values on each Milestone as read-only reference data, separate from the editable milestone fields.

---

### Requirement 3: Milestone Create

**User Story:** As a Project_Manager, I want to add new milestones to a project, so that I can capture deliverables that were not in the original Costing Sheet.

#### Acceptance Criteria

1. WHILE a Project has status Active, THE Project_System SHALL allow a Project_Manager to add a new Milestone with: name (required), target date (required), description (optional), and TRF_Expense flag (required, defaults to false).
2. IF a Project_Manager submits a new Milestone with the name or target date missing, THEN THE Project_System SHALL reject the submission and display a field-level validation error for each missing field.
3. WHEN a Project_Manager adds a Milestone with TRF_Expense set to true, THE Project_System SHALL require the Project_Manager to enter a cost amount and currency before the Milestone is saved.
4. WHEN a new Milestone is saved, THE Project_System SHALL set its Milestone_Status to Pending and record the creating user and creation timestamp.
5. THE Project_System SHALL prevent a Sales_User from creating Milestones on any Project.

---

### Requirement 4: Milestone Read

**User Story:** As a Project_Manager or Sales_User, I want to view all milestones for a project, so that I can track delivery progress at a glance.

#### Acceptance Criteria

1. WHEN a user navigates to a Project detail page, THE Project_System SHALL display all Milestones for that Project, including: name, target date, Milestone_Status, TRF_Expense flag, and cost amount (if applicable).
2. THE Project_System SHALL display Milestones ordered by target date ascending by default.
3. WHEN a Milestone has TRF_Expense set to true, THE Project_System SHALL display a visible indicator linking back to the source TRF Costing_Sheet line item.
4. THE Project_System SHALL display the Project's source TRF name and a navigable link to the TRF detail page on the Project detail page.

---

### Requirement 5: Milestone Update

**User Story:** As a Project_Manager, I want to edit existing milestones, so that I can keep delivery details accurate as the project evolves.

#### Acceptance Criteria

1. WHILE a Project has status Active, THE Project_System SHALL allow a Project_Manager to edit any Milestone's name, target date, description, Milestone_Status, TRF_Expense flag, cost amount, and currency.
2. WHEN a Project_Manager changes a Milestone's TRF_Expense flag from false to true, THE Project_System SHALL require a cost amount and currency to be provided before saving.
3. WHEN a Project_Manager changes a Milestone's TRF_Expense flag from true to false, THE Project_System SHALL clear the stored cost amount and currency from that Milestone.
4. WHEN a Milestone is updated, THE Project_System SHALL record the updating user and update timestamp.
5. THE Project_System SHALL prevent a Sales_User from editing any Milestone.
6. THE Project_System SHALL preserve the original Costing_Sheet reference values on auto-created Milestones regardless of subsequent edits to the editable fields.

---

### Requirement 6: Milestone Delete

**User Story:** As a Project_Manager, I want to remove milestones that are no longer relevant, so that the project plan stays accurate and uncluttered.

#### Acceptance Criteria

1. WHILE a Project has status Active, THE Project_System SHALL allow a Project_Manager to delete any Milestone that has Milestone_Status of Pending.
2. IF a Project_Manager attempts to delete a Milestone with Milestone_Status of In_Progress, THEN THE Project_System SHALL reject the deletion and display an error message instructing the user to change the Milestone_Status to Pending before deleting.
3. IF a Project_Manager attempts to delete a Milestone with Milestone_Status of Completed, THEN THE Project_System SHALL reject the deletion and display an error message stating that completed milestones cannot be deleted.
4. WHEN a Project_Manager deletes a Milestone, THE Project_System SHALL require confirmation before the deletion is executed.
5. WHEN a Milestone is deleted, THE Project_System SHALL record the deleting user and deletion timestamp in the Project audit trail.
6. THE Project_System SHALL prevent a Sales_User from deleting any Milestone.

---

### Requirement 7: TRF Expense Linkage

**User Story:** As a Finance_Team member, I want to see which project milestones are linked to TRF cost items, so that I can reconcile approved expenses against actual delivery milestones.

#### Acceptance Criteria

1. THE Project_System SHALL maintain a traceable link between each TRF_Expense Milestone and its originating TRF Costing_Sheet line item.
2. WHEN a Finance_Team member views a Project, THE Project_System SHALL display a summary of all TRF_Expense Milestones showing: milestone name, target date, cost amount, currency, and Milestone_Status.
3. WHEN a Finance_Team member views a TRF detail page, THE Project_System SHALL display the linked Project name and a navigable link to the Project detail page.
4. THE Project_System SHALL calculate and display the total approved TRF expense value alongside the sum of all TRF_Expense Milestone cost amounts on the Project detail page, so that Finance_Team members can identify any variance.
5. IF a TRF_Expense Milestone's cost amount differs from the linked Costing_Sheet line item amount, THEN THE Project_System SHALL display a visual variance indicator on that Milestone.

---

### Requirement 8: Project Status Management

**User Story:** As a Project_Manager, I want to update the status of a project, so that stakeholders know whether the project is active, on hold, completed, or cancelled.

#### Acceptance Criteria

1. THE Project_System SHALL allow a Project_Manager to transition a Project status from Active to On_Hold, Completed, or Cancelled.
2. THE Project_System SHALL allow a Project_Manager to transition a Project status from On_Hold back to Active.
3. WHILE a Project has status Completed or Cancelled, THE Project_System SHALL prevent any Project_Manager from adding, editing, or deleting Milestones on that Project.
4. WHEN a Project status is updated, THE Project_System SHALL record the updating user and update timestamp.
5. IF a Project_Manager attempts to mark a Project as Completed while one or more Milestones have Milestone_Status of Pending or In_Progress, THEN THE Project_System SHALL display a warning listing the incomplete Milestones and require explicit confirmation before completing the Project.

---

### Requirement 9: Project Audit Trail

**User Story:** As a manager or Finance_Team member, I want a complete audit trail for every project and its milestones, so that I can review the history of changes and ensure accountability.

#### Acceptance Criteria

1. THE Project_System SHALL record every Project status transition, including the actor, action, timestamp, and any associated reason.
2. THE Project_System SHALL record every Milestone creation, update, and deletion, including the actor, action, changed fields, and timestamp.
3. WHEN a user views a Project detail page, THE Project_System SHALL display the full Project audit trail in chronological order.
4. THE Project_System SHALL retain Project and Milestone audit trail records for a minimum of 7 years.
5. THE Project_System SHALL prevent any user from modifying or deleting an audit trail record after it has been created.
