╔══════════════════════════════════════════════════════════════════╗
║              MEMBER — HOME / DASHBOARD                           ║
╚══════════════════════════════════════════════════════════════════╝

[] - Dashboard Home

The Member lands on a mobile-optimized dashboard showing a hero card with a
welcome greeting, avatar, name, membership-status badge, and a stats strip
(Events Attended, Dues Balance, Member Since). Below is a Quick Access grid
(Attendance, Dues/Finance, Profile), a Membership Overview card with fee
status and a "View Finance" button, an Upcoming Activities panel, and a
Latest Notices panel. A bottom navigation bar provides one‑tap switching
between Home, Attendance, Finance, and Profile.

Tables read:

- MEMBER — profile info (name, avatar, status, joined date)
- MEMBERSHIP_FEE — latest fee status/amount (aggregated)
- MONTHLY_DUES — dues balance (aggregated)
- ATTENDANCE_LOG — event count (aggregated)

╔══════════════════════════════════════════════════════════════════╗
║              MEMBER — ATTENDANCE                                 ║
╚══════════════════════════════════════════════════════════════════╝

[] - My Digital QR ID

The Member can view their official CAUFA QR code (used for check‑in during
meetings and events). If no QR code is registered, an upload button is shown.
The QR code can be expanded to full‑screen or downloaded. A caption reminds
the member to present the QR code to the Secretary during attendance.

Tables read:

- MEMBER — qr_code URL

Tables affected:

- MEMBER — qr_code field updated (on upload/replace)

[] - Attendance Summary

The system displays a summary grid showing total Present, Absent, Late, and
attendance Rate (percentage) across all events.

Tables read:

- ATTENDANCE_LOG — aggregated per member (present/absent/late counts)

[] - Attendance History

A list of recent attendance records (event name, status, date, time). A
"View All" button opens a full‑page history sub‑view with all records.

Tables read:

- ATTENDANCE_LOG — ordered by timestamp, filtered by member
- ATTENDANCE_EVENT — linked event name

[] - Upcoming Events

Shows events the member has not yet registered for (is_ended = False). Each
entry displays the event name, description, date, time, and location.

Tables read:

- ATTENDANCE_EVENT — upcoming events not yet attended

[] - Attendance PIN Setup

The Member can set a 4‑10 digit numeric PIN that the Secretary can use to
check them in manually if they forget or lose their QR code. The UI shows
whether a PIN is already registered, masked, and allows saving a new PIN.

Tables affected:

- MEMBER — pin_hash / pin fields updated

╔══════════════════════════════════════════════════════════════════╗
║              MEMBER — FINANCE                                    ║
╚══════════════════════════════════════════════════════════════════╝

[] - Financial Overview

Displays a summary card showing: Outstanding Balance, Membership Fee status,
Monthly Contributions total, Death Aid Contribution, Medical Aid Claim info,
and Next Due Date.

Tables read:

- MEMBERSHIP_FEE — latest fee record
- MONTHLY_DUES — aggregated paid/pending amounts
- MEDICAL_AID — aggregated claim amounts per member
- DEATH_AID — aggregated benefit amounts per member
- CONTRIBUTION — aggregated contribution amounts per member

[] - Payment Status

Shows Total Paid, Pending Payments, Last Payment Date, and Payment Method.

Tables read:

- MEMBERSHIP_FEE — paid/pending fee records
- MONTHLY_DUES — paid/pending dues records

[] - My Ledger

A full table of all financial records for the member: membership fees,
monthly dues, medical aid claims, death aid claims, and contributions.
Each row shows date, type, description, debit/credit, status, and reference.

Tables read:

- MEMBERSHIP_FEE — all fee records for member
- MONTHLY_DUES — all dues records for member
- MEDICAL_AID — all medical claims for member
- DEATH_AID — all death claims for member
- CONTRIBUTION — all contribution records for member

[] - Contribution History

A focused view showing only aid contribution records (linked to aid tracking
posts) with date, type, amount, and status.

Tables read:

- CONTRIBUTION — filtered by member, ordered by date

[] - Payment History

Shows past payment records (membership fees and monthly dues) with date,
type, amount, and status.

Tables read:

- MEMBERSHIP_FEE — ordered by created_at, filtered by member
- MONTHLY_DUES — ordered by created_at, filtered by member

[] - Submit Direct Payment

The Member can submit a payment (Membership Fee or Monthly Dues) directly.
Required fields: payment type, amount, payment method, and optional reference
number and proof‑of‑payment file. On submission, a record is created with
status "Pending" and a TransactionVerification entry is queued for the
Treasurer (Pending Treasurer Check).

Tables created:

