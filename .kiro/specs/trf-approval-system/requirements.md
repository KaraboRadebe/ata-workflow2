# Requirements Document

## Introduction

The TRF (Training Request Form) Approval System is an internal workflow tool for ATA International. When a Sales team member qualifies a lead, they create a TRF that must pass through two levels of management approval before Finance and Operations are notified to act. The system must reduce approval cycle time from days to hours by providing a structured, trackable, and auditable approval workflow with remediation support for rejected forms.

## Glossary

- **TRF**: Training Request Form — the primary document capturing project details, training dates, milestones, and expenses for a qualified lead.
- **Sales_User**: A member of the Sales team who creates and submits TRFs.
- **Level_2_Approver**: One of three named approvers (Aidan, Trevor, or Tasneem) responsible for the second-level review of a TRF.
- **Level_3_Approver**: One of three named approvers (Sharona, Melisa, or Andre) responsible for the third-level review of a TRF.
- **Finance_Team**: The Finance department notified by email upon full TRF approval.
- **Operations_Team**: The Operations department notified by email and Slack upon full TRF approval.
- **Approval_Workflow**: The sequential two-level approval process a TRF must complete before being considered fully approved.
- **Remediation**: The process by which a Sales_User revises and resubmits a rejected TRF.
- **Delegate**: A named approver who temporarily covers for an unavailable approver at the same level.
- **TRF_Status**: The current state of a TRF — one of: Draft, Pending_L2, Pending_L3, Approved, Rejected, Remediation.

---

## Requirements

### Requirement 1: TRF Creation

**User Story:** As a Sales_User, I want to create a TRF when a lead is qualified, so that I can formally request training resources and initiate the approval process.

#### Acceptance Criteria

1. THE TRF_System SHALL provide a form that captures: project name, training start date, milestones (list of name + target date pairs), and itemised expenses (description, amount, currency).
2. WHEN a Sales_User submits a TRF with all required fields populated, THE TRF_System SHALL save the TRF with status Pending_L2 and record the submitting user and submission timestamp.
3. IF a Sales_User submits a TRF with one or more required fields missing, THEN THE TRF_System SHALL reject the submission and display a field-level validation error for each missing field.
4. WHEN a TRF is saved with status Pending_L2, THE TRF_System SHALL send an in-app notification to all available Level_2_Approvers.

---

### Requirement 2: Level 2 Approval

**User Story:** As a Level_2_Approver, I want to review and approve or reject a TRF, so that only qualified training requests advance to senior management.

#### Acceptance Criteria

1. WHILE a TRF has status Pending_L2, THE TRF_System SHALL display the TRF in the Level_2_Approver's review queue.
2. WHEN a Level_2_Approver approves a TRF, THE TRF_System SHALL update the TRF status to Pending_L3, record the approver's name and approval timestamp, and send an in-app notification to all available Level_3_Approvers.
3. WHEN a Level_2_Approver rejects a TRF, THE TRF_System SHALL require the approver to provide a rejection reason before the rejection is recorded.
4. WHEN a Level_2_Approver rejects a TRF with a reason provided, THE TRF_System SHALL update the TRF status to Rejected, record the approver's name, rejection reason, and rejection timestamp, and notify the originating Sales_User by in-app notification.
5. THE TRF_System SHALL prevent any user who is not a Level_2_Approver from approving or rejecting a TRF at the Level 2 stage.

---

### Requirement 3: Level 3 Approval

**User Story:** As a Level_3_Approver, I want to review and approve or reject a TRF that has passed Level 2, so that senior management has final authority over training commitments.

#### Acceptance Criteria

1. WHILE a TRF has status Pending_L3, THE TRF_System SHALL display the TRF in the Level_3_Approver's review queue.
2. WHEN a Level_3_Approver approves a TRF, THE TRF_System SHALL update the TRF status to Approved, record the approver's name and approval timestamp, and trigger the post-approval notification workflow.
3. WHEN a Level_3_Approver rejects a TRF, THE TRF_System SHALL require the approver to provide a rejection reason before the rejection is recorded.
4. WHEN a Level_3_Approver rejects a TRF with a reason provided, THE TRF_System SHALL update the TRF status to Rejected, record the approver's name, rejection reason, and rejection timestamp, and notify the originating Sales_User by in-app notification.
5. THE TRF_System SHALL prevent any user who is not a Level_3_Approver from approving or rejecting a TRF at the Level 3 stage.
6. THE TRF_System SHALL prevent a Level_2_Approver from also acting as the Level_3_Approver on the same TRF.

