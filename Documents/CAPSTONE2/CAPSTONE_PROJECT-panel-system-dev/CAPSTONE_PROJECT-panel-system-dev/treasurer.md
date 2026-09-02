╔══════════════════════════════════════════════════════════════════╗
║ MEMBERSHIP ║
╚══════════════════════════════════════════════════════════════════╝

[] - Add Member Profile

The system saves the new member's details (name, ID, department, status, etc.) into the database. If the status is Permanent or Temporary, it automatically creates a Pending fee record and queues up a transaction verification task for the Auditor. It sends a welcome email to the new member (if an email address was provided) and records the entire process in the audit trail for security tracking.

---

Tables created:

- MEMBER — main profile
- MEMBERSHIP_FEE — only if Permanent/Temporary
- TRANSACTION_VERIFICATION — tracks Auditor/President approval pipeline
- GLOBAL_AUDIT_TRAIL — immutable audit log entry
- NOTIFICATION — welcome email record

Approval pipeline (for the auto-created fee):

- Treasurer creates the record
- Auditor verifies it (can return for revision)
- President approves it → fund is recorded in FUND_TRANSACTION

╔══════════════════════════════════════════════════════════════════╗
║ MONTHLY DUES ║
╚══════════════════════════════════════════════════════════════════╝

[] - Monthly Dues — Individual (OTC)

The Treasurer records an over-the-counter payment for a specific member and month. The system validates that the amount matches the policy rate (PHP 50), checks that the member hasn't already paid for that month, and ensures the member is not retired. A receipt reference and payment date are required, and a photo of the receipt can be uploaded as proof. The record is saved with a "Pending" verification status.

---

Tables created:

- MONTHLY_DUES — payment details (member, month, amount, method, receipt, date)
- TRANSACTION_VERIFICATION — status "Pending", awaits Auditor
- SUPPORTING_PROOF — uploaded receipt file (optional)
- GLOBAL_AUDIT_TRAIL — audit log entry

Approval pipeline:

- Treasurer records the payment
- Auditor verifies it (can return for revision)
- President approves it → recorded as fund inflow in FUND_TRANSACTION

---

[] - Monthly Dues — Individual (Salary Deduction)

The Treasurer records a single member's dues deducted directly from salary. Same validation as OTC (amount, duplicate month, member status), plus an accounting deduction summary and remittance reference number are required. The system assigns a deduction_batch_reference for tracking. Payment date is auto-set to the first of the covered month.

---

Tables created:

- MONTHLY_DUES — payment details (payment_method = "Salary Deduction", batch ref, remittance ref)
- TRANSACTION_VERIFICATION — status "Pending"
- SUPPORTING_PROOF — uploaded proof (optional)
- GLOBAL_AUDIT_TRAIL — audit log entry

Approval pipeline:

- Treasurer records the deduction
- Auditor verifies → President approves → fund inflow in FUND_TRANSACTION

---

[] - Monthly Dues — Bulk Salary Deduction

The Treasurer selects a month and the system previews all active (non-retired) members, flagging who already has a salary deduction for that month. Members not yet processed are checked by default. The Treasurer picks which members to include and submits. The system auto-generates a batch reference number (format: ISU-CAUFA-YY-N) and creates individual MONTHLY_DUES records with a matching remittance_reference for all selected members in a single transaction. Duplicate processing is prevented via row locking.

---

Tables created:

- MONTHLY_DUES — one row per member, all sharing the same remittance_reference (batch ref)
- TRANSACTION_VERIFICATION — one per member, status "Pending"
- SUPPORTING_PROOF — single uploaded file linked to all records (optional)
- GLOBAL_AUDIT_TRAIL — one audit entry per member

Approval pipeline:

- Same as individual: Treasurer → Auditor → President → FUND_TRANSACTION
- Each member's record goes through verification individually

╔══════════════════════════════════════════════════════════════════╗
║ MEDICAL AID ║
╚══════════════════════════════════════════════════════════════════╝

[] - Medical Aid — Individual

The Treasurer files a medical aid claim for a member. The system validates that the member hasn't already claimed this year (once-per-year rule), is in good standing, and that the hospital bill exceeds the minimum threshold (PHP 500). The aid amount is auto-calculated based on policy (up to PHP 20,000). Multiple proof files (receipts, doctor's notes) can be uploaded. The claim is saved with a "Pending" status across all tracking fields.

---

Tables created:

- MEDICAL_AID — claim details (member, dates, hospital, bill amount, validated amount, status)
- TRANSACTION_VERIFICATION — status "Pending", awaits Auditor
- SUPPORTING_PROOF — uploaded medical documents (multi-file)
- GLOBAL_AUDIT_TRAIL — audit log entry

