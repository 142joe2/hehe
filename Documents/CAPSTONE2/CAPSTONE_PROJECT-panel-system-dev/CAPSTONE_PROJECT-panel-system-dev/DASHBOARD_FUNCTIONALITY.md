# Dashboard Functionality Summary

This document summarizes the main dashboard workflows for the President, Treasurer, Auditor, and Member roles in the `CAPSTONE_PROJECT-panel-system-dev` workspace.

---

## 1. President Dashboard

### Render Path
- View function: `core_system/president_views.py::president_dashboard`
- Template: `templates/website/President/president_dashboard.html`

### Navigation and Screen Flow
1. Open the President dashboard page.
2. Sidebar items are grouped into folders: Verification, Fund, Registry, Reports, Bylaws, Administration.
3. Clicking a folder header calls `toggleFolder(...)` to expand or collapse nested menu items.
4. Clicking a menu item switches the active `dashboard-module` section by `data-target`.
5. The dashboard does not navigate to a new URL; it shows and hides sections within the same page.

### Feature Flows
- `presidential-payments`
  - Sidebar button: `data-target="presidential-payments"`
  - Screen: payments verification table
  - JS flow: `loadPresidentialQueue()` fetches pending payments
  - Backend fetch: `GET /api/president/pending-payments/`
  - User action: select rows, approve/reject payments

- `presidential-aid-requests`
  - Sidebar button: `data-target="presidential-aid-requests"`
  - Screen: pending aid request queue
  - JS flow: `loadPresidentialAidsQueue()` fetches aid requests
  - Backend fetch: `GET /api/president/pending-aids/`
  - User action: batch-select claims, then approve or reject

- `president-finish-approvals`
  - Sidebar button: `data-target="president-finish-approvals"`
  - Screen: finish approval queue
  - JS flow: `window.faApplyFilter()` filters finish requests
  - Backend fetch: likely `GET /api/president/pending-finish-requests/`

- `president-registration-requests`
  - Sidebar button: `data-target="president-registration-requests"`
  - Screen: registration approval queue
  - JS flow: `fetchRegistrationRequests()` loads requests
  - Backend fetch: `GET /api/president/registration-requests/list/`
  - User action: approve/reject registration requests

- `president-contributions`
  - Sidebar button: `data-target="president-contributions"`
  - Screen: contribution review queue
  - JS flow: `loadContributionsQueue()` fetches pending contributions
  - Backend fetch: `GET /api/president/pending-contributions/`
  - User action: `reviewBatch(batchId)` opens batch modal, then `approveBatch()` / `rejectBatch()`
  - Backend decision: `POST /api/president/contribution-decision/`

- `fund-ledger`
  - Sidebar button: `data-target="fund-ledger"`
  - Screen: fund ledger list
  - JS flow: `loadLedger(page)` loads ledger pages
  - Backend fetch: `GET /api/president/fund-ledger/?page=X`

- `view-executive-ledger`
  - Sidebar button: `data-target="view-executive-ledger"`
  - Screen: executive log and audit table
  - JS flow: `renderExecutiveLogsTable()` / `elApplyFilter()`
  - Backend fetch: `GET /api/president/executive-logs/`

- `view-reports-compiler`
  - Sidebar button: `data-target="view-reports-compiler"`
  - Screen: report generator and preview list
  - JS flow: `repApplyFilter()` filters reports
  - Backend fetch: `GET /api/president/reports/`

- Bylaws and Administration folders
  - `bylaws-constants`, `bylaws-documents`, `administration-officers`, `administration-self-enroll`, `administration-backups`
  - Each screen loads via sidebar selection and uses page-local JavaScript to fetch or submit data.

### Key UI Actions
- `toggleFolder(folderId, headerElement)` toggles sidebar folders.
- `setActiveModule(target)` sets which section is visible.
- `loadSystemDatabase()` initializes empty client-side state.
- `renderAllComponents()` refreshes KPI cards, aid queue, contribution queue, and notifications.
- `showCustomModal(...)` displays confirmation or alert dialogs.
- `clearPaymentApprovalSelection()` and `clearAidApprovalSelection()` clear selected rows.

### Data and Backend Interaction
- The President dashboard is mostly a client-side single-page experience.
- Data is loaded from API endpoints under `/api/president/...`.
- Approvals, batches, and contributions are handled entirely by JavaScript functions in the president template.

---

## 2. Treasurer Dashboard