---

### Requirement 4: Post-Approval Notifications

**User Story:** As a Finance_Team member and Operations_Team member, I want to be notified when a TRF is fully approved, so that I can take the necessary financial and operational actions without delay.

#### Acceptance Criteria

1. WHEN a TRF status transitions to Approved, THE TRF_System SHALL send an email to the Finance_Team containing the TRF project name, training start date, milestones, and total expenses.
2. WHEN a TRF status transitions to Approved, THE TRF_System SHALL send an email to the Operations_Team containing the TRF project name, training start date, and milestones.
3. WHEN a TRF status transitions to Approved, THE TRF_System SHALL send a Slack message to the Operations_Team channel containing the TRF project name and a link to the TRF detail page.
4. IF the Slack notification fails to deliver, THEN THE TRF_System SHALL log the failure with the TRF identifier and timestamp, and SHALL NOT block the approval status update.
5. IF the Finance_Team email fails to deliver, THEN THE TRF_System SHALL log the failure with the TRF identifier and timestamp, and SHALL NOT block the approval status update.

---

### Requirement 5: TRF Remediation

**User Story:** As a Sales_User, I want to revise and resubmit a rejected TRF, so that I can address the approver's concerns and continue the approval process.

#### Acceptance Criteria

1. WHILE a TRF has status Rejected, THE TRF_System SHALL display a "Remediate TRF" action to the originating Sales_User.
2. WHEN a Sales_User initiates remediation, THE TRF_System SHALL display the rejection reason alongside the editable TRF form.
3. WHEN a Sales_User submits a remediated TRF with all required fields populated, THE TRF_System SHALL update the TRF status to Pending_L2, record the remediation timestamp, and restart the Approval_Workflow from Level 2.
4. THE TRF_System SHALL preserve the full history of all previous approval and rejection events on a remediated TRF.
5. THE TRF_System SHALL prevent a Sales_User from submitting a remediated TRF without modifying at least one field from the previously rejected version.

---

### Requirement 6: Approver Unavailability

**User Story:** As a Level_2_Approver or Level_3_Approver, I want to mark myself as unavailable and designate a delegate, so that TRF approvals are not blocked when I am absent.

#### Acceptance Criteria

1. WHEN a Level_2_Approver or Level_3_Approver marks themselves as unavailable, THE TRF_System SHALL allow them to designate one of the other named approvers at the same level as their delegate.
2. WHILE an approver is marked unavailable, THE TRF_System SHALL route TRF notifications to the designated delegate instead of the unavailable approver.
3. WHILE an approver is marked unavailable, THE TRF_System SHALL display the unavailable approver's queue to their designated delegate.
4. IF all Level_2_Approvers are simultaneously marked unavailable, THEN THE TRF_System SHALL notify a Level_3_Approver that no Level_2_Approver is available and SHALL NOT allow the TRF to advance without a Level_2_Approval action.
5. IF all Level_3_Approvers are simultaneously marked unavailable, THEN THE TRF_System SHALL notify the system administrator that no Level_3_Approver is available.
6. WHEN an approver marks themselves as available again, THE TRF_System SHALL restore their standard notification routing and remove delegate access to their queue.

---

### Requirement 7: TRF Audit Trail

**User Story:** As a manager or Finance_Team member, I want a complete audit trail for every TRF, so that I can review the history of decisions and ensure accountability.

#### Acceptance Criteria

1. THE TRF_System SHALL record every status transition for a TRF, including the actor, action, timestamp, and any associated reason.
2. WHEN a user views a TRF detail page, THE TRF_System SHALL display the full audit trail in chronological order.
3. THE TRF_System SHALL retain audit trail records for a minimum of 7 years.
4. THE TRF_System SHALL prevent any user from modifying or deleting an audit trail record after it has been created.
