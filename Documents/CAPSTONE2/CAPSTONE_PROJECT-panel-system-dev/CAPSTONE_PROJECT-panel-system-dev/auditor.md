╔══════════════════════════════════════════════════════════════════╗
║                    AUDITOR — MEMBERSHIP FEES                     ║
╚══════════════════════════════════════════════════════════════════╝

[] - Verify Membership Fee (Single)

The Auditor reviews a pending membership fee record submitted by the Treasurer. The system
displays the member details, fee amount, receipt number, and any uploaded proof. The Auditor
can either mark it as Verified (approves the fee) or Return for Revision (sends it back to
the Treasurer with remarks). An optional findings file can be attached as evidence. If
returned, a snapshot of the record is saved so the Treasurer can correct and resubmit.

Tables affected:

- MEMBERSHIP_FEE — status unchanged (only updated on release)
- TRANSACTION_VERIFICATION — status set to "Auditor Verified" or "Returned for Revision",
  auditor_id_FK, verified_at, remarks, return_count incremented
- FINANCIAL_DOCUMENT_ARCHIVE — auditor findings file stored (if uploaded)
- GLOBAL_AUDIT_TRAIL — action "VERIFIED" or "RETURNED" logged

Pipeline position:

- Treasurer creates fee → Auditor verifies (step 2 of 3) → President approves

[] - Verify Membership Fee (Batch)

The Auditor selects multiple pending membership fees and verifies or returns them all at
once in a single action. Same logic as single verification but processed in bulk with
atomic transactions.

Tables affected:

- Same as single verification, applied to multiple records
- TRANSACTION_VERIFICATION — batch-updated
- GLOBAL_AUDIT_TRAIL — one audit entry per record

╔══════════════════════════════════════════════════════════════════╗
║                    AUDITOR — MONTHLY DUES                        ║
╚══════════════════════════════════════════════════════════════════╝

[] - Verify Monthly Dues

The Auditor reviews a pending monthly dues record (OTC or Salary Deduction). The system
shows the member, month covered, amount, payment method, receipt or batch reference, and
supporting proof. The Auditor can Verify or Return for Revision with remarks. An optional
findings file can be attached.

Tables affected:

- MONTHLY_DUES — status unchanged
- TRANSACTION_VERIFICATION — status updated, auditor_id_FK, verified_at, remarks,
  return_count incremented on return
- FINANCIAL_DOCUMENT_ARCHIVE — auditor findings file (if uploaded)
- GLOBAL_AUDIT_TRAIL — "VERIFIED" or "RETURNED" logged

Pipeline position:

- Treasurer records dues → Auditor verifies (step 2 of 3) → President approves → FUND_TRANSACTION

╔══════════════════════════════════════════════════════════════════╗
║                     AUDITOR — AID & CLAIMS                       ║
╚══════════════════════════════════════════════════════════════════╝

[] - Verify Medical Aid Claim