### Render Path
- View function: `core_system/treasurer_views.py::treasurer_dashboard`
- Template: `templates/website/Treasurer/treasurer_dashboard.html`

### Navigation and Screen Flow
1. Open the Treasurer dashboard page.
2. Sidebar items are grouped into Membership, Monthly Dues, Claims, Aid, Fund, and Reports.
3. Clicking a menu item displays the matching section ID, such as `view-claims-queue` or `treasurer-aid-history`.
4. Sections are shown/hidden within the same HTML page rather than loading a new URL.

### Feature Flows
- `view-claims-queue`
  - Sidebar button: `data-target="view-claims-queue"`
  - Screen: pending claims list
  - JS flow: `loadClaimsQueue()` fetches `GET /api/treasurer/claims/pending/list/`
  - User action: click `Review`, then `openClaimReview(type,id)` to show claim details

- `view-member-profile`
  - Sidebar button: `data-target="view-member-profile"`
  - Screen: member upload and profile management
  - JS flow: `triggerBulkUpload()` or `triggerSingleUpload()` opens upload forms

- `view-registration-requests`
  - Sidebar button: `data-target="view-registration-requests"`
  - Screen: registration verification queue
  - JS flow: `fetchRegistrationRequests()` fetches `GET /api/treasurer/registration-requests/list/`

- `view-fee-payment`
  - Sidebar button: `data-target="view-fee-payment"`
  - Screen: membership fee payment verification

- `view-returned-entries`
  - Sidebar button: `data-target="view-returned-entries"`
  - Screen: returned fee entries and corrections

- `view-salary-deduction`, `view-otc-payment`, `view-monthly-dues-returned`
  - Screens for payroll deduction, OTC payments, and returned dues

- `view-dues-tracking`
  - Sidebar button: `data-target="view-dues-tracking"`
  - Screen: dues tracking and status dashboard

- `view-payroll-batches`
  - Sidebar button: `data-target="view-payroll-batches"`
  - Screen: payroll batch management
  - Action: `saveOrUpdateBatch()` submits payroll batch data

- `view-medical-aid`, `view-death-aid`
  - Sidebar buttons under Aid folder
  - Screens: medical and death aid request management

- `view-medical-aid-returned`, `view-death-aid-returned`
  - Screens: returned aid claims for revision

- `treasurer-aid-tracking-posts`
  - Sidebar button: `data-target="treasurer-aid-tracking-posts"`
  - Screen: active aid tracking posts and member collection actions
  - JS flow: loads `/api/treasurer/approved-aid-posts/`
  - Actions: `aid-post-member-pay`, `aid-post-member-skip`, `aid-post-member-notify`

- `treasurer-record-contribution`
  - Sidebar button: `data-target="treasurer-record-contribution"`
  - Screen: record contribution or remittance

- `treasurer-aid-history`
  - Sidebar button: `data-target="treasurer-aid-history"`
  - Screen: historical aid and contribution records

- `fund-ledger`
  - Sidebar button: `data-target="fund-ledger"`
  - Screen: fund ledger entries
  - Action: `loadLedger(1)` to fetch the first ledger page

- `view-reports`
  - Sidebar button: `data-target="view-reports"`
  - Screen: reports generation
  - Backend: `GET /api/treasurer/reports/generate/`

- `view-fund-reports`
  - Sidebar button: `data-target="view-fund-reports"`
  - Screen: fund report downloads
  - Backend: `/api/treasurer/fund-reports/`

### Key UI Actions
- `toggleFolder(folderId, headerElement)` expands/collapses menu folders.
- `setActiveModule(target)` makes a module visible.
- `saveDashboardState()` persists module and filter state.
- `restoreDashboardState()` restores state on reload.
- `loadClaimsQueue()` refreshes the claims list.
- `fetchRegistrationRequests()` refreshes registration queue and badge count.
- `fetchMembershipFeeTotal()` reloads fee totals for the dashboard.
- `refreshDepartmentData()` refreshes department analytics tables.

### Data and Backend Interaction
- The Treasurer dashboard uses APIs under `/api/treasurer/...`.
- Most interactions are JavaScript-driven from the template.
- Data updates happen in-page with fetch requests and DOM rendering.

---

## 3. Auditor Dashboard

### Render Path
- View function: `core_system/auditor_views.py::auditor_dashboard`
- Template: `templates/website/Auditor/auditor_dashboard.html`

