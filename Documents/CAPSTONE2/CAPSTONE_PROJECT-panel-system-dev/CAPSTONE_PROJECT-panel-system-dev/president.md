╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — PAYMENTS VERIFICATION ║
╚══════════════════════════════════════════════════════════════════╝

[] - Approve / Reject Membership Fee

The President reviews membership fees that have already been verified by the Auditor. The
system shows the member details, fee amount, receipt, the Treasurer's original entry, and
the Auditor's verification summary (name, date, evidence, remarks). The President can
Approve (which creates a FUND_TRANSACTION inflow record and archives the transaction) or
Reject (which returns the fee to the Treasurer for revision).

Tables affected:

- TRANSACTION_VERIFICATION — status set to "Approved" or "Rejected", president_id_FK,
  approved_at
- FUND_TRANSACTION — inflow record created (on approve)
- TRANSACTION_ARCHIVE — archived record created (on approve)
- GLOBAL_AUDIT_TRAIL — "APPROVED" or "REJECTED" logged

Pipeline position:

- Treasurer creates fee → Auditor verifies → President approves (step 3 of 3) → done

[] - Approve / Reject Monthly Dues

The President reviews monthly dues (OTC or Salary Deduction) that have been verified by the
Auditor. Same flow as membership fee — shows member, month, amount, method, Treasurer's
entry, Auditor's findings. Approve creates fund inflow + archive. Reject returns for
revision.

Tables affected:

- Same as membership fee approval, applied to MONTHLY_DUES
- FUND_TRANSACTION — inflow recorded
- TRANSACTION_ARCHIVE — archived record

Pipeline position:

- Treasurer records dues → Auditor verifies → President approves (step 3 of 3) → done

[] - Batch Approve / Reject

The President can approve or reject multiple payments (fees and/or dues) at once in a
single action. Each record is processed individually with its own audit trail entry.

Tables affected:

- Same as single approval, applied to multiple records

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — AID & CLAIMS ║
╚══════════════════════════════════════════════════════════════════╝

[] - Approve / Reject Medical Aid Claim

The President reviews medical aid claims that have been verified by the Auditor. The system
shows the member, hospital details, bill amount, validated aid amount, and the Auditor's
verification. On approval, the President sets the approved amount, which triggers creation
of an AID_TRACKING_POST and per-member CONTRIBUTION records for all non-retired members.
An email notification is sent to members about the aid distribution.

Tables affected:

- MEDICAL_AID — status set to "Approved" or "Rejected", president_decided_by_user_id_FK,
  president_decision
- TRANSACTION_VERIFICATION — status updated, president_id_FK, approved_at
- AID_TRACKING_POST — created (on approve) with total_expected = approved amount
- CONTRIBUTION — one record per active non-retired member (on approve)
- GLOBAL_AUDIT_TRAIL — "APPROVED" or "REJECTED" logged

Pipeline position:

- Treasurer files claim → Auditor verifies → President approves (step 3 of 7) →
  AID_TRACKING_POST created → Treasurer releases → Auditor verifies finish →
  President approves finish → Treasurer final release

[] - Approve / Reject Death Aid Claim

The President reviews death aid claims (member deceased or dependent deceased) that have
been verified by the Auditor. Same flow as medical aid — on approval, creates tracking post
and contribution records for all non-retired members.

Tables affected:

- DEATH_AID — status set, president_decided_by_user_id_FK, president_decision
- TRANSACTION_VERIFICATION — status updated
- AID_TRACKING_POST — created (on approve)
- CONTRIBUTION — one per active non-retired member
- GLOBAL_AUDIT_TRAIL — logged

Pipeline position:

- Same 7-step pipeline as medical aid

[] - Batch Approve / Reject Aid Claims

The President can approve or reject multiple aid claims (medical and/or death) at once.

Tables affected:

- Same as single approval, applied to multiple records

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — CONTRIBUTIONS & RELEASES ║
╚══════════════════════════════════════════════════════════════════╝

[] - Approve / Reject Contribution

The President reviews individual contribution records that have been recorded by the
Treasurer or Auditor for an aid tracking post. On approval, a FUND_TRANSACTION inflow is
created for the contribution amount.

Tables affected:

- CONTRIBUTION — status updated to "PAID" or "Returned"
- FUND_TRANSACTION — inflow record created (on approve)
- GLOBAL_AUDIT_TRAIL — logged

Pipeline position:

- Treasurer records contribution → President approves → fund inflow recorded

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — FINISH APPROVALS ║
╚══════════════════════════════════════════════════════════════════╝

[] - Approve / Reject Aid Post Finish

The President reviews aid tracking post finish requests that have been forwarded by the
Auditor (or directly by the Treasurer). The system shows the contribution breakdown per
member (expected vs paid), deduction sheet reference, and collection rate.

