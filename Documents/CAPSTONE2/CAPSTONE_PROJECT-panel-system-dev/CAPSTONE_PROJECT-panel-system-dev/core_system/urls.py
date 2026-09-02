from django.urls import path
from . import views
from . import member_views
from . import auditor_views
from . import treasurer_views
from . import president_views
from . import secretary_views
from . import push_views
from . import settings_views
from . import report_views
from . import auditor_report_views
from . import fund_report_views
from . import htmx_views
from . import public_views
from . import auth_views
from . import pio_views


urlpatterns = [
    # --- Member Workspace Endpoints ---
    path("member/", views.member_dashboard, name="member_dashboard"),
    path("member/onboarding/", views.member_onboarding, name="member_onboarding"),
    path("api/member/notifications/", member_views.member_notifications, name="member_notifications"),
    path("api/member/notifications/mark-read/", member_views.member_mark_notifications_read, name="member_mark_notifications_read"),
    path("api/member/notifications/<int:notification_id>/mark-read/", member_views.member_mark_notification_read, name="member_mark_notification_read"),
    path("api/member/ledger/", member_views.member_ledger, name="member_ledger"),
    path("api/member/unpaid-months/", member_views.member_unpaid_months, name="member_unpaid_months"),
    path("api/member/exemption/request/", member_views.member_request_exemption, name="member_request_exemption"),
    path("api/member/attendance/", member_views.member_attendance_summary, name="member_attendance_summary"),
    path("api/member/events/", member_views.member_events, name="member_events"),
    path("api/member/profile/update/", member_views.member_update_profile, name="member_update_profile"),
    path("api/member/profile/change-email/", member_views.member_change_email, name="member_change_email"),
    path("api/member/profile/send-email-otp/", member_views.member_send_email_otp, name="member_send_email_otp"),
    path("api/member/profile/verify-email-otp/", member_views.member_verify_email_otp, name="member_verify_email_otp"),
    path("api/member/profile/check-email-exists/", member_views.member_check_email_exists, name="member_check_email_exists"),
    path("api/member/payment/submit/", member_views.member_submit_payment, name="member_submit_payment"),
    path("api/member/claim/file/", member_views.member_file_claim, name="member_file_claim"),
    path("api/member/claim/upload-proof/", member_views.member_claim_upload_proof, name="member_claim_upload_proof"),
    path("api/member/claims/list/", member_views.member_claims_list, name="member_claims_list"),
    path("api/member/claim/detail/<int:claim_id>/", member_views.member_claim_detail, name="member_claim_detail"),
    path("api/member/pin/save/", member_views.member_save_pin, name="member_save_pin"),
    path("api/member/rep/save/", member_views.member_save_rep, name="member_save_rep"),
    path("api/member/dashboard/data/", member_views.member_dashboard_data, name="member_dashboard_data"),
    path("api/member/picture/upload/", member_views.member_upload_picture, name="member_upload_picture"),
    # --- Member Onboarding API ---
    path("api/member/onboarding/photo/", member_views.onboarding_upload_photo, name="onboarding_upload_photo"),
    path("api/member/onboarding/qr/", member_views.onboarding_save_qr, name="onboarding_save_qr"),
    path("api/member/onboarding/qr/check/", member_views.onboarding_check_qr, name="onboarding_check_qr"),
    path("api/member/onboarding/pin/", member_views.onboarding_save_pin, name="onboarding_save_pin"),
    path("api/member/onboarding/pin/check/", member_views.onboarding_check_pin, name="onboarding_check_pin"),
    path("api/member/onboarding/complete/", member_views.onboarding_complete, name="onboarding_complete"),
    path("api/member/certificates/", member_views.member_certificates, name="member_certificates"),
    path("api/member/certificate/<int:certificate_id>/view/", member_views.member_certificate_view, name="member_certificate_view"),
    path("api/member/certificate/<int:certificate_id>/download/", member_views.member_certificate_download, name="member_certificate_download"),
    # --- Treasurer Workspace Endpoints ---
    path("treasurer/", treasurer_views.treasurer_dashboard, name="treasurer_dashboard"),
    # --- Treasurer Member Enrollment API ---
    # Frontend posts to: /api/treasurer/members/add/
    path(
        "api/treasurer/members/add/",
        treasurer_views.treasurer_add_member,
        name="treasurer_add_member",
    ),
    # --- Treasurer Members List API (for dashboard table rendering) ---
    path(
        "api/treasurer/members/list/",
        treasurer_views.treasurer_members_list,
        name="treasurer_members_list",
    ),
    path(
        "api/treasurer/members/active-count/",
        treasurer_views.treasurer_active_members_count,
        name="treasurer_active_members_count",
    ),
    path(
        "api/treasurer/officers/list/",
        treasurer_views.treasurer_officers_list,
        name="treasurer_officers_list",
    ),
    path(
        "api/treasurer/records/requiring-revision/",
        treasurer_views.treasurer_records_requiring_revision,
        name="treasurer_records_requiring_revision",
    ),
    # --- Secretary Workspace Endpoints ---
    path("secretary/", secretary_views.secretary_dashboard, name="secretary_dashboard"),
    path("api/secretary/attendance/today/", secretary_views.secretary_attendance_today, name="secretary_attendance_today"),
    path("api/secretary/attendance/summary/", secretary_views.secretary_attendance_summary, name="secretary_attendance_summary"),
    path("api/secretary/attendance/event-records/", secretary_views.secretary_event_attendance_records, name="secretary_event_attendance_records"),
    path("api/secretary/attendance/checkin/", secretary_views.secretary_attendance_checkin, name="secretary_attendance_checkin"),
    path("api/secretary/events/", secretary_views.secretary_all_events_list, name="secretary_events"),
    path("api/secretary/events/list/", secretary_views.secretary_events_list, name="secretary_events_list"),
    path("api/secretary/events/create/", secretary_views.secretary_event_create, name="secretary_event_create"),
    path("api/secretary/events/open-attendance/", secretary_views.secretary_event_open_attendance, name="secretary_event_open_attendance"),
    path("api/secretary/events/close-attendance/", secretary_views.secretary_event_close_attendance, name="secretary_event_close_attendance"),
    path("api/secretary/events/list-all/", secretary_views.secretary_all_events_list, name="secretary_all_events_list"),
    path("api/secretary/events/<int:event_id>/participants/", secretary_views.secretary_event_participants, name="secretary_event_participants"),
    path("api/secretary/attendance/bulk-time-in/", secretary_views.secretary_bulk_time_in, name="secretary_bulk_time_in"),
    path("api/secretary/attendance/records/", secretary_views.secretary_attendance_records, name="secretary_attendance_records"),
    path("api/secretary/attendance/live-monitoring/", secretary_views.secretary_live_monitoring, name="secretary_live_monitoring"),
    path("api/secretary/documents/list/", secretary_views.secretary_documents_list, name="secretary_documents_list"),
    path("api/secretary/documents/upload/", secretary_views.secretary_document_upload, name="secretary_document_upload"),
    path("api/secretary/minutes/list/", secretary_views.secretary_minutes_list, name="secretary_minutes_list"),
    path("api/secretary/minutes/create/", secretary_views.secretary_minutes_create, name="secretary_minutes_create"),
    path("api/secretary/announcements/list/", secretary_views.secretary_announcements_list, name="secretary_announcements_list"),
    path("api/secretary/announcements/create/", secretary_views.secretary_announcement_create, name="secretary_announcement_create"),
    path("api/secretary/members/directory/", secretary_views.secretary_member_directory, name="secretary_member_directory"),
    path("api/secretary/certificate/settings/", secretary_views.secretary_certificate_settings, name="secretary_certificate_settings"),
    path("api/secretary/certificate/settings/save/", secretary_views.secretary_certificate_settings_save, name="secretary_certificate_settings_save"),
    path("api/secretary/certificate/history/", secretary_views.secretary_certificate_history, name="secretary_certificate_history"),
    path("api/secretary/certificate/resend/", secretary_views.secretary_certificate_resend, name="secretary_certificate_resend"),
    path("api/secretary/dashboard/charts/", secretary_views.secretary_dashboard_charts, name="secretary_dashboard_charts"),
    path("api/secretary/notifications/", secretary_views.secretary_notifications, name="secretary_notifications"),
    path("api/secretary/profile/update/", secretary_views.secretary_profile_update, name="secretary_profile_update"),
    path("api/secretary/profile/upload-photo/", secretary_views.secretary_profile_upload_photo, name="secretary_profile_upload_photo"),
    path("api/secretary/attendance/export/pdf/", secretary_views.secretary_attendance_export_pdf, name="secretary_attendance_export_pdf"),
    path("api/secretary/attendance/export/excel/", secretary_views.secretary_attendance_export_excel, name="secretary_attendance_export_excel"),
    path("api/secretary/reports/generate/", secretary_views.generate_attendance_report, name="generate_attendance_report"),
    path("api/secretary/reports/legacy/<str:report_type>/", secretary_views.secretary_reports, name="secretary_reports"),
    path("api/secretary/documents/stats/", secretary_views.secretary_document_stats, name="secretary_document_stats"),
    path("api/secretary/documents/activity/", secretary_views.secretary_document_activity, name="secretary_document_activity"),
    path("api/secretary/documents/replace/", secretary_views.secretary_document_replace, name="secretary_document_replace"),
    path("api/secretary/documents/version-history/", secretary_views.secretary_document_version_history, name="secretary_document_version_history"),
    path("api/secretary/documents/toggle-favorite/", secretary_views.secretary_document_toggle_favorite, name="secretary_document_toggle_favorite"),
    path("api/secretary/documents/toggle-public/", secretary_views.secretary_document_toggle_public, name="secretary_document_toggle_public"),
    path("api/secretary/documents/preview/", secretary_views.secretary_document_preview, name="secretary_document_preview"),
    path("api/secretary/documents/download/", secretary_views.secretary_document_download, name="secretary_document_download"),
    path("api/secretary/categories/list/", secretary_views.secretary_category_list, name="secretary_category_list"),
    path("api/secretary/categories/create/", secretary_views.secretary_category_create, name="secretary_category_create"),
    path("api/secretary/categories/rename/", secretary_views.secretary_category_rename, name="secretary_category_rename"),
    path("api/secretary/categories/delete/", secretary_views.secretary_category_delete, name="secretary_category_delete"),
    path("api/secretary/event-types/list/", secretary_views.secretary_eventtype_list, name="secretary_eventtype_list"),
    path("api/secretary/event-types/create/", secretary_views.secretary_eventtype_create, name="secretary_eventtype_create"),
    path("api/secretary/event-types/rename/", secretary_views.secretary_eventtype_rename, name="secretary_eventtype_rename"),
    path("api/secretary/event-types/delete/", secretary_views.secretary_eventtype_delete, name="secretary_eventtype_delete"),
    # --- Treasurer Membership Fee APIs ---
    path(
        "api/treasurer/membership-fees/add/",
        treasurer_views.treasurer_membership_fee_add,
        name="treasurer_membership_fee_add",
    ),
    path(
        "register/",
        public_views.public_register,
        name="public_register",
    ),
    path(
        "register/status/",
        public_views.public_registration_status,
        name="public_registration_status",
    ),
    path(
        "api/public/membership-registration/availability/",
        public_views.public_registration_field_availability,
        name="public_registration_field_availability",
    ),
    path(
        "api/public/membership-registration/",
        public_views.public_submit_registration_request,
        name="public_submit_registration_request",
    ),
    path(
        "api/treasurer/membership-fees/list/",
        treasurer_views.treasurer_membership_fee_list,
        name="treasurer_membership_fee_list",
    ),
    path(
        "api/treasurer/registration-requests/list/",
        treasurer_views.treasurer_registration_requests_list,
        name="treasurer_registration_requests_list",
    ),
    path(
        "api/treasurer/registration-requests/<int:request_id>/action/",
        treasurer_views.treasurer_registration_request_action,
        name="treasurer_registration_request_action",
    ),
    path(
        "api/treasurer/financial-pending-counts/",
        treasurer_views.treasurer_financial_pending_counts,
        name="treasurer_financial_pending_counts",
    ),
    path(
        "api/treasurer/membership-fees/returned/list/",
        treasurer_views.treasurer_membership_fees_returned_list,
        name="treasurer_membership_fees_returned_list",
    ),
    path(
        "api/treasurer/monthly-dues/returned/list/",
        treasurer_views.treasurer_monthly_dues_returned_list,
        name="treasurer_monthly_dues_returned_list",
    ),
    path(
        "api/treasurer/medical-aid/returned/list/",
        treasurer_views.treasurer_medical_aid_returned_list,
        name="treasurer_medical_aid_returned_list",
    ),
    path(
        "api/treasurer/death-aid/returned/list/",
        treasurer_views.treasurer_death_aid_returned_list,
        name="treasurer_death_aid_returned_list",
    ),
    path(
        "api/treasurer/approved-transactions-total/",
        treasurer_views.treasurer_approved_transactions_total,
        name="treasurer_approved_transactions_total",
    ),
    path(
        "api/cash-flow-summary/",
        treasurer_views.cash_flow_summary,
        name="cash_flow_summary",
    ),
    # --- Treasurer Monthly Dues OTC / Salary APIs ---
    path("api/treasurer/monthly-dues/add/", treasurer_views.treasurer_monthly_dues_add, name="treasurer_monthly_dues_add"),
    path("api/treasurer/monthly-dues/otc/add/", treasurer_views.treasurer_monthly_dues_otc_add, name="treasurer_monthly_dues_otc_add"),
    path("api/treasurer/monthly-dues/list/", treasurer_views.treasurer_monthly_dues_otc_list, name="treasurer_monthly_dues_list"),
    path("api/treasurer/monthly-dues/otc/list/", treasurer_views.treasurer_monthly_dues_otc_list, name="treasurer_monthly_dues_otc_list"),
    path("api/treasurer/monthly-dues/detail/<int:dues_id>/", treasurer_views.treasurer_monthly_dues_detail, name="treasurer_monthly_dues_detail"),
    path("api/treasurer/monthly-dues/salary/add/", treasurer_views.treasurer_monthly_dues_salary_add, name="treasurer_monthly_dues_salary_add"),
    path("api/treasurer/monthly-dues/salary/list/", treasurer_views.treasurer_monthly_dues_salary_list, name="treasurer_monthly_dues_salary_list"),
    path("api/treasurer/monthly-dues/salary/bulk-preview/", treasurer_views.treasurer_salary_bulk_preview, name="treasurer_salary_bulk_preview"),
    path("api/treasurer/monthly-dues/salary/bulk-process/", treasurer_views.treasurer_salary_bulk_process, name="treasurer_salary_bulk_process"),
    path("api/treasurer/monthly-dues/salary/next-batch-ref/", treasurer_views.treasurer_next_batch_ref, name="treasurer_next_batch_ref"),
    path("api/treasurer/monthly-dues/tracking/", treasurer_views.treasurer_monthly_dues_tracking, name="treasurer_monthly_dues_tracking"),
    path("api/treasurer/monthly-dues/approve/", treasurer_views.treasurer_approve_monthly_dues, name="treasurer_approve_monthly_dues"),
    path("api/treasurer/member/<int:member_id>/unpaid-months/", treasurer_views.treasurer_member_unpaid_months, name="treasurer_member_unpaid_months"),
    path("api/treasurer/member/<int:member_id>/deductions/", treasurer_views.treasurer_member_deductions, name="treasurer_member_deductions"),
    path("api/treasurer/exemption-requests/list/", treasurer_views.treasurer_exemption_requests_list, name="treasurer_exemption_requests_list"),
    path("api/treasurer/exemption-requests/<int:exemption_id>/action/", treasurer_views.treasurer_exemption_action, name="treasurer_exemption_action"),
    path("api/treasurer/exemption-requests/<int:exemption_id>/override/", treasurer_views.treasurer_exemption_override, name="treasurer_exemption_override"),
    path(
        "api/treasurer/releases/list/",
        treasurer_views.treasurer_releases_list,
        name="treasurer_releases_list",
    ),
    path(
        "api/treasurer/dashboard/inflow-outflow/",
        treasurer_views.treasurer_dashboard_inflow_outflow,
        name="treasurer_dashboard_inflow_outflow",
    ),
    path(
        "api/treasurer/dashboard/monthly-flow/",
        treasurer_views.treasurer_monthly_flow,
        name="treasurer_monthly_flow",
    ),
    # --- Treasurer Visualization Data Endpoints ---
    path(
        "api/treasurer/dashboard/payment-methods/",
        treasurer_views.treasurer_dashboard_payment_methods,
        name="treasurer_dashboard_payment_methods",
    ),
    path(
        "api/treasurer/dashboard/dues-status/",
        treasurer_views.treasurer_dashboard_dues_status,
        name="treasurer_dashboard_dues_status",
    ),
    path(
        "api/treasurer/dashboard/aid-progress/",
        treasurer_views.treasurer_dashboard_aid_progress,
        name="treasurer_dashboard_aid_progress",
    ),
    path(
        "api/treasurer/dashboard/action-queue/",
        treasurer_views.treasurer_dashboard_action_queue,
        name="treasurer_dashboard_action_queue",
    ),
    path(
        "api/treasurer/aids/release/",
        treasurer_views.treasurer_release_aid,
        name="treasurer_release_aid",
    ),
    # --- Medical Aid (Claims) APIs ---
    path(
        "api/treasurer/medical-aid/add/",
        treasurer_views.treasurer_medical_aid_add,
        name="treasurer_medical_aid_add",
    ),
    path(
        "api/treasurer/medical-aids/list/",
        treasurer_views.treasurer_medical_aid_list,
        name="treasurer_medical_aid_list",
    ),
    path(
        "api/treasurer/medical-aid/batch-add/",
        treasurer_views.treasurer_medical_aid_batch_add,
        name="treasurer_medical_aid_batch_add",
    ),
    # --- Death Aid (Claims) APIs ---
    path(
        "api/treasurer/death-aid/add/",
        treasurer_views.treasurer_death_aid_add,
        name="treasurer_death_aid_add",
    ),
    path(
        "api/treasurer/death-aids/list/",
        treasurer_views.treasurer_death_aids_list,
        name="treasurer_death_aids_list",
    ),
    # --- Treasurer Resubmit API ---
    path(
        "api/treasurer/resubmit/<str:table_name>/<int:record_id>/",
        treasurer_views.treasurer_resubmit_entry,
        name="treasurer_resubmit_entry",
    ),
    # --- Treasurer Member Update / Retire API ---
    path(
        "api/treasurer/members/update/",
        treasurer_views.treasurer_member_update,
        name="treasurer_member_update",
    ),
    path(
        "api/treasurer/members/retire/",
        treasurer_views.treasurer_member_retire,
        name="treasurer_member_retire",
    ),
    path(
        "api/treasurer/members/batch-add/",
        treasurer_views.treasurer_member_batch_add,
        name="treasurer_member_batch_add",
    ),
    path(
        "api/treasurer/members/position-ranks/list/",
        treasurer_views.treasurer_position_rank_list,
        name="treasurer_position_rank_list",
    ),
    path(
        "api/treasurer/members/position-ranks/options/",
        treasurer_views.treasurer_position_rank_options,
        name="treasurer_position_rank_options",
    ),
    path(
        "api/treasurer/members/position-ranks/add/",
        treasurer_views.treasurer_position_rank_add,
        name="treasurer_position_rank_add",
    ),
    path(
        "api/treasurer/members/position-ranks/<int:rank_id>/update/",
        treasurer_views.treasurer_position_rank_update,
        name="treasurer_position_rank_update",
    ),
    path(
        "api/treasurer/members/position-ranks/<int:rank_id>/delete/",
        treasurer_views.treasurer_position_rank_delete,
        name="treasurer_position_rank_delete",
    ),
    path(
        "api/treasurer/member/<int:member_id>/details/",
        treasurer_views.treasurer_member_details,
        name="treasurer_member_details",
    ),

    # --- Treasurer Payroll Batch APIs ---
    path(
        "api/treasurer/payroll-batches/create/",
        treasurer_views.treasurer_payroll_batch_create,
        name="treasurer_payroll_batch_create",
    ),
    path(
        "api/treasurer/payroll-batches/list/",
        treasurer_views.treasurer_payroll_batch_list,
        name="treasurer_payroll_batch_list",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/",
        treasurer_views.treasurer_payroll_batch_detail,
        name="treasurer_payroll_batch_detail",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/edit/",
        treasurer_views.treasurer_payroll_batch_edit,
        name="treasurer_payroll_batch_edit",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/delete/",
        treasurer_views.treasurer_payroll_batch_delete,
        name="treasurer_payroll_batch_delete",
    ),
    path(
        "api/treasurer/payroll-batches/<int:batch_id>/history/",
        treasurer_views.treasurer_payroll_batch_history,
        name="treasurer_payroll_batch_history",
    ),

    # --- Treasurer Department Visualization APIs ---
    path(
        "api/treasurer/department/member-stats/",
        treasurer_views.treasurer_member_stats_by_department,
        name="treasurer_member_stats_by_department",
    ),
    path(
        "api/treasurer/department/payment-tracking/",
        treasurer_views.treasurer_payment_tracking_by_department,
        name="treasurer_payment_tracking_by_department",
    ),
    path(
        "api/treasurer/department/financial-summary/",
        treasurer_views.treasurer_financial_summary_by_department,
        name="treasurer_financial_summary_by_department",
    ),
    path(
        "api/treasurer/department/aid-trends/",
        treasurer_views.treasurer_aid_trends_by_department,
        name="treasurer_aid_trends_by_department",
    ),
    path(
        "api/treasurer/department/payroll-analysis/",
        treasurer_views.treasurer_payroll_analysis_by_department,
        name="treasurer_payroll_analysis_by_department",
    ),

    # --- Superadmin Workspace Endpoints ---
    path("superadmin/", views.superadmin_dashboard, name="superadmin_dashboard"),

    # --- Auditor Workspace Endpoints ---
    path("auditor/", auditor_views.auditor_dashboard, name="auditor_dashboard"),

    path(
        "api/auditor/pending-payments/list/",
        auditor_views.auditor_pending_payments,
        name="auditor_pending_payments",
    ),
    path(
        "api/auditor/member-registry/",
        auditor_views.auditor_member_registry,
        name="auditor_member_registry",
    ),
    path(
        "api/auditor/pending-aids/list/",
        auditor_views.auditor_pending_aids,
        name="auditor_pending_aids",
    ),
    path(
        "api/auditor/pending-counts/",
        auditor_views.auditor_pending_counts,
        name="auditor_pending_counts",
    ),
    path(
        "api/auditor/verify-payment/",
        auditor_views.auditor_verify_payment,
        name="auditor_verify_payment",
    ),
    path(
        "api/auditor/verify-aid/",
        auditor_views.auditor_verify_aid,
        name="auditor_verify_aid",
    ),
    path(
        "api/auditor/pending-membership-fees/list/",
        auditor_views.auditor_pending_membership_fees,
        name="auditor_pending_membership_fees",
    ),
    path(
        "api/auditor/verify-membership-fee/",
        auditor_views.auditor_verify_membership_fee,
        name="auditor_verify_membership_fee",
    ),
    path(
        "api/auditor/verify-membership-fee/batch/",
        auditor_views.auditor_verify_membership_fee_batch,
        name="auditor_verify_membership_fee_batch",
    ),
    path(
        "api/auditor/verify-batch/",
        auditor_views.auditor_verify_batch,
        name="auditor_verify_batch",
    ),
    path(
        "api/auditor/reject/",
        auditor_views.reject_transaction,
        name="auditor_reject_transaction",
    ),
    path(
        "api/auditor/supporting-proof/<str:model_type>/<int:record_id>/",
        auditor_views.auditor_supporting_proof,
        name="auditor_supporting_proof",
    ),
    # --- Auditor Payroll Batch APIs ---
    path(
        "api/auditor/pending-payroll-batches/",
        auditor_views.auditor_pending_payroll_batches,
        name="auditor_pending_payroll_batches",
    ),
    path(
        "api/auditor/payroll-batches/<int:batch_id>/",
        auditor_views.auditor_payroll_batch_detail,
        name="auditor_payroll_batch_detail",
    ),
    path(
        "api/auditor/payroll-batches/<int:batch_id>/verify/",
        auditor_views.auditor_verify_payroll_batch,
        name="auditor_verify_payroll_batch",
    ),
    path(
        "api/auditor/payroll-batches/<int:batch_id>/reject/",
        auditor_views.auditor_reject_payroll_batch,
        name="auditor_reject_payroll_batch",
    ),
    # --- Auditor Registration Review ---
    path(
        "api/auditor/registration-requests/list/",
        auditor_views.auditor_registration_requests_list,
        name="auditor_registration_requests_list",
    ),
    path(
        "api/auditor/registration-requests/<int:request_id>/verify/",
        auditor_views.auditor_verify_registration_request,
        name="auditor_verify_registration_request",
    ),
    # --- President Workspace Endpoints ---
    path("president/", president_views.president_dashboard, name="president_dashboard"),
    # --- SystemBackup Workspace Endpoints ---
    path("systembackup/", president_views.systembackup_dashboard, name="systembackup_dashboard"),
    path("api/president/monthly-dues/approve/", president_views.president_approve_monthly_dues, name="president_approve_monthly_dues"),
    path("api/president/officers/", president_views.president_officers_list, name="president_officers_list"),
    path("api/president/officers/create/", president_views.president_officers_create, name="president_officers_create"),
    path("api/president/officers/<int:officer_id>/update/", president_views.president_officers_update, name="president_officers_update"),
    path("api/president/officers/<int:officer_id>/reset-password/", president_views.president_officers_reset_password, name="president_officers_reset_password"),
    path("api/president/officers/<int:officer_id>/deactivate/", president_views.president_officers_deactivate, name="president_officers_deactivate"),
    path("api/president/profile/", president_views.president_profile, name="president_profile"),
    path("api/president/profile/update/", president_views.president_profile_update, name="president_profile_update"),
    path("api/president/officers/self-enroll/", president_views.president_officer_self_enroll, name="president_officer_self_enroll"),
    path("api/president/backups/", president_views.president_backups_list, name="president_backups_list"),
    path("api/president/backups/manual/", president_views.president_backups_manual, name="president_backups_manual"),
    path("api/president/backups/<int:job_id>/restore/", president_views.president_backups_restore, name="president_backups_restore"),
    # --- President Document Repository Endpoints ---
    path("api/president/documents/list/", president_views.president_documents_list, name="president_documents_list"),
    path("api/president/documents/stats/", president_views.president_document_stats, name="president_document_stats"),
    path("api/president/documents/activity/", president_views.president_document_activity, name="president_document_activity"),
    path("api/president/documents/upload/", president_views.president_document_upload, name="president_document_upload"),
    path("api/president/documents/replace/", president_views.president_document_replace, name="president_document_replace"),
    path("api/president/documents/toggle-favorite/", president_views.president_document_toggle_favorite, name="president_document_toggle_favorite"),
    path("api/president/documents/toggle-public/", president_views.president_document_toggle_public, name="president_document_toggle_public"),
    path("api/president/documents/preview/", president_views.president_document_preview, name="president_document_preview"),
    path("api/president/documents/download/", president_views.president_document_download, name="president_document_download"),
    path("api/president/categories/list/", president_views.president_category_list, name="president_category_list"),
    path("api/president/categories/create/", president_views.president_category_create, name="president_category_create"),
    path("api/president/categories/rename/", president_views.president_category_rename, name="president_category_rename"),
    path("api/president/categories/delete/", president_views.president_category_delete, name="president_category_delete"),
    path("api/president/audit-logs/", president_views.president_audit_logs, name="president_audit_logs"),
    # --- President Payroll Batch APIs ---
    path(
        "api/president/pending-payroll-batches/",
        president_views.president_pending_payroll_batches,
        name="president_pending_payroll_batches",
    ),
    path(
        "api/president/payroll-batches/<int:batch_id>/",
        president_views.president_payroll_batch_detail,
        name="president_payroll_batch_detail",
    ),
    path(
        "api/president/payroll-batches/<int:batch_id>/approve/",
        president_views.president_approve_payroll_batch,
        name="president_approve_payroll_batch",
    ),
    path(
        "api/president/payroll-batches/<int:batch_id>/reject/",
        president_views.president_reject_payroll_batch,
        name="president_reject_payroll_batch",
    ),
    # --- President Registration Approval ---
    path(
        "api/president/registration-requests/list/",
        president_views.president_registration_requests_list,
        name="president_registration_requests_list",
    ),
    path(
        "api/president/registration-requests/<int:request_id>/approve/",
        president_views.president_approve_registration_request,
        name="president_approve_registration_request",
    ),
    # --- President: auditor-approved payments display ---
    path(
        "api/president/auditor-approved-payments/list/",
        president_views.president_auditor_approved_payments_queue,
        name="president_auditor_approved_payments_queue",
    ),
    path(
        "api/president/auditor-approved-payments/detail/<int:entity_id>/",
        president_views.president_auditor_approved_payment_detail,
        name="president_auditor_approved_payment_detail",
    ),
    path(
        "api/president/auditor-approved-aids/list/",
        president_views.president_auditor_approved_aids_queue,
        name="president_auditor_approved_aids_queue",
    ),
    path(
        "api/payments/presidential-queue/",
        president_views.get_pending_presidential_payments,
        name="presidential_queue",
    ),
    path(
        "api/payments/presidential-decision/",
        president_views.submit_presidential_decision,
        name="presidential_decision",
    ),
    path(
        "api/payments/presidential-decision/batch/",
        president_views.submit_presidential_decision_batch,
        name="presidential_decision_batch",
    ),
    path(
        "api/aids/presidential-decision/",
        president_views.submit_presidential_aid_decision,
        name="presidential_aid_decision",
    ),
    path(
        "api/aids/presidential-decision/batch/",
        president_views.submit_presidential_aid_decision_batch,
        name="presidential_aid_decision_batch",
    ),
    path(
        "api/audit/trail/<str:table_name>/<int:record_id>/",
        president_views.audit_trail_api,
        name="audit_trail_api",
    ),
    path(
        "api/president/overview/",
        president_views.president_overview,
        name="president_overview",
    ),
    path(
        "api/president/kpi-counts/",
        president_views.president_kpi_counts,
        name="president_kpi_counts",
    ),
    # --- President Visualization Data Endpoints ---
    path(
        "api/president/dashboard/financial-overview/",
        president_views.president_dashboard_financial_overview,
        name="president_dashboard_financial_overview",
    ),
    path(
        "api/president/dashboard/fund-movement/",
        president_views.president_dashboard_fund_movement,
        name="president_dashboard_fund_movement",
    ),
    path(
        "api/president/dashboard/membership-overview/",
        president_views.president_dashboard_membership_overview,
        name="president_dashboard_membership_overview",
    ),
    path(
        "api/president/dashboard/dues-compliance/",
        president_views.president_dashboard_dues_compliance,
        name="president_dashboard_dues_compliance",
    ),
    path(
        "api/president/dashboard/aid-overview/",
        president_views.president_dashboard_aid_overview,
        name="president_dashboard_aid_overview",
    ),
    path(
        "api/president/dashboard/contribution-progress/",
        president_views.president_dashboard_contribution_progress,
        name="president_dashboard_contribution_progress",
    ),
    path(
        "api/president/dashboard/approval-pipeline/",
        president_views.president_dashboard_approval_pipeline,
        name="president_dashboard_approval_pipeline",
    ),
    path(
        "api/president/dashboard/oversight-attention/",
        president_views.president_dashboard_oversight_attention,
        name="president_dashboard_oversight_attention",
    ),
    # --- Auditor Aid Tracking Post Endpoints ---
    # NOTE: approved-aid-posts is kept for the PayrollBatch UI to list active posts
    path(
        "api/auditor/approved-aid-posts/",
        auditor_views.auditor_approved_aid_posts,
        name="auditor_approved_aid_posts",
    ),
    path(
        "api/auditor/aid-post-members/<int:post_id>/",
        auditor_views.auditor_aid_post_members,
        name="auditor_aid_post_members",
    ),
    # DEPRECATED â€” replaced by PayrollBatch deductions
    # path("api/auditor/aid-post-member-pay/", auditor_views.auditor_aid_post_member_pay, name="auditor_aid_post_member_pay"),
    # path("api/auditor/aid-post-member-skip/", auditor_views.auditor_aid_post_member_skip, name="auditor_aid_post_member_skip"),
    # path("api/auditor/aid-post-finish/", auditor_views.auditor_aid_post_finish, name="auditor_aid_post_finish"),
    path(
        "api/auditor/aid-post-history/",
        auditor_views.auditor_aid_post_history,
        name="auditor_aid_post_history",
    ),
    path(
        "api/auditor/audited-logs/",
        auditor_views.auditor_audited_logs,
        name="auditor_audited_logs",
    ),
    path(
        "api/audit/trail/verify/",
        auditor_views.auditor_audit_trail_verify,
        name="audit_trail_verify_all",
    ),
    path(
        "api/audit/trail/verify/<str:table_name>/<int:record_id>/",
        auditor_views.auditor_audit_trail_verify,
        name="audit_trail_verify",
    ),
    # --- Auditor Department Payment Compliance Heat Map ---
    path(
        "api/auditor/compliance-heatmap/",
        auditor_views.auditor_compliance_heatmap,
        name="auditor_compliance_heatmap",
    ),
    # --- Auditor Visualization Data Endpoints ---
    path(
        "api/auditor/dashboard/paid-pending-unpaid/",
        auditor_views.auditor_dashboard_paid_pending_unpaid,
        name="auditor_dashboard_paid_pending_unpaid",
    ),
    path(
        "api/auditor/dashboard/audit-pipeline/",
        auditor_views.auditor_dashboard_audit_pipeline,
        name="auditor_dashboard_audit_pipeline",
    ),
    path(
        "api/auditor/dashboard/audit-attention/",
        auditor_views.auditor_dashboard_audit_attention,
        name="auditor_dashboard_audit_attention",
    ),
    path(
        "api/auditor/payment-years/",
        auditor_views.auditor_payment_years,
        name="auditor_payment_years",
    ),
    path(
        "api/auditor/department-detail/",
        auditor_views.auditor_department_detail,
        name="auditor_department_detail",
    ),
    path(
        "api/auditor/member-payment-history/",
        auditor_views.auditor_member_payment_history,
        name="auditor_member_payment_history",
    ),
    path(
        "api/auditor/send-reminder/",
        auditor_views.auditor_send_payment_reminder,
        name="auditor_send_payment_reminder",
    ),
    # --- Treasurer Member Claims Queue ---
    path("api/treasurer/claims/pending/list/", treasurer_views.treasurer_claims_pending_list, name="treasurer_claims_pending_list"),
    path("api/treasurer/claim/review/", treasurer_views.treasurer_claim_review, name="treasurer_claim_review"),
    # --- Treasurer Aid Tracking Post Endpoints ---
    # NOTE: approved-aid-posts is kept for the PayrollBatch UI to list active posts
    path(
        "api/treasurer/approved-aid-posts/",
        treasurer_views.treasurer_approved_aid_posts,
        name="treasurer_approved_aid_posts",
    ),
    path(
        "api/treasurer/aid-post-members/<int:post_id>/",
        treasurer_views.treasurer_aid_post_members,
        name="treasurer_aid_post_members",
    ),
    path("api/treasurer/aid-post-member-pay/", treasurer_views.treasurer_aid_post_member_pay, name="treasurer_aid_post_member_pay"),
    path("api/treasurer/aid-post-member-skip/", treasurer_views.treasurer_aid_post_member_skip, name="treasurer_aid_post_member_skip"),
    path("api/treasurer/aid-post-member-unskip/", treasurer_views.treasurer_aid_post_member_unskip, name="treasurer_aid_post_member_unskip"),
    path("api/treasurer/aid-post-start-collection/", treasurer_views.treasurer_aid_post_start_collection, name="treasurer_aid_post_start_collection"),
    path("api/treasurer/aid-post-finish/", treasurer_views.treasurer_aid_post_finish, name="treasurer_aid_post_finish"),
    path("api/treasurer/aid-post-paid-with-funds/", treasurer_views.treasurer_aid_post_paid_with_funds, name="treasurer_aid_post_paid_with_funds"),
    path("api/treasurer/aid-post-member-notify/", treasurer_views.treasurer_aid_post_member_notify, name="treasurer_aid_post_member_notify"),
    path(
        "api/treasurer/aid-post-history/",
        treasurer_views.treasurer_aid_post_history,
        name="treasurer_aid_post_history",
    ),
    # --- Public (no-auth) Bylaws / Policy viewing for landing page ---
    path("api/public/bylaws/", public_views.public_bylaws, name="public_bylaws"),
    path(
        "api/public/bylaws/file/<int:document_id>/",
        public_views.public_bylaws_file,
        name="public_bylaws_file",
    ),
    path(
        "api/public/bylaws/render/<int:document_id>/",
        public_views.public_bylaws_render,
        name="public_bylaws_render",
    ),
    path(
        "api/public/documents/render/<int:document_id>/",
        public_views.public_document_render,
        name="public_document_render",
    ),
    # --- Logout (custom officer session) ---
    path("logout/", views.logout_view, name="logout"),
    # --- Push Notification Subscriptions ---
    path("api/push/vapid-key/", push_views.vapid_public_key, name="push_vapid_key"),
    path("api/push/subscribe/", push_views.push_subscribe, name="push_subscribe"),
    path("api/push/unsubscribe/", push_views.push_unsubscribe, name="push_unsubscribe"),
    path("api/push/health-check/", push_views.push_health_check, name="push_health_check"),
    path("api/push/vapid-check/", push_views.push_vapid_check, name="push_vapid_check"),
    path("api/push/validate-subscription/", push_views.validate_subscription, name="push_validate_subscription"),
    # --- System Settings API Endpoints ---
    path(
        "api/settings/grace-period/",
        settings_views.grace_period_setting,
        name="grace_period_setting",
    ),
    path(
        "api/settings/notifications/",
        settings_views.notification_settings,
        name="notification_settings",
    ),
    # --- Report API Endpoints ---
    path(
        "api/reports/overall/",
        report_views.download_overall_report,
        name="download_overall_report",
    ),
    path(
        "api/reports/department/<int:dept_id>/",
        report_views.download_department_report,
        name="download_department_report",
    ),
    path(
        "api/reports/contributions/",
        report_views.download_contribution_report,
        name="download_contribution_report",
    ),
    path(
        "api/treasurer/reports/generate/",
        report_views.generate_unified_report_view,
        name="generate_unified_report",
    ),
    # --- Auditor Report Endpoints ---
    path(
        "api/auditor/reports/create/",
        auditor_report_views.auditor_create_report,
        name="auditor_create_report",
    ),
    path(
        "api/auditor/reports/",
        auditor_report_views.auditor_reports_list,
        name="auditor_reports_list",
    ),
    path(
        "api/auditor/reports/<int:report_id>/",
        auditor_report_views.auditor_report_detail,
        name="auditor_report_detail",
    ),
    # --- President Report Approval Flow ---
    path(
        "api/president/auditor-reports/",
        auditor_report_views.president_auditor_reports_list,
        name="president_auditor_reports_list",
    ),
    path(
        "api/president/auditor-reports/<int:report_id>/approve/",
        auditor_report_views.president_approve_report,
        name="president_approve_report",
    ),
    path(
        "api/president/auditor-reports/<int:report_id>/request-revision/",
        auditor_report_views.president_request_report_revision,
        name="president_request_report_revision",
    ),
    # --- Treasurer: Organization Fund Report ---
    path(
        "api/treasurer/fund-reports/",
        fund_report_views.treasurer_fund_reports_list,
        name="treasurer_fund_reports_list",
    ),
    path(
        "api/treasurer/fund-reports/create/",
        fund_report_views.treasurer_create_fund_report,
        name="treasurer_create_fund_report",
    ),
    path(
        "api/treasurer/fund-reports/<int:report_id>/download/",
        fund_report_views.treasurer_download_fund_report,
        name="treasurer_download_fund_report",
    ),
    path(
        "api/treasurer/fund-reports/<int:report_id>/submit/",
        fund_report_views.treasurer_submit_fund_report,
        name="treasurer_submit_fund_report",
    ),
    # --- Auditor: Fund Report Verification (mockup maker-checker flow) ---
    path(
        "api/auditor/fund-reports/",
        fund_report_views.auditor_fund_reports_list,
        name="auditor_fund_reports_list",
    ),
    path(
        "api/auditor/fund-reports/<int:report_id>/verify/",
        fund_report_views.auditor_verify_fund_report,
        name="auditor_verify_fund_report",
    ),
    path(
        "api/auditor/fund-reports/<int:report_id>/return/",
        fund_report_views.auditor_return_fund_report,
        name="auditor_return_fund_report",
    ),
    path(
        "api/auditor/fund-reports/<int:report_id>/download/",
        fund_report_views.auditor_download_fund_report,
        name="auditor_download_fund_report",
    ),
    # --- President: Fund Report Approval ---
    path(
        "api/president/fund-reports/",
        fund_report_views.president_fund_reports_list,
        name="president_fund_reports_list",
    ),
    path(
        "api/president/fund-reports/<int:report_id>/approve/",
        fund_report_views.president_approve_fund_report,
        name="president_approve_fund_report",
    ),
    path(
        "api/president/fund-reports/<int:report_id>/reject/",
        fund_report_views.president_reject_fund_report,
        name="president_reject_fund_report",
    ),
    path(
        "api/president/fund-reports/<int:report_id>/download/",
        fund_report_views.president_download_fund_report,
        name="president_download_fund_report",
    ),
    # --- Treasurer: Mark Aid Post as Finished (sends to Auditor) ---
    path("api/treasurer/aid-post-upload-deduction-sheet/", treasurer_views.treasurer_aid_post_upload_deduction_sheet, name="treasurer_aid_post_upload_deduction_sheet"),
    path("api/treasurer/aid-post-record-remittance/", treasurer_views.treasurer_aid_post_record_remittance, name="treasurer_aid_post_record_remittance"),
    path("api/treasurer/aid-post-mark-finished/", treasurer_views.treasurer_aid_post_mark_finished, name="treasurer_aid_post_mark_finished"),
    # --- Treasurer: Release Aid Post (record fund in/out and close) ---
    path("api/treasurer/aid-post-release/", treasurer_views.treasurer_aid_post_release, name="treasurer_aid_post_release"),
    path("api/treasurer/aid-post-release-acknowledge/<int:post_id>/", treasurer_views.treasurer_aid_post_release_acknowledge, name="treasurer_aid_post_release_acknowledge"),
    path("api/treasurer/aid-post-close-repayment/", treasurer_views.treasurer_aid_post_close_repayment, name="treasurer_aid_post_close_repayment"),
    # --- Monthly Collection Trend ---
    path(
        "api/treasurer/dashboard/monthly-collection/",
        treasurer_views.treasurer_dashboard_monthly_collection,
        name="treasurer_dashboard_monthly_collection",
    ),
    # --- Auditor: Aid Post Finish Verification ---
    path("api/auditor/pending-finish-requests/", auditor_views.auditor_pending_finish_requests, name="auditor_pending_finish_requests"),
    path("api/auditor/aid-post-verify-finish/", auditor_views.auditor_verify_post_finish, name="auditor_verify_post_finish"),
    path("api/auditor/finish-request-details/", auditor_views.auditor_finish_request_details, name="auditor_finish_request_details"),
    # --- President Aid Tracking Post Finish Approval ---
    path("api/president/aid-post-finish-requests/", president_views.president_pending_finish_requests, name="president_pending_finish_requests"),
    path("api/president/aid-post-finish-approve/", president_views.president_approve_aid_post_finish, name="president_approve_aid_post_finish"),
    path("api/president/aid-post-finish-reject/", president_views.president_reject_aid_post_finish, name="president_reject_aid_post_finish"),
    path("api/president/finish-request-details/", president_views.president_finish_request_details, name="president_finish_request_details"),
    # --- President ByLaws Constants Management ---
    path("api/president/pending-contributions/", president_views.president_pending_contributions, name="president_pending_contributions"),
    path("api/president/contribution-decision/", president_views.submit_presidential_contribution_decision, name="president_contribution_decision"),
    path("api/president/bylaws/constants/", president_views.get_policy_constants, name="president_bylaws_constants"),
    path("api/president/bylaws/constants/update/", president_views.update_policy_constant, name="president_bylaws_constant_update"),
    path("api/president/bylaws/files/", president_views.bylaws_files_api, name="president_bylaws_files"),
    path("api/president/bylaws/files/upload/", president_views.upload_bylaws_file, name="president_bylaws_file_upload"),
    path("api/president/bylaws/files/<int:document_id>/delete/", president_views.delete_bylaws_file, name="president_bylaws_file_delete"),
    path("api/president/bylaws/files/<int:document_id>/visibility/", president_views.toggle_bylaws_visibility, name="president_bylaws_file_visibility"),

    # --- President Oversight Reports ---
    path("api/president/oversight/members-by-college/", president_views.oversight_members_by_college, name="oversight_members_by_college"),
    path("api/president/oversight/paid-unpaid-summary/", president_views.oversight_paid_unpaid_summary, name="oversight_paid_unpaid_summary"),
    path("api/president/oversight/pending-claims/", president_views.oversight_pending_claims, name="oversight_pending_claims"),
    path("api/president/oversight/membership-status/", president_views.oversight_membership_status, name="oversight_membership_status"),
    path("api/president/oversight/membership-summary/", president_views.oversight_membership_summary, name="oversight_membership_summary"),
    path("api/president/oversight/monthly-dues-summary/", president_views.oversight_monthly_dues_summary, name="oversight_monthly_dues_summary"),
    path("api/president/oversight/contributions-summary/", president_views.oversight_contributions_summary, name="oversight_contributions_summary"),
    path("api/president/oversight/fund-summary/", president_views.oversight_fund_summary, name="oversight_fund_summary"),
    path("api/president/oversight/medical-aid/", president_views.oversight_medical_aid, name="oversight_medical_aid"),
    path("api/president/oversight/death-aid/", president_views.oversight_death_aid, name="oversight_death_aid"),
    path("api/president/oversight/approved-claims/", president_views.oversight_approved_claims, name="oversight_approved_claims"),
    path("api/president/oversight/released-claims/", president_views.oversight_released_claims, name="oversight_released_claims"),
    path("api/president/oversight/export/", president_views.oversight_export_report, name="oversight_export_report"),
    path("api/president/oversight/summary/", president_views.oversight_summary, name="oversight_summary"),
    path("api/president/oversight/custom-report/", president_views.oversight_custom_report, name="oversight_custom_report"),

    # --- HTMX Partial Endpoints ---
    path(
        "hx/cash-flow-summary/",
        htmx_views.hx_cash_flow_summary,
        name="hx_cash_flow_summary",
    ),
    path(
        "hx/treasurer/module/<str:module_name>/",
        htmx_views.hx_treasurer_module,
        name="hx_treasurer_module",
    ),
    path(
        "hx/auditor/module/<str:module_name>/",
        htmx_views.hx_auditor_module,
        name="hx_auditor_module",
    ),
    path(
        "hx/president/module/<str:module_name>/",
        htmx_views.hx_president_module,
        name="hx_president_module",
    ),
    # --- Shared Fund Ledger & Transparency APIs ---
    path(
        "api/fund-ledger/",
        views.fund_ledger_list,
        name="fund_ledger_list",
    ),
    path(
        "api/fund-balance/",
        views.fund_balance_summary,
        name="fund_balance_summary",
    ),
    path(
        "api/member-deductions/",
        views.member_deductions_list,
        name="member_deductions_list",
    ),
    path(
        "api/member/<int:member_id>/deductions/",
        views.member_deductions_list,
        name="member_deductions_by_id",
    ),
    # --- MFA API ---
    path("api/auth/mfa/enable/", auth_views.mfa_enable, name="mfa_enable"),
    path("api/auth/mfa/disable/", auth_views.mfa_disable, name="mfa_disable"),
    path("api/auth/mfa/challenge/", auth_views.mfa_challenge, name="mfa_challenge"),
    path("api/auth/mfa/verify/", auth_views.mfa_verify, name="mfa_verify"),
    path("mfa/challenge/", auth_views.mfa_challenge_page, name="mfa_challenge_page"),
    path("api/auth/zero-trust/challenge/", auth_views.zero_trust_challenge, name="zero_trust_challenge"),
    path("api/auth/zero-trust/verify/", auth_views.zero_trust_verify, name="zero_trust_verify"),
    path("api/auth/zero-trust/status/", auth_views.zero_trust_status, name="zero_trust_status"),
    path("api/auth/term-info/", auth_views.term_info, name="term_info"),
    # --- PIO Website Management ---
    path("pio/", pio_views.pio_dashboard, name="pio_dashboard"),
    path("api/pio/announcements/list/", pio_views.pio_announcements_list, name="pio_announcements_list"),
    path("api/pio/announcements/create/", pio_views.pio_announcement_create, name="pio_announcement_create"),
    path("api/pio/announcements/<int:announcement_id>/toggle/", pio_views.pio_announcement_toggle, name="pio_announcement_toggle"),
    path("api/pio/announcements/<int:announcement_id>/delete/", pio_views.pio_announcement_delete, name="pio_announcement_delete"),
    path("api/pio/announcement-categories/list/", pio_views.pio_announcement_categories_list, name="pio_announcement_categories_list"),
    path("api/pio/announcement-categories/create/", pio_views.pio_announcement_category_create, name="pio_announcement_category_create"),
    path("api/pio/announcement-categories/rename/", pio_views.pio_announcement_category_rename, name="pio_announcement_category_rename"),
    path("api/pio/announcement-categories/delete/", pio_views.pio_announcement_category_delete, name="pio_announcement_category_delete"),
    path("api/pio/news/list/", pio_views.pio_news_list, name="pio_news_list"),
    path("api/pio/news/<int:news_id>/", pio_views.pio_news_detail, name="pio_news_detail"),
    path("api/pio/news/create/", pio_views.pio_news_create, name="pio_news_create"),
    path("api/pio/news/<int:news_id>/delete/", pio_views.pio_news_delete, name="pio_news_delete"),
    path("api/pio/news-categories/list/", pio_views.pio_news_categories_list, name="pio_news_categories_list"),
    path("api/pio/news-categories/create/", pio_views.pio_news_category_create, name="pio_news_category_create"),
    path("api/pio/news-categories/rename/", pio_views.pio_news_category_rename, name="pio_news_category_rename"),
    path("api/pio/news-categories/delete/", pio_views.pio_news_category_delete, name="pio_news_category_delete"),
    path("api/pio/hero/list/", pio_views.pio_hero_list, name="pio_hero_list"),
    path("api/pio/hero/<int:hero_id>/", pio_views.pio_hero_detail, name="pio_hero_detail"),
    path("api/pio/hero/create/", pio_views.pio_hero_create, name="pio_hero_create"),
    path("api/pio/hero/<int:hero_id>/toggle/", pio_views.pio_hero_toggle, name="pio_hero_toggle"),
    path("api/pio/hero/<int:hero_id>/delete/", pio_views.pio_hero_delete, name="pio_hero_delete"),
    path("api/pio/albums/list/", pio_views.pio_albums_list, name="pio_albums_list"),
    path("api/pio/albums/create/", pio_views.pio_album_create, name="pio_album_create"),
    path("api/pio/albums/<int:album_id>/delete/", pio_views.pio_album_delete, name="pio_album_delete"),
    path("api/pio/albums/<int:album_id>/photos/", pio_views.pio_album_photos, name="pio_album_photos"),
    path("api/pio/albums/<int:album_id>/photos/upload/", pio_views.pio_photo_upload, name="pio_photo_upload"),
    path("api/pio/photos/<int:photo_id>/delete/", pio_views.pio_photo_delete, name="pio_photo_delete"),
    path("api/pio/photos/set-featured/", pio_views.pio_photo_set_featured, name="pio_photo_set_featured"),
    path("api/pio/about/content/", pio_views.pio_about_content, name="pio_about_content"),
    path("api/pio/about/save/", pio_views.pio_about_save, name="pio_about_save"),
    path("api/pio/events/list/", pio_views.pio_events_list, name="pio_events_list"),
    path("api/pio/officers/list/", pio_views.pio_officers_list, name="pio_officers_list"),
    path("api/pio/officers/save/", pio_views.pio_officer_profile_save, name="pio_officer_profile_save"),
    path("api/pio/officers/<int:profile_id>/delete/", pio_views.pio_officer_profile_delete, name="pio_officer_profile_delete"),
    path("api/pio/resources/list/", pio_views.pio_public_resources, name="pio_public_resources"),
]

handler403 = "core_system.president_views.permission_denied_view"