### Navigation and Screen Flow
1. Open the Auditor dashboard page.
2. Sidebar sections group features into Aid, Verification, Registry, Fund, and Reports.
3. Clicking a menu item displays the corresponding section.
4. The page remains a single HTML document with section switching.

### Feature Flows
- `audit-members-payments`
  - Sidebar button: `data-target="audit-members-payments"`
  - Screen: member payment audit list
  - JS flow: `audPayToggle()` filters the list
  - Backend fetch: likely `GET /api/auditor/pending-payments/`

- `audit-aid-requests`
  - Sidebar button: `data-target="audit-aid-requests"`
  - Screen: aid request audit list
  - JS flow: `audAidToggle()` filters the list
  - Backend fetch: likely `GET /api/auditor/pending-aids/`

- `audit-finish-requests`
  - Sidebar button: `data-target="audit-finish-requests"`
  - Screen: finish request queue
  - JS flow: `loadPendingFinishRequests()` fetches `/api/auditor/pending-finish-requests/`
  - User action: `verifyFinish(postId)` / `rejectFinish(postId)` calls `/api/auditor/aid-post-verify-finish/`

- `auditor-registration-requests`
  - Sidebar button: `data-target="auditor-registration-requests"`
  - Screen: registration approval queue
  - JS flow: `fetchAuditorRegistrationRequests()` calls `GET /api/auditor/registration-requests/list/`
  - User action: `openAuditorRegModal(requestId)` opens details modal
  - Decision action: `auditorHandleAction(...)` posts to `/api/auditor/registration-requests/<id>/verify/`

- `view-audit-ledger`
  - Sidebar button: `data-target="view-audit-ledger"`
  - Screen: audit ledger
  - JS flow: `loadLedger(page)` fetches audit ledger pages

- `audit-payroll-batches`
  - Sidebar button: `data-target="audit-payroll-batches"`
  - Screen: payroll batch review
  - Review action: `reviewBatch(batchId)` opens batch details
  - Approve/reject: `/api/auditor/payroll-batches/<id>/verify/` or `/reject/`

- `audit-chain-integrity`
  - Sidebar button: `data-target="audit-chain-integrity"`
  - Screen: audit chain viewer
  - JS flow: `loadAuditChain()` loads chain entries

- `fund-ledger` and `member-deductions`
  - Screens show fund and deduction data via ledger pagination

- `view-reports-compiler`
  - Screen: reports compiler and preview list

### Key UI Actions
- `refreshDepartmentData()` reloads department analytics.
- `loadPendingFinishRequests()` refreshes the finish request list.
- `verifyFinish(postId)` and `rejectFinish(postId)` perform finish approval actions.
- `fetchAuditorRegistrationRequests()` refreshes the registration queue.
- `openAuditorRegModal(requestId)` opens a modal with request details and action buttons.

### Data and Backend Interaction
- Auditor actions use APIs under `/api/auditor/...`.
- Most screens are rendered and updated entirely in the template.
- Approval and verification workflows are JavaScript-driven.

---

## 4. Member Dashboard

### Render Path
- View function: `core_system/views.py::member_dashboard`
- API endpoint for data: `core_system/member_views.py::member_dashboard_data`
- Template: `templates/website/Member/member_dashboard.html`

### Navigation and Screen Flow
1. Open the Member dashboard page.
2. The bottom nav and screen panels are connected by `switchScreen(id)`.
3. `switchScreen(...)` hides all `.screen` sections and activates the selected one.
4. If a member opens `screen-claims`, `loadMyClaims()` runs automatically.
5. `updateNav(activeScreen)` updates the bottom navigation highlight.

### Feature Flows
- `screen-home`
  - Default landing page
  - Shows summary cards and quick access buttons
  - Data updated by `updateHomeScreen(d)` after `refreshDashboard()`

- `screen-attendance`
  - Attendance hub with QR, summary, events, and PIN
  - Tabs: `attend-qr`, `attend-summary`, `attend-events`, `attend-pin`
  - `openAttendTab(el, tabId)` switches the active attendance tab
  - `loadAttendance()` fetches `/api/member/attendance/`

- `screen-finance`
  - Finance overview page
  - Buttons:
    - My Ledger → `switchScreen('screen-ledger')`
    - Contribution History → `switchScreen('screen-contributions')`
    - Payment History → `switchScreen('screen-payments')`
    - Submit Direct Payment → `switchScreen('screen-submit-payment')`
    - File a Claim → `switchScreen('screen-file-claim')`
    - Claim History → `switchScreen('screen-claims')`
  - `updateFinanceScreen(d)` updates outstanding balances, fee status, and claim status