Approval pipeline (7-step):

- Treasurer files the claim
- Auditor verifies the documents and claim validity
- President approves the claim → creates AID_TRACKING_POST + CONTRIBUTION records for all non-retired members
- Treasurer releases the aid → TRANSACTION_ARCHIVE + FUND_TRANSACTION (outflow)
- Auditor verifies the tracking post finish (contribution collection and deduction sheet)
- President approves the finish
- Treasurer does final release → post closed, fund transactions finalized

---

[] - Medical Aid — Batch (up to 5 members)

The Treasurer selects multiple members (max 5) in a single form and fills in each member's claim details (request date, reason, hospital, bill amount). Each entry is validated individually against the same rules (once-per-year, good standing, bill threshold). Each member gets their own MEDICAL_AID record and verification entry. Proof files can be attached per member per card.

---

Tables created per member:

- MEDICAL_AID — one row per member
- TRANSACTION_VERIFICATION — one per member, status "Pending"
- SUPPORTING_PROOF — files per member
- GLOBAL_AUDIT_TRAIL — one audit entry per member

Approval pipeline:

- Treasurer files the batch → each claim goes individually through Auditor → President → Treasurer release → Auditor → President → Treasurer final release
- Each claim is tracked and approved independently through the full 7-step pipeline

╔══════════════════════════════════════════════════════════════════╗
║ DEATH AID ║
╚══════════════════════════════════════════════════════════════════╝

[] - Death Aid — Member Deceased

The Treasurer files a death aid claim when the member themselves has passed away. The deceased name matches the member's name. The system checks that the member is in good standing and is not retired (retired members are exempt). The benefit amount is looked up from policy by relationship (member = PHP 500). Claimant info is required (who is claiming on behalf of the estate); if the claimant already exists, their record is reused. Supporting documents (death certificate, etc.) can be uploaded.

---

Tables created:

- CLAIMANT — claimant info (name, contact, relationship) — created if new, reused if existing
- DEATH_AID — member, claimant, deceased name, relationship, benefit amount, funeral details, status
- TRANSACTION_VERIFICATION — status "Pending", awaits Auditor
- SUPPORTING_PROOF — uploaded documents (multi-file)
- GLOBAL_AUDIT_TRAIL — audit log entry

Approval pipeline (7-step):

- Treasurer files the claim
- Auditor verifies the documents and claim validity
- President approves the claim → creates AID_TRACKING_POST + CONTRIBUTION records for all non-retired members
- Treasurer releases the aid → TRANSACTION_ARCHIVE + FUND_TRANSACTION (outflow)
- Auditor verifies the tracking post finish (contribution collection and deduction sheet)
- President approves the finish
- Treasurer does final release → post closed, fund transactions finalized

---

[] - Death Aid — Dependent Deceased

The Treasurer files a death aid claim when a dependent (spouse, parent, child, sibling) of the member has passed away. The claim is filed under the member's account and the deceased name is the dependent's name, not the member's. The benefit amount is calculated based on the dependent's relationship tier. Same validations apply: good standing check and retired exemption. Claimant info is required and existing claimants are reused. Supporting documents can be uploaded.

---

Benefit tiers:

- Member (self): PHP 500
- Spouse: PHP 300
- Parent / Child: PHP 250
- Full-blood sibling: PHP 100

Tables created:

- CLAIMANT — claimant info (created if new, reused if existing)
- DEATH_AID — member, claimant, deceased name (dependent), relationship, relationship group ("immediate" or "extended"), benefit amount, funeral location, interment date, status
- TRANSACTION_VERIFICATION — status "Pending"
- SUPPORTING_PROOF — uploaded documents
- GLOBAL_AUDIT_TRAIL — audit log entry

Approval pipeline (7-step):

- Treasurer files the claim
- Auditor verifies the documents and claim validity
- President approves the claim → creates AID_TRACKING_POST + CONTRIBUTION records
- Treasurer releases the aid → TRANSACTION_ARCHIVE + FUND_TRANSACTION (outflow)
- Auditor verifies the tracking post finish
- President approves the finish
- Treasurer does final release → post closed

---

> **Footnote — Sidebar visibility:**
> The following sidebar menu items are **commented out** in the Treasurer dashboard and not
> accessible via navigation: Payroll Batches, Returned Entries (Membership),
> Membership Fee Payment, Returned Entries (Monthly Dues), Returned Medical Aid,
> Returned Death Aid, Aid Collection / Tracking, Aid Tracking History.
> Their backend code and database tables remain active but lack a UI entry point.