The Auditor reviews a pending medical aid claim filed by the Treasurer. The system displays
the member, request date, hospital name and dates, hospital bill amount, validated aid
amount, and all uploaded proof documents (receipts, doctor's notes). The Auditor can Verify
or Return for Revision. On verification, the claim's status is updated to "Auditor
Verified". An optional findings file can be uploaded as evidence.

Tables affected:

- MEDICAL_AID — status set to "Auditor Verified" or "Returned for Revision",
  auditor_verified_by_user_id_FK set
- TRANSACTION_VERIFICATION — status updated, auditor_id_FK, verified_at, remarks
- FINANCIAL_DOCUMENT_ARCHIVE — auditor findings file (if uploaded)
- GLOBAL_AUDIT_TRAIL — "VERIFIED" or "RETURNED" logged

Pipeline position:

- Treasurer files claim → Auditor verifies (step 2 of 7) → President approves → Treasurer
  releases → Auditor verifies finish → President approves finish → Treasurer final release

---

[] - Verify Death Aid Claim

The Auditor reviews a pending death aid claim (member deceased or dependent deceased). The
system shows the member, deceased name, relationship, claimant info, benefit amount, funeral
details, and uploaded documents (death certificate, etc.). The Auditor can Verify or Return
for Revision. On verification, the claim status is updated to "Auditor Verified". An
optional findings file can be attached.

Tables affected:

- DEATH_AID — status set to "Auditor Verified" or "Returned for Revision",
  auditor_verified_by_user_id_FK set
- TRANSACTION_VERIFICATION — status updated, auditor_id_FK, verified_at, remarks
- FINANCIAL_DOCUMENT_ARCHIVE — auditor findings file (if uploaded)
- GLOBAL_AUDIT_TRAIL — "VERIFIED" or "RETURNED" logged

Pipeline position:

- Treasurer files claim → Auditor verifies (step 2 of 7) → President approves → Treasurer
  releases → Auditor verifies finish → President approves finish → Treasurer final release

---

[] - Verify Aid Tracking Post Finish

The Auditor reviews a finish request sent by the Treasurer for an aid tracking post
(medical or death aid contribution recovery). This occurs after the aid has been released
and the Treasurer has collected member contributions, uploaded a deduction sheet, and marked
the post as finished. The Auditor can:

- **Verified**: Marks recorded/pending contributions as PAID, creates FUND_TRANSACTION inflow
  records for each contribution, and forwards the post to the President for final approval.
- **Rejected**: Returns the post to the Treasurer with remarks for correction.

The system enforces that a deduction sheet must be uploaded (unless paid-with-funds) before
verification.

Tables affected:

- AID_TRACKING_POST — finish_status set to "pending_president" (verified) or "rejected"
- CONTRIBUTION — RECORDED/PENDING_VERIFICATION contributions set to PAID, updated_by_user_id_FK
- FUND_TRANSACTION — inflow records created per paid contribution
- TRANSACTION_VERIFICATION — contribution verification records updated
- GLOBAL_AUDIT_TRAIL — "FINISH_VERIFIED" or "FINISH_REJECTED" logged

Pipeline position:

- Treasurer files claim → Auditor verifies claim → President approves → Treasurer releases
  → Auditor verifies finish (step 5 of 7) → President approves finish → Treasurer final release

╔══════════════════════════════════════════════════════════════════╗
║               AUDITOR — VERIFIED REGISTRY                        ║
╚══════════════════════════════════════════════════════════════════╝

[] - View Audited Logs

The Auditor can view all finalized TransactionVerification records that have been
completed (excluding pending ones). Shows the table name, record ID, verification status,
auditor, timestamps, and linked member/amount details for historical reference.

Tables read:

- TRANSACTION_VERIFICATION — completed records
- MEMBER — linked member info
- MEMBERSHIP_FEE / MONTHLY_DUES / MEDICAL_AID / DEATH_AID — related records

╔══════════════════════════════════════════════════════════════════╗
║                     AUDITOR — FUND LEDGER                        ║
╚══════════════════════════════════════════════════════════════════╝

[] - View Full Fund Ledger

The Auditor can view the complete organization fund ledger showing all inflows and outflows
across membership fees, monthly dues, aid disbursements, and contributions.

Tables read:

- FUND_TRANSACTION — all transactions
- MEMBER — linked member info

[] - View Member Deductions

The Auditor can view per-member payroll deduction records showing amounts deducted for
membership fees, monthly dues, and aid contributions.

Tables read:

- PAYROLL_DEDUCTION — deduction records
- MEMBER — linked member info
- PAYROLL_BATCH — batch period info

╔══════════════════════════════════════════════════════════════════╗
║                 AUDITOR — REPORTS                                ║
╚══════════════════════════════════════════════════════════════════╝

[] - Generate Certifications

The Auditor can create audit reports summarizing findings, list all existing reports,
view report details, and submit fund reports to the President for review.

Tables affected:

- AUDIT_REPORT / ORGANIZATION_FUND_REPORT — report records created/submitted
- GLOBAL_AUDIT_TRAIL — report actions logged

╔══════════════════════════════════════════════════════════════════╗
║                   AUDITOR — FINANCE & COLLECTIONS                ║
╚══════════════════════════════════════════════════════════════════╝

[] - Finance & Collections

The Auditor can view finance and collections data. (Further details to be documented.)

---

> **Footnote — Sidebar visibility:**
> The following sidebar menu items are **commented out** in the Auditor dashboard and not
> accessible via navigation: Payroll Batches (under Verified Registry), Audit Chain Integrity,
> Tracking, History (the entire Aid Tracking folder is commented out).
> Their backend code and database tables remain active but lack a UI entry point.
