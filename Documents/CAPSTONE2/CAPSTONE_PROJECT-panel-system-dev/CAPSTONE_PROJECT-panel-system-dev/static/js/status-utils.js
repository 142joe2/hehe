// ── Canonical status constants ──
// Mirror of core_system/constants/status_constants.py
const Status = {
  PENDING: "Pending",
  PENDING_VERIF: "Pending Verification",
  PENDING_TRES_CHECK: "Pending Treasurer Check",
  AUDITOR_VERIFIED: "Auditor Verified",
  RETURNED_REVISION: "Returned for Revision",
  APPROVED: "Approved",
  PRESIDENT_APPROVED: "President Approved",
  REJECTED: "Rejected",
  RELEASED: "Released",
  TREASURER_DIRECT: "Treasurer Direct",  // Treasurer-created claims that go directly to Auditor

  ALL_PENDING: new Set(["Pending", "Pending Verification", "Pending Treasurer Check", "Treasurer Direct"]),
  ALL_AUDITOR_VERIFIED: new Set(["Auditor Verified", "Approved", "President Approved", "Released"]),
  ALL_AUDITOR_ACTED: new Set(["Auditor Verified", "Returned for Revision"]),
  ALL_PRESIDENT_CAN_ACT: new Set([
    "Pending", "Pending Verification", "Pending Treasurer Check",
    "Auditor Verified", "Returned for Revision",
  ]),
  ALL_APPROVED: new Set(["Approved", "President Approved"]),
};

const statusUtils = {
  isPending: (s) => Status.ALL_PENDING.has(s),
  isAuditorVerified: (s) => Status.ALL_AUDITOR_VERIFIED.has(s),
  isAuditorActed: (s) => Status.ALL_AUDITOR_ACTED.has(s),
  isReturned: (s) => s === Status.RETURNED_REVISION,
  isApproved: (s) => Status.ALL_APPROVED.has(s),
  isRejected: (s) => s === Status.REJECTED,
  isReleased: (s) => s === Status.RELEASED,
  canPresidentAct: (s) => Status.ALL_PRESIDENT_CAN_ACT.has(s),
};