- `screen-ledger`
  - Shows dues and payment records
  - `updateLedgerScreen(d)` renders `dues_records` from dashboard API

- `screen-contributions`
  - Shows aid contribution history
  - `updateContributionsScreen(d)` renders `contribution_records`
  - Claims-related contribution entries are excluded in the backend query
  - Backend: `GET /api/member/dashboard/data/`

- `screen-payments`
  - Shows payment history
  - `updatePaymentHistoryScreen(d)` renders recent membership fee and dues entries
  - `filterPayments(el, filter)` updates the visible list by payment type

- `screen-submit-payment`
  - Payment submission form
  - `selectPaymentType(el, type)` chooses Membership Fee or Monthly Dues
  - `updatePaymentMethodDetails()` switches field visibility for cash vs reference number
  - `submitPayment()` posts to `/api/member/payment/submit/`

- `screen-file-claim`
  - Multi-step claim wizard
  - `selectClaimType(el, type)` switches between medical and death aid
  - `claimNextStep()` and `claimPrevStep()` navigate steps
  - `addClaimFile(input)` / `removeClaimFile(index)` manage uploaded proof files
  - `buildClaimReview()` renders the claim summary before submission
  - `submitClaim()` posts to `/api/member/claim/file/` and uploads proofs to `/api/member/claim/upload-proof/`

- `screen-claims`
  - Claim history list
  - `loadMyClaims()` fetches `/api/member/claims/list/`
  - `filterClaims(el, filter)` filters claim type
  - `openClaimDetail(id, type)` sets `screen-claim-detail`

- `screen-claim-detail`
  - Shows detailed claim information for a selected claim

- `screen-profile`
  - Member profile hub with navigation to sub-screens
  - Buttons:
    - Personal Information → `switchScreen('screen-profile-personal')`
    - Contact Information → `switchScreen('screen-profile-contact')`
    - Association Info → `switchScreen('screen-profile-association')`
    - Edit Profile → `switchScreen('screen-edit-profile')`
    - QR Code → `switchScreen('screen-qr-profile')`
    - Authorized Rep → `switchScreen('screen-rep')`
    - Security → `switchScreen('screen-security')`
    - Settings → `switchScreen('screen-settings')`
    - Logout → `logoutUser()`

- `screen-profile-personal`, `screen-profile-contact`, `screen-profile-association`
  - Show personal member details grouped by type

- `screen-edit-profile`
  - Edit contact details and upload profile photo
  - `saveProfile()` posts updates to `/api/member/profile/update/`

- `screen-qr-profile`
  - QR code display generated by `buildQR(...)`

- `screen-rep`
  - Authorized representative details
  - Member save endpoint: `/api/member/rep/save/`

- `screen-security`
  - Security settings page

- `screen-settings`
  - App settings page

### Key UI Actions
- `switchScreen(id)` changes the visible screen panel.
- `openAttendTab(el, tabId)` changes attendance tab panels.
- `apiGet(url)` and `apiPost(url, data)` are generic fetch helpers.
- `refreshDashboard()` reloads the main dashboard data.
- `updateHomeScreen(...)`, `updateProfileScreens(...)`, `updateFinanceScreen(...)`, `updateLedgerScreen(...)`, `updateContributionsScreen(...)`, `updatePaymentHistoryScreen(...)`, `updateClaimsScreens(...)`, `updateNotificationScreen(...)` update specific sections.
- `saveProfile()` sends profile updates.
- `logoutUser()` confirms sign-out and redirects to `/logout/`.
- `loadMyClaims()` fetches claims and then `renderClaims(filter)` updates the claim list.

### Data and Backend Interaction
- `member_dashboard_data()` returns all screen data in a single API response.
- `member_submit_payment()` handles direct payment submission.
- `member_file_claim()` handles claim filing and prevents duplicate pending claims.
- `member_notifications()` returns member notifications.
- Backend query for `contribution_records` excludes claim-related contribution entries so claimants do not see their own aid repayment contributions.

---

## Reference Files
- `templates/website/President/president_dashboard.html`
- `templates/website/Treasurer/treasurer_dashboard.html`
- `templates/website/Auditor/auditor_dashboard.html`
- `templates/website/Member/member_dashboard.html`
- `core_system/president_views.py`
- `core_system/treasurer_views.py`
- `core_system/auditor_views.py`
- `core_system/views.py`
- `core_system/member_views.py`