On approval, the President handles two scenarios:

- **First cycle (pending release)**: Sets finish_status to "pending_release" — the
  Treasurer then does the final release which records fund in/out and closes the post.
- **Second cycle (repayment close)**: For paid-with-funds posts where members have
  completed repayments, the President's approval closes the post permanently.

Tables affected:

- AID_TRACKING_POST — finish_status set to "pending_release" or "approved"
- CONTRIBUTION — remaining NOT_PAID records skipped (if skip_remaining was set)
- GLOBAL_AUDIT_TRAIL — "FINISH_APPROVED" or "REPAYMENT_APPROVED" logged

Pipeline position:

- Treasurer releases aid → Auditor verifies finish → President approves finish
  (step 6 of 7) → Treasurer final release → post closed

[] - Reject Aid Post Finish

The President can reject a finish request, which returns the post to active tracking
status for the Treasurer to correct.

Tables affected:

- AID_TRACKING_POST — finish_status set to "rejected"
- GLOBAL_AUDIT_TRAIL — "FINISH_REJECTED" logged

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — FUND LEDGER ║
╚══════════════════════════════════════════════════════════════════╝

[] - View Full Fund Ledger

The President can view the complete organization fund ledger showing all inflows and
outflows across membership fees, monthly dues, aid disbursements, and contributions.

Tables read:

- FUND_TRANSACTION — all transactions
- MEMBER — linked member info

[] - View Member Deductions

The President can view per-member payroll deduction records.

Tables read:

- PAYROLL_DEDUCTION — deduction records
- MEMBER — linked member info
- PAYROLL_BATCH — batch period info

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — DISBURSEMENT LOGS ║
╚══════════════════════════════════════════════════════════════════╝

[] - View Executive Ledger

The President can view historical disbursement logs — records of all completed
transactions that have gone through the full approval pipeline.

Tables read:

- TRANSACTION_ARCHIVE — completed/released records
- GLOBAL_AUDIT_TRAIL — audit history

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — OVERSIGHT REPORTS ║
╚══════════════════════════════════════════════════════════════════╝

[] - Generate Oversight Summary

The President can generate and view executive oversight reports, review auditor-submitted
reports (approve or request revision), and approve/reject organization fund reports.

Tables affected:

- AUDIT_REPORT — status updated (approve/reject/revision)
- ORGANIZATION_FUND_REPORT — status updated (approve/reject)
- GLOBAL_AUDIT_TRAIL — report actions logged

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — BYLAWS CONSTANTS ║
╚══════════════════════════════════════════════════════════════════╝

[] - Manage Policy Constants

The President can view and update policy constants (membership fee amount, monthly dues
amount, aid thresholds and benefits, death aid amounts by relationship). Changes are saved
as SystemSetting overrides and logged in the audit trail.

Tables affected:

- SYSTEM_SETTING — setting_key / setting_value updated
- GLOBAL_AUDIT_TRAIL — policy change logged

[] - Manage Bylaws Documents

The President can upload, list, and delete bylaws documents (PDF/DOC/DOCX/TXT, max 10MB).

Tables affected:

- BYLAWSFILE — document records created or deleted
- GLOBAL_AUDIT_TRAIL — document actions logged

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — ADMINISTRATION ║
╚══════════════════════════════════════════════════════════════════╝

[] - Manage Officer Accounts

The President can create, update, deactivate, and reset passwords for officer accounts
(Treasurer, Auditor, President). Each action is logged.

Tables affected:

- OFFICER_USER — account records created/updated/deactivated
- GLOBAL_AUDIT_TRAIL — account actions logged

[] - Self-Enrollment

The President can enroll themselves as a member of the association. Creates a member
profile, auto-creates a pending membership fee, and sends a welcome notification.

Tables affected:

- MEMBER — profile created
- MEMBERSHIP_FEE — auto-created (if Permanent/Temporary)
- TRANSACTION_VERIFICATION — pending record created
- NOTIFICATION — welcome notification
- GLOBAL_AUDIT_TRAIL — enrollment logged

[] - Backup Management

The President can view backup history, trigger manual backups (database dump + media
archive), and restore from a previous backup by job ID.

Tables affected:

- BACKUPJOB — backup records created/listed
- (Database dump and media files on disk)

╔══════════════════════════════════════════════════════════════════╗
║ PRESIDENT — FINANCE & COLLECTIONS ║
╚══════════════════════════════════════════════════════════════════╝

[] - Finance & Collections

The President can view finance and collections data. (Further details to be documented.)

---

> **Footnote — Sidebar visibility:**
> The following sidebar menu items are **commented out** in the President dashboard and not
> accessible via navigation: Approve Payroll Batches.
> Its backend code and database tables remain active but lack a UI entry point.