- MEMBERSHIP_FEE — fee record (if "membership_fee")
- MONTHLY_DUES — dues record (if "monthly_dues")
- TRANSACTION_VERIFICATION — status "Pending Treasurer Check"
- SUPPORTING_PROOF — uploaded proof file (if provided)
- GLOBAL_AUDIT_TRAIL — "MEMBER_SUBMITTED" logged

Pipeline position:

- Member submits → Treasurer checks → Auditor verifies → President approves
  → FUND_TRANSACTION inflow created

[] - File a Claim — Medical Aid

The Member can file a medical aid claim. Required fields: hospital name,
total bill amount, and a bill file. Additional receipts can be attached.
The system enforces a once‑per‑year rule. On submission, the claim is saved
with "Pending Verification" status and a TransactionVerification entry is
queued for the Treasurer.

Tables created:

- MEDICAL_AID — claim record (status "Pending Verification")
- TRANSACTION_VERIFICATION — status "Pending Treasurer Check"
- SUPPORTING_PROOF — uploaded bill/receipt files
- GLOBAL_AUDIT_TRAIL — "MEMBER_SUBMITTED" logged

Pipeline position (7‑step):

- Member files claim → Treasurer checks → Auditor verifies → President
  approves → AID_TRACKING_POST + CONTRIBUTION created → Treasurer releases
  → Auditor verifies finish → President approves finish → Treasurer final
  release

[] - File a Claim — Death Aid

The Member can file a death aid claim for a deceased dependent. Required
fields: deceased name, relationship to member, and claimant name. Optional:
death certificate, funeral bill amount, funeral location, interment date.
The benefit amount is auto‑calculated based on the relationship tier.
On submission, a claimant record is created/reused and the claim is saved
with "Pending Verification" status.

Benefit tiers:

- Spouse: PHP 500
- Parent / Child: PHP 500
- Sibling: PHP 250
- Parent‑in‑law: PHP 250

Tables created:

- CLAIMANT — claimant info (created if new, reused if existing)
- DEATH_AID — claim record (status "Pending Verification")
- TRANSACTION_VERIFICATION — status "Pending Treasurer Check"
- SUPPORTING_PROOF — uploaded death certificate
- GLOBAL_AUDIT_TRAIL — "MEMBER_SUBMITTED" logged

Pipeline position:

- Same 7‑step pipeline as medical aid

[] - Claim History

The Member can view all their submitted claims (medical and death aid) with
date, type, details, and status.

Tables read:

- MEDICAL_AID — all claims for member
- DEATH_AID — all claims for member

[] - Download Statement

A button to export the member's financial summary as a downloadable document.

Tables read:

- Same as My Ledger (aggregated financial data)

╔══════════════════════════════════════════════════════════════════╗
║              MEMBER — PROFILE                                    ║
╚══════════════════════════════════════════════════════════════════╝

[] - Personal Information

The Member can view their personal details: first name, middle name, last
name, gender, date of birth, and age.

Tables read:

- MEMBER — personal detail fields

[] - Account Information

The Member can view their account username and email address (read‑only).

Tables read:

- auth.USER — username, email

[] - Association Information

The Member can view their faculty/college, rank/position, membership status,
and membership date (read‑only, managed by admin).

Tables read:

- MEMBER — association fields

[] - Edit Profile

The Member can update their personal information (first name, middle name,
last name, gender, date of birth, age) and upload a profile picture. The
Account and Association tabs are read‑only with a note to contact the admin
for changes. A Rep tab allows setting an authorized representative, and a
Password tab allows changing the account password.

Tables affected:

- MEMBER — personal fields and profile picture updated
- CLAIMANT — authorized representative info (if rep tab saved)
- auth.USER — password updated (if password tab saved)
- GLOBAL_AUDIT_TRAIL — profile update logged

[] - Official CAUFA QR Code

The Member can view, download, upload, or replace their attendance QR code.
Only one QR code may be registered per member.

Tables affected:

- MEMBER — qr_code field updated

[] - Authorized Representative

The Member can set a person (name, relationship, contact number, optional
email) to act on their behalf in case of emergencies and important
membership matters.

Tables affected:

- CLAIMANT — representative record created/updated

[] - Security

The Member can view security settings: two‑factor authentication toggle,
email verification status, registered device info, and login activity. A
"Log Out From All Devices" button is provided.

[] - Change Password

The Member can update their account password with current password, new
password, and confirmation fields. Must be at least 8 characters with
letters and numbers.

Tables affected:

- auth.USER — password updated

[] - Settings

The Member can toggle Dark Mode, Push Notifications, and SMS Alerts, and
view app version information.

---

> **Footnote — Bottom Navigation:**
> The member dashboard uses a bottom navigation bar with four tabs: Home,
> Attendance, Finance, and Profile. Sub‑views (Ledger, Claim forms, QR code,
> Edit Profile, etc.) slide in as full‑page overlays with a back button.
