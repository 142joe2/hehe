from django.db import models
import hashlib
import hmac
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
from django.db.models.signals import pre_save
from django.dispatch import receiver

class OfficerUser(models.Model):
    user_id_PK = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    department_id_FK = models.ForeignKey(
        "Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="department_id_FK",
        related_name="officers",
    )
    account_status = models.CharField(max_length=50)
    term_start = models.DateField(null=True, blank=True)
    term_end = models.DateField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=255, null=True, blank=True)
    last_mfa_email_sent_at = models.DateTimeField(null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    must_change_password = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "officer_user"


class Department(models.Model):
    department_id_PK = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    head_officer_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="head_officer_id_FK",
        related_name="headed_departments",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "department"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Member(models.Model):
    member_id_PK = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    employee_id = models.CharField(max_length=50, null=True, blank=True, unique=True)
    officer_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="officer_user_id_FK",
        related_name="linked_member_profiles",
    )
    department = models.CharField(max_length=100, null=True, blank=True)
    department_id_FK = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="department_id_FK",
        related_name="members",
    )
    position = models.CharField(max_length=100, null=True, blank=True)
    contact_number = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    employment_status = models.CharField(max_length=50)
    membership_status = models.CharField(max_length=50)
    member_type = models.CharField(max_length=50, blank=True)
    date_joined = models.DateField()
    profile_picture = models.ImageField(upload_to="profile_pics/", null=True, blank=True)
    pin_code = models.CharField(max_length=255, null=True, blank=True)
    qr_code = models.ImageField(upload_to="qr_codes/", null=True, blank=True)
    qr_data = models.CharField(max_length=255, null=True, blank=True)
    emergency_contact = models.CharField(max_length=255, null=True, blank=True)
    emergency_number = models.CharField(max_length=50, null=True, blank=True)
    setup_complete = models.BooleanField(default=False)

    class Meta:
        db_table = "member"


# Standard contribution amounts from the ISU-CAUFA By-Laws
# These are authoritative constants used by aid workflows and automated calculations.
DEATH_AID_CONTRIBUTION_MAPPING = {
    # normalized relationship -> contribution amount
    "member": Decimal("500.00"),
    "husband": Decimal("300.00"),
    "wife": Decimal("300.00"),
    "spouse": Decimal("300.00"),
    "parent": Decimal("250.00"),
    "child": Decimal("250.00"),
    "son": Decimal("250.00"),
    "daughter": Decimal("250.00"),
    "brother": Decimal("100.00"),
    "sister": Decimal("100.00"),
    "sibling": Decimal("100.00"),
    "full-blood brother": Decimal("100.00"),
    "full-blood sister": Decimal("100.00"),
}

# Fixed medical aid contribution expected from each eligible member
MEDICAL_AID_CONTRIBUTION_AMOUNT = Decimal("100.00")


class Attendance(models.Model):
    attendance_id_PK = models.AutoField(primary_key=True)
    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column="member_id_FK",
        related_name="attendance_records",
    )
    event_id_FK = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        db_column="event_id_FK",
        related_name="attendance_records",
        null=True,
        blank=True,
    )
    date = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='Present')  # Present, Late, Absent
    check_in_method = models.CharField(max_length=20, default='PIN')  # PIN, QR, Manual

    class Meta:
        db_table = "attendance"
        unique_together = [['member_id_FK', 'date']]


class MemberRegistrationRequest(models.Model):
    request_id_PK = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    employee_id = models.CharField(max_length=50)
    email = models.CharField(max_length=255, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    position = models.CharField(max_length=100, null=True, blank=True)
    membership_category = models.CharField(max_length=50, default="Permanent")
    payment_method = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    receipt_number = models.CharField(max_length=100)
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    password_hash = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, default="Pending Treasurer Review")
    returned_reason = models.TextField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_by_ip = models.GenericIPAddressField(protocol="both", unpack_ipv4=False, null=True, blank=True)
    submitted_by_user_agent = models.CharField(max_length=255, null=True, blank=True)
    processed_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="processed_by_user_id_FK",
        related_name="processed_registration_requests",
    )
    treasurer_verified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="treasurer_verified_by_user_id_FK",
        related_name="treasurer_verified_registrations",
    )
    auditor_verified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_verified_by_user_id_FK",
        related_name="auditor_verified_registrations",
    )
    president_approved_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_approved_by_user_id_FK",
        related_name="president_approved_registrations",
    )

    class Meta:
        db_table = "member_registration_request"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.full_name} ({self.employee_id}) - {self.status}"


class LoginAttemptLog(models.Model):
    attempt_id_PK = models.AutoField(primary_key=True)

    user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="user_id_FK",
    )
    username_used = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    result = models.CharField(max_length=50)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "login_attempt_log"


class AccessSession(models.Model):
    session_id_PK = models.AutoField(primary_key=True)

    user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.CASCADE,
        db_column="user_id_FK",
    )
    token_id = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    session_status = models.CharField(max_length=50)
    last_activity_at = models.DateTimeField(null=True, blank=True)

    trusted_device = models.BooleanField(default=False)
    last_verified_location = models.JSONField(null=True, blank=True)
    session_policy = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "access_session"


class Notification(models.Model):
    notification_id_PK = models.AutoField(primary_key=True)

    recipient_type = models.CharField(max_length=50)
    recipient_id = models.IntegerField()
    recipient_name = models.CharField(max_length=255)
    recipient_contact = models.CharField(max_length=255, null=True, blank=True)
    notification_type = models.CharField(max_length=50)
    message = models.TextField()
    delivery_status = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)

    sender_name = models.CharField(max_length=255, null=True, blank=True)
    sender_role = models.CharField(max_length=50, null=True, blank=True)
    receipt_number = models.CharField(max_length=255, null=True, blank=True)

    category = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="dues, contribution, or general",
    )
    related_post_id_FK = models.ForeignKey(
        "AidTrackingPost",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column="related_post_id_FK",
        related_name="notifications",
    )
    overdue_bucket = models.CharField(
        max_length=10, null=True, blank=True,
        help_text="1d, 3d, 5d, 7d, 15d+",
    )
    channel = models.CharField(
        max_length=20, null=True, blank=True,
        help_text="email, sms, push",
    )
    scheduled_date = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    is_read = models.BooleanField(default=False, db_column="is_read")

    class Meta:
        db_table = "notification"


class PushSubscription(models.Model):
    subscription_id_PK = models.AutoField(primary_key=True)

    officer_id_FK = models.ForeignKey(
        "OfficerUser",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column="officer_id_FK",
        related_name="push_subscriptions",
    )
    member_id_FK = models.ForeignKey(
        "Member",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        db_column="member_id_FK",
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=500)
    p256dh_key = models.CharField(max_length=256)
    auth_key = models.CharField(max_length=128)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    origin = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "push_subscription"
        unique_together = (("member_id_FK", "endpoint"), ("officer_id_FK", "endpoint"))


class MonthlyDues(models.Model):
    dues_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )
    month_covered = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=50)

    # Approval workflow fields
    treasurer_status = models.CharField(max_length=50, default="Pending Treasurer Review", db_column="treasurer_status")
    treasurer_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="treasurer_id_FK",
        related_name="monthly_dues_treasurer_approved",
    )
    treasurer_remarks = models.TextField(null=True, blank=True)
    treasurer_approved_at = models.DateTimeField(null=True, blank=True)

    auditor_status = models.CharField(max_length=50, default="Pending Auditor Review", db_column="auditor_status")
    auditor_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_id_FK",
        related_name="monthly_dues_auditor_approved",
    )
    auditor_remarks = models.TextField(null=True, blank=True)
    auditor_approved_at = models.DateTimeField(null=True, blank=True)

    president_status = models.CharField(max_length=50, default="Pending President Approval", db_column="president_status")
    president_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_id_FK",
        related_name="monthly_dues_president_approved",
    )
    president_remarks = models.TextField(null=True, blank=True)
    president_approved_at = models.DateTimeField(null=True, blank=True)

    # Added to support treasurer_dashboard.html OTC form field: otc_date
    payment_date = models.DateField(null=True, blank=True)

    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    deduction_batch_reference = models.CharField(max_length=100, null=True, blank=True)
    remittance_reference = models.CharField(max_length=100, null=True, blank=True)

    is_advance = models.BooleanField(
        default=False,
        db_column="is_advance",
        help_text="True when the covered month is in the future (early/advance payment).",
    )

    recorded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="recorded_by_user_id_FK",
    )


    class Meta:
        db_table = "monthly_dues"


class MemberLedger(models.Model):
    ledger_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
        related_name="ledger_entries",
    )

    transaction_type = models.CharField(
        max_length=50,
        help_text="membership_fee, monthly_dues, contribution, medical_aid, death_aid, refund, adjustment",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    direction = models.CharField(
        max_length=10,
        help_text="credit or debit",
    )
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    reference_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="FK to the source record (MonthlyDues, MembershipFee, etc.)",
    )
    reference_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="The model name of the reference",
    )

    description = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    recorded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="recorded_by_user_id_FK",
        related_name="ledger_entries_recorded",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "member_ledger"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["member_id_FK"]),
            models.Index(fields=["transaction_type"]),
            models.Index(fields=["recorded_at"]),
        ]


class MembershipFee(models.Model):
    fee_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=50)
    payment_date = models.DateField()
    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    deposit_reference = models.CharField(max_length=100, null=True, blank=True)

    recorded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="recorded_by_user_id_FK",
    )

    class Meta:
        db_table = "membership_fee"
        unique_together = (('member_id_FK', 'receipt_number'),)


class FinancialDocumentArchive(models.Model):
    document_id_PK = models.AutoField(primary_key=True)

    related_module = models.CharField(max_length=100)
    related_record_id = models.IntegerField()
    document_type = models.CharField(max_length=100)

    file_path = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_hash = models.CharField(max_length=255)
    verification_status = models.CharField(max_length=50)

    uploaded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="uploaded_by_user_id_FK",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "financial_document_archive"


class BylawsFile(models.Model):
    BYLAWS_DOCUMENT_TYPE_CONSTITUTION = "Constitution"
    BYLAWS_DOCUMENT_TYPE_BYLAWS = "By-Laws"
    BYLAWS_DOCUMENT_TYPE_PUBLIC = "Public Documents"
    BYLAWS_DOCUMENT_TYPE_OTHER = "Other"

    BYLAWS_DOCUMENT_TYPE_CHOICES = [
        (BYLAWS_DOCUMENT_TYPE_CONSTITUTION, "Constitution"),
        (BYLAWS_DOCUMENT_TYPE_BYLAWS, "By-Laws"),
        (BYLAWS_DOCUMENT_TYPE_PUBLIC, "Public Documents"),
        (BYLAWS_DOCUMENT_TYPE_OTHER, "Other"),
    ]

    bylaws_file_id = models.AutoField(primary_key=True)

    document_type = models.CharField(
        max_length=50,
        choices=BYLAWS_DOCUMENT_TYPE_CHOICES,
        default=BYLAWS_DOCUMENT_TYPE_BYLAWS,
    )
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_data = models.BinaryField()
    file_size = models.IntegerField()
    file_hash = models.CharField(max_length=255)

    verification_status = models.CharField(max_length=50, default="Active")
    is_public_visible = models.BooleanField(default=False)

    uploaded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="uploaded_by_user_id_FK",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bylaws_files"


class SupportingProof(models.Model):
    proof_id_PK = models.AutoField(primary_key=True)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_column="content_type_id",
    )
    object_id = models.PositiveIntegerField(db_column="object_id")
    content_object = GenericForeignKey("content_type", "object_id")

    file = models.FileField(
        upload_to="supporting_proofs/%Y/%m/%d/",
        max_length=500,
        db_column="file_path",
    )
    file_name = models.CharField(max_length=255, db_column="file_name")
    file_type = models.CharField(max_length=100, db_column="file_type")

    file_sha256 = models.CharField(max_length=64, db_column="file_sha256")
    row_signature = models.CharField(max_length=64, db_column="row_signature")

    uploaded_at = models.DateTimeField(auto_now_add=True, db_column="uploaded_at")
    uploaded_by = models.ForeignKey(
        "OfficerUser",
        on_delete=models.SET_NULL,
        null=True,
        db_column="uploaded_by_user_id_FK",
        related_name="supporting_proofs",
    )

    class Meta:
        db_table = "supporting_proof"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["uploaded_at"]),
        ]

    def compute_file_hash(self):
        sha = hashlib.sha256()
        for chunk in self.file.open("rb").chunks():
            sha.update(chunk)
        self.file.open("rb").close()
        return sha.hexdigest()

    def compute_row_signature(self, file_digest, object_id):
        from django.conf import settings

        message = f"{file_digest}:{object_id}:{settings.SECRET_KEY}".encode()
        return hmac.new(
            settings.SECRET_KEY.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()





class AuditFindingsReport(models.Model):
    audit_report_id_PK = models.AutoField(primary_key=True)

    report_title = models.CharField(max_length=255)
    report_period = models.CharField(max_length=100)
    findings_summary = models.TextField()
    report_status = models.CharField(max_length=50)

    prepared_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.RESTRICT,
        db_column="prepared_by_user_id_FK",
        related_name="audit_findings_reports_prepared",
    )

    prepared_date = models.DateField()

    board_submission_date = models.DateField(null=True, blank=True)
    board_meeting_reference = models.CharField(max_length=255, null=True, blank=True)

    presentation_status = models.CharField(max_length=50)
    certification_status = models.CharField(max_length=50)

    certified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="certified_by_user_id_FK",
        related_name="audit_reports_certified",
    )

    class Meta:
        db_table = "audit_findings_report"


class OrganizationFundReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]
    REPORT_STATUS_CHOICES = [
        ("Draft", "Draft"),
        ("Submitted", "Submitted"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    report_id_PK = models.AutoField(primary_key=True)

    report_period = models.CharField(max_length=20)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    report_status = models.CharField(max_length=50, choices=REPORT_STATUS_CHOICES, default="Draft")
    file_path = models.CharField(max_length=500, blank=True)

    prepared_by_user_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.RESTRICT,
        db_column="prepared_by_user_id_FK",
        related_name="fund_reports_prepared",
    )
    approved_by_user_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="approved_by_user_id_FK",
        related_name="fund_reports_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    auditor_verified_by_user_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="auditor_verified_by_user_id_FK",
        related_name="fund_reports_verified",
    )
    auditor_verified_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization_fund_report"
        ordering = ["-created_at"]


class MedicalAid(models.Model):
    medical_aid_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )

    request_date = models.DateField()
    requested_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hospital_name = models.CharField(max_length=255, blank=True)
    hospital_date = models.CharField(max_length=50, null=True, blank=True)
    hospital_address = models.CharField(max_length=500, null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    discharge_date = models.DateField(null=True, blank=True)
    reason_for_request = models.TextField(null=True, blank=True)
    hospital_bill_amount = models.DecimalField(max_digits=10, decimal_places=2)
    claim_year = models.IntegerField()

    document_status = models.CharField(max_length=50)
    policy_record_status = models.CharField(max_length=50)

    validated_aid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)

    treasurer_validated_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="treasurer_validated_by_user_id_FK",
        related_name="death_aid_treasurer_validated",
    )

    auditor_verified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_verified_by_user_id_FK",
        related_name="medical_aid_auditor_verified",
    )

    president_decided_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_decided_by_user_id_FK",
        related_name="death_aid_president_decided",
    )

    president_decision = models.CharField(max_length=50, null=True, blank=True)

    disbursement_source = models.CharField(
        max_length=20, null=True, blank=True,
        choices=[("fund", "Fund — paid from org fund"), ("direct", "Direct — payroll deduction, no fund impact")],
        help_text="How was this aid funded?",
    )

    released_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="released_by_user_id_FK",
        related_name="death_aid_released",
        db_constraint=False,
    )

    release_reference = models.CharField(max_length=100, null=True, blank=True)
    acknowledgement_reference = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "medical_aid"


class Claimant(models.Model):
    claimant_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column="member_id_FK",
    )
    full_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=50, null=True, blank=True)
    relationship_to_member = models.CharField(max_length=100)
    relationship_group = models.CharField(max_length=20, blank=True)
    authorization_status = models.CharField(max_length=50)

    class Meta:
        db_table = "claimant"


class DeathAid(models.Model):
    death_aid_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )

    claimant_id_FK = models.ForeignKey(
        Claimant,
        on_delete=models.RESTRICT,
        db_column="claimant_id_FK",
    )

    claim_date = models.DateField()
    claim_type = models.CharField(max_length=50)
    date_of_death = models.DateField(null=True, blank=True)

    deceased_name = models.CharField(max_length=255)
    relationship_to_member = models.CharField(max_length=100)
    relationship_group = models.CharField(max_length=20, blank=True)

    funeral_location = models.CharField(max_length=255, blank=True)
    interment_date = models.DateField(null=True, blank=True)

    benefit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    bill_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    document_status = models.CharField(max_length=50)
    status = models.CharField(max_length=50)

    treasurer_validated_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="treasurer_validated_by_user_id_FK",
    )
    auditor_verified_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_verified_by_user_id_FK",
        related_name="death_aid_auditor_verified",
    )

    president_decided_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_decided_by_user_id_FK",
        related_name="medical_aid_president_decided",
    )

    president_decision = models.CharField(max_length=50, null=True, blank=True)

    disbursement_source = models.CharField(
        max_length=20, null=True, blank=True,
        choices=[("fund", "Fund — paid from org fund"), ("direct", "Direct — payroll deduction, no fund impact")],
        help_text="How was this aid funded?",
    )

    released_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="released_by_user_id_FK",
        related_name="medical_aid_released",
        db_constraint=False,
    )

    release_reference = models.CharField(max_length=100, null=True, blank=True)
    acknowledgement_reference = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = "death_aid"


@receiver(pre_save, sender=DeathAid)
def set_death_aid_benefit(sender, instance, **kwargs):
    """Auto-set standard benefit amount and relationship_group from relationship_to_member.

    Uses `DEATH_AID_CONTRIBUTION_MAPPING` to canonicalize common relationship text.
    """
    try:
        from decimal import Decimal as _D
    except Exception:
        _D = Decimal

    rel_raw = (instance.relationship_to_member or "").strip().lower()
    if not rel_raw:
        return

    # Determine canonical amount
    amount = None
    if rel_raw in DEATH_AID_CONTRIBUTION_MAPPING:
        amount = DEATH_AID_CONTRIBUTION_MAPPING[rel_raw]
    else:
        # Keyword-based fallback
        if any(k in rel_raw for k in ("husband", "wife", "spouse")):
            amount = DEATH_AID_CONTRIBUTION_MAPPING.get("spouse")
        elif any(k in rel_raw for k in ("parent", "mother", "father")):
            amount = DEATH_AID_CONTRIBUTION_MAPPING.get("parent")
        elif any(k in rel_raw for k in ("child", "son", "daughter")):
            amount = DEATH_AID_CONTRIBUTION_MAPPING.get("child")
        elif any(k in rel_raw for k in ("brother", "sister", "sibling")):
            amount = DEATH_AID_CONTRIBUTION_MAPPING.get("sibling")
        elif "member" in rel_raw:
            amount = DEATH_AID_CONTRIBUTION_MAPPING.get("member")

    if amount is not None and (not instance.benefit_amount or instance.benefit_amount == _D("0")):
        instance.benefit_amount = amount

    # Ensure bill_amount is not automatically set to benefit_amount
    # Only set bill_amount if explicitly provided
    if not hasattr(instance, '_skip_bill_amount_auto_set'):
        # Don't auto-set bill_amount - it should remain None unless explicitly set
        pass

    # Set relationship_group for reporting/UI: member, spouse, parent_child, sibling, other
    if "member" in rel_raw:
        instance.relationship_group = "member"
    elif any(k in rel_raw for k in ("husband", "wife", "spouse")):
        instance.relationship_group = "spouse"
    elif any(k in rel_raw for k in ("parent", "mother", "father", "child", "son", "daughter")):
        instance.relationship_group = "parent_child"
    elif any(k in rel_raw for k in ("brother", "sister", "sibling")):
        instance.relationship_group = "sibling"
    else:
        instance.relationship_group = "other"


class PositionRank(models.Model):
    position_rank_id_PK = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(
        max_length=50,
        choices=[
            ("Instructor", "Instructor"),
            ("Assistant Professor", "Assistant Professor"),
            ("Associate Professor", "Associate Professor"),
            ("Full Professor", "Full Professor"),
            ("Administrative", "Administrative"),
            ("Staff", "Staff"),
            ("Other", "Other"),
        ],
        default="Other"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="created_by_user_id_FK",
    )

    class Meta:
        db_table = "position_rank"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class RevisionLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_column="content_type_id",
    )
    object_id = models.PositiveIntegerField(db_column="object_id")
    content_object = GenericForeignKey("content_type", "object_id")

    rejection_reason = models.TextField()
    snapshot_data = models.JSONField()
    auditor_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.SET_NULL,
        null=True,
        db_column="auditor_id_FK",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "revision_log"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["created_at"]),
        ]



class TransactionVerification(models.Model):
    verification_id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=50)
    record_id = models.IntegerField()

    target_category = models.CharField(
        max_length=50, null=True, blank=True,
        help_text="'payment' or 'aid' — replaces AuditorPaymentVerification/AuditorAidVerification",
    )

    verification_status = models.CharField(
        max_length=50,
        default="Pending Verification"
    )

    auditor_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_id_FK",
        related_name="transaction_verifications_audited",
    )
    auditor_remarks = models.TextField(null=True, blank=True)
    evidence_file_path = models.CharField(max_length=500, null=True, blank=True)
    evidence_file_hash = models.CharField(max_length=255, null=True, blank=True)

    returned_by_auditor_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="returned_by_auditor_id_FK",
        related_name="transaction_verifications_returned",
    )
    returned_reason = models.TextField(null=True, blank=True)
    return_count = models.IntegerField(default=0)
    deposit_slip_reference = models.CharField(max_length=255, null=True, blank=True)

    president_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="president_id_FK",
        related_name="transaction_verifications_approved",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "transaction_verification"


class TransactionArchive(models.Model):
    archive_id_PK = models.AutoField(primary_key=True)

    transaction_type = models.CharField(max_length=50)
    record_id = models.IntegerField()

    member_id_FK = models.ForeignKey(
        Member,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="member_id_FK",
    )

    member_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    validated_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=50)
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    fiscal_term = models.CharField(max_length=50, null=True, blank=True)

    release_reference = models.CharField(max_length=100, null=True, blank=True)
    released_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="released_by_user_id_FK",
        related_name="archived_releases",
    )

    verified_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(auto_now_add=True)
    archived_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="archived_by_user_id_FK",
        related_name="archived_by",
    )

    class Meta:
        db_table = "transaction_archive"


class SalaryDeductionExemption(models.Model):
    exemption_id_PK = models.AutoField(primary_key=True)

    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column="member_id_FK",
        related_name="salary_deduction_exemptions",
    )

    month_covered = models.CharField(max_length=50)
    reason = models.TextField(null=True, blank=True)
    
    status = models.CharField(
        max_length=50,
        default="Pending",
        help_text="Pending, Approved, Rejected"
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by_member = models.BooleanField(default=True)

    reviewed_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="reviewed_by_user_id_FK",
        related_name="reviewed_exemptions",
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remarks = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "salary_deduction_exemption"
        unique_together = (('member_id_FK', 'month_covered'),)


class AidTrackingPost(models.Model):
    STATUS_CHOICES = [
        ("tracking", "Tracking — members are being charged"),
        ("closed", "Closed — all tracked"),
    ]

    post_id_PK = models.AutoField(primary_key=True)

    archive_id_FK = models.ForeignKey(
        TransactionArchive,
        on_delete=models.CASCADE,
        db_column="archive_id_FK",
        related_name="aid_tracking_posts",
    )
    aid_type = models.CharField(max_length=50)
    target_month = models.CharField(max_length=7)
    total_expected = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_collected = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="tracking")
    notes = models.TextField(blank=True)

    source_type = models.CharField(max_length=50, null=True, blank=True,
        help_text="'death_aid' or 'medical_aid' — the aid that triggered this tracking post")
    source_id = models.IntegerField(null=True, blank=True,
        help_text="PK of the DeathAid or MedicalAid record")

    created_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.SET_NULL,
        null=True,
        db_column="created_by_user_id_FK",
        related_name="aid_posts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    finish_status = models.CharField(
        max_length=20, blank=True, default="",
        help_text="'' = no request, 'pending_approval' = awaiting President, 'rejected' = rejected, 'pending_release' = awaiting Treasurer fund release, 'pending_auditor' = awaiting Auditor verification, 'pending_president' = awaiting President, 'repayment' = fund released, members still owe"
    )
    finish_skip_remaining = models.BooleanField(
        default=False,
        help_text="Whether to auto-skip unpaid contributions when President approves"
    )
    finish_paid_with_funds = models.BooleanField(
        default=False,
        help_text="True when the post was paid using organizational funds instead of member contributions"
    )
    finish_cycle = models.PositiveSmallIntegerField(
        default=0,
        help_text="0 = initial collection, 1 = first cycle (paid with funds), 2 = repayment close cycle"
    )
    collection_started = models.BooleanField(
        default=False,
        help_text="Whether the treasurer has started collecting contributions for this post"
    )
    deduction_sheet = models.FileField(
        upload_to="deduction_sheets/", null=True, blank=True,
        help_text="Uploaded salary deduction accounting sheet"
    )
    deduction_batch_reference = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Reference or batch number from the salary deduction sheet"
    )
    deduction_payroll_period = models.CharField(
        max_length=50, blank=True, default="",
        help_text="Payroll period covered (e.g. 2026-07)"
    )
    deduction_sheet_uploaded_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the deduction sheet was uploaded"
    )
    deduction_remitted_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Amount deposited from salary deduction remittance"
    )
    deduction_remittance_reference = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Bank reference or deposit slip number for the remittance"
    )
    deduction_remitted_date = models.DateField(
        null=True, blank=True,
        help_text="Date the remittance was deposited"
    )
    deduction_remitted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the remittance was recorded in the system"
    )

    class Meta:
        db_table = "aid_tracking_post"
        ordering = ["-created_at"]


class Contribution(models.Model):
    STATUS_NOT_PAID = "NOT_PAID"
    STATUS_RECORDED = "RECORDED"
    STATUS_PENDING_VERIFICATION = "PENDING_VERIFICATION"
    STATUS_PAID = "PAID"
    STATUS_SKIPPED = "SKIPPED"
    STATUS_EXCLUDED_REQUESTER = "EXCLUDED_REQUESTER"

    STATUS_CHOICES = [
        (STATUS_NOT_PAID, "Not Paid"),
        (STATUS_RECORDED, "Recorded"),
        (STATUS_PENDING_VERIFICATION, "Pending Verification"),
        (STATUS_PAID, "Paid"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_EXCLUDED_REQUESTER, "Not Included (Requester)"),
    ]

    contribution_id_PK = models.AutoField(primary_key=True)

    aid_tracking_post_id_FK = models.ForeignKey(
        AidTrackingPost,
        on_delete=models.CASCADE,
        db_column="aid_tracking_post_id_FK",
        related_name="contributions",
    )
    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )
    expected_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NOT_PAID)
    is_manually_overridden = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    updated_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="updated_by_user_id_FK",
        related_name="contribution_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contribution"
        unique_together = (("aid_tracking_post_id_FK", "member_id_FK"),)


class GlobalAuditTrail(models.Model):
    trail_id = models.AutoField(primary_key=True)

    table_name = models.CharField(max_length=100)
    record_id = models.IntegerField()
    action = models.CharField(max_length=50)

    document_archive_id_FK = models.ForeignKey(
        FinancialDocumentArchive,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="document_archive_id_FK",
        related_name="audit_trails",
    )
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)

    actor_type = models.CharField(max_length=50)
    actor_id = models.IntegerField(null=True, blank=True)
    actor_name = models.CharField(max_length=255)

    ip_address = models.GenericIPAddressField(protocol="both", unpack_ipv4=False, null=True, blank=True)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    previous_hash = models.CharField(max_length=64, null=True, blank=True)
    entry_hash = models.CharField(max_length=64, null=True, blank=True)
    hmac_signature = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "global_audit_trail"
        indexes = [
            models.Index(fields=["table_name", "record_id", "timestamp"]),
        ]



class SystemSetting(models.Model):
    setting_id_PK = models.AutoField(primary_key=True)
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.TextField()
    updated_by_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="updated_by_id_FK",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "system_setting"

    def __str__(self):
        return f"{self.setting_key} = {self.setting_value}"


class SensitiveReadLog(models.Model):
    read_id = models.AutoField(primary_key=True, db_column="read_id_PK")

    table_name = models.CharField(max_length=100, db_column="module")
    record_id = models.IntegerField(null=True, blank=True)

    reader_type = models.CharField(max_length=50, db_column="purpose", default="")
    reader_id = models.IntegerField(null=True, blank=True, db_column="user_id_FK")

    device_info = models.CharField(max_length=255, null=True, blank=True)

    read_at = models.DateTimeField(auto_now_add=True, db_column="timestamp")

    class Meta:
        db_table = "sensitive_read_log"
        indexes = [
            models.Index(fields=["table_name", "record_id"]),
            models.Index(fields=["read_at"]),
        ]


class FundTransaction(models.Model):
    SOURCE_TYPES = [
        ("payroll_batch", "Payroll Batch"),
        ("death_aid", "Death Aid Disbursement"),
        ("medical_aid", "Medical Aid Disbursement"),
        ("membership_fee", "Membership Fee"),
        ("monthly_dues", "Monthly Dues"),
        ("contribution", "Contribution"),
        ("manual_adjustment", "Manual Adjustment"),
        ("aid_post_payment", "Aid Post Fund Payment"),
        ("salary_deduction_remittance", "Salary Deduction Remittance"),
    ]
    DIRECTION_CHOICES = [("inflow", "Inflow"), ("outflow", "Outflow")]

    transaction_id_PK = models.AutoField(primary_key=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    source_id = models.IntegerField(help_text="FK to the source record")
    description = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=100, null=True, blank=True, help_text="Official reference / OR number")

    recorded_by_user_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.RESTRICT,
        db_column="recorded_by_user_id_FK",
        related_name="fund_transactions",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fund_transaction"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["direction"]),
            models.Index(fields=["source_type", "source_id"]),
        ]

    @staticmethod
    def get_balance():
        from django.db.models import Sum, Q
        totals = FundTransaction.objects.aggregate(
            total_in=Sum("amount", filter=Q(direction="inflow")),
            total_out=Sum("amount", filter=Q(direction="outflow")),
        )
        return (totals["total_in"] or 0) - (totals["total_out"] or 0)


class PayrollBatch(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Auditor Verified", "Auditor Verified"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Returned for Revision", "Returned for Revision"),
    ]

    batch_id_PK = models.AutoField(primary_key=True)
    payroll_period = models.CharField(max_length=7, help_text="YYYY-MM")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    member_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    hardcopy_reference = models.CharField(max_length=100, null=True, blank=True)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Pending")
    recorded_by_user_id_FK = models.ForeignKey(
        "OfficerUser",
        on_delete=models.RESTRICT,
        db_column="recorded_by_user_id_FK",
        related_name="payroll_batches_recorded",
    )

    auditor_verified_by_user_id_FK = models.ForeignKey(
        "OfficerUser", null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column="auditor_verified_by_user_id_FK",
        related_name="payroll_batches_verified",
    )
    auditor_verified_at = models.DateTimeField(null=True, blank=True)
    auditor_remarks = models.TextField(null=True, blank=True)
    returned_by_user_id_FK = models.ForeignKey(
        "OfficerUser", null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column="returned_by_user_id_FK",
        related_name="payroll_batches_returned",
    )
    returned_reason = models.TextField(null=True, blank=True)

    president_approved_by_user_id_FK = models.ForeignKey(
        "OfficerUser", null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column="president_approved_by_user_id_FK",
        related_name="payroll_batches_approved",
    )
    president_approved_at = models.DateTimeField(null=True, blank=True)
    president_remarks = models.TextField(null=True, blank=True)

    archive_id_FK = models.ForeignKey(
        "TransactionArchive", null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column="archive_id_FK",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payroll_batch"
        ordering = ["-created_at"]


class PayrollDeduction(models.Model):
    CATEGORY_CHOICES = [
        ("monthly_dues", "Monthly Dues"),
        ("membership_fee", "Membership Fee"),
        ("aid_contribution", "Aid Contribution"),
    ]
    FUND_IMPACT_CHOICES = [
        ("inflow", "Inflow — replenishes the fund"),
        ("none", "No fund impact — direct pass-through deduction"),
    ]

    deduction_id_PK = models.AutoField(primary_key=True)
    batch_id_FK = models.ForeignKey(
        PayrollBatch,
        on_delete=models.CASCADE,
        db_column="batch_id_FK",
        related_name="deductions",
    )
    member_id_FK = models.ForeignKey(
        Member,
        on_delete=models.RESTRICT,
        db_column="member_id_FK",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    fund_impact = models.CharField(
        max_length=10, choices=FUND_IMPACT_CHOICES, default="inflow",
        help_text="'inflow' if replenishes fund, 'none' if direct pass-through",
    )

    month_covered = models.CharField(max_length=7, null=True, blank=True, help_text="YYYY-MM for monthly_dues")
    aid_tracking_post_id_FK = models.ForeignKey(
        "AidTrackingPost", null=True, blank=True,
        on_delete=models.SET_NULL,
        db_column="aid_tracking_post_id_FK",
        help_text="Links to the aid disbursement this contribution repays",
    )

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "payroll_deduction"
        indexes = [
            models.Index(fields=["batch_id_FK", "category"]),
            models.Index(fields=["member_id_FK"]),
        ]


class BackupJob(models.Model):
    STATUS_PENDING = "Pending"
    STATUS_COMPLETED = "Completed"
    STATUS_FAILED = "Failed"

    TYPE_DB = "db"
    TYPE_MEDIA = "media"
    TYPE_CONFIG = "config"

    job_id = models.AutoField(primary_key=True)

    backup_type = models.CharField(max_length=20, choices=[
        (TYPE_DB, "Database"),
        (TYPE_MEDIA, "Media"),
        (TYPE_CONFIG, "Config"),
    ])

    backup_status = models.CharField(max_length=20, choices=[
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ], default=STATUS_PENDING)

    created_at = models.DateTimeField(auto_now_add=True)

    db_dump_path = models.CharField(max_length=500, null=True, blank=True)
    media_archive_path = models.CharField(max_length=500, null=True, blank=True)

    metadata_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "backup_job"
        ordering = ["-created_at"]


class OutgoingEmail(models.Model):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SENT, "Sent"),
        (FAILED, "Failed"),
    ]

    outgoing_email_id = models.AutoField(primary_key=True)
    recipient_list = models.JSONField(default=list)
    subject = models.CharField(max_length=255)
    html_template = models.CharField(max_length=255)
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    retry_count = models.IntegerField(default=0)

    class Meta:
        db_table = "outgoing_email"
        ordering = ["created_at"]


class Event(models.Model):
    STATUS_UPCOMING = "Upcoming"
    STATUS_ONGOING = "Ongoing"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"

    STATUS_CHOICES = [
        (STATUS_UPCOMING, "Upcoming"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    event_id_PK = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    venue = models.CharField(max_length=255)
    event_date = models.DateField()
    event_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    event_type = models.CharField(max_length=100)  # General Assembly, Monthly Meeting, Seminar, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UPCOMING)
    attendance_open = models.BooleanField(default=False)
    attendance_closed = models.BooleanField(default=False)
    quorum_required = models.IntegerField(default=60)  # Percentage
    quorum_reached = models.BooleanField(default=False)
    # Certificate-related fields
    given_place = models.CharField(max_length=255, blank=True, help_text="Place where certificate is given")
    certificate_issue_date = models.DateField(null=True, blank=True, help_text="Date certificate is issued")
    auto_generate_certificates = models.BooleanField(default=False, help_text="Automatically generate certificates on event completion")
    certificate_prefix = models.CharField(max_length=20, blank=True, default="ISU-CAUFA-ATT", help_text="Prefix for certificate numbers")
    created_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="created_by_user_id_FK",
        related_name="created_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "event"
        ordering = ["-event_date", "-event_time"]


class Document(models.Model):
    DOCUMENT_TYPE_CONSTITUTION = "Constitution"
    DOCUMENT_TYPE_BYLAWS = "By-Laws"
    DOCUMENT_TYPE_MINUTES = "Minutes of Meeting"
    DOCUMENT_TYPE_MEMORANDUM = "Memorandum"
    DOCUMENT_TYPE_OFFICE_ORDER = "Office Order"
    DOCUMENT_TYPE_RESOLUTION = "Resolution"
    DOCUMENT_TYPE_CIRCULAR = "Circular"
    DOCUMENT_TYPE_ACTIVITY_REPORT = "Activity Report"
    DOCUMENT_TYPE_FINANCIAL = "Financial Document"
    DOCUMENT_TYPE_CERTIFICATE = "Certificate"
    DOCUMENT_TYPE_OTHER = "Other"

    DOCUMENT_TYPE_CHOICES = [
        (DOCUMENT_TYPE_CONSTITUTION, "Constitution"),
        (DOCUMENT_TYPE_BYLAWS, "By-Laws"),
        (DOCUMENT_TYPE_MINUTES, "Minutes of Meeting"),
        (DOCUMENT_TYPE_MEMORANDUM, "Memorandum"),
        (DOCUMENT_TYPE_OFFICE_ORDER, "Office Order"),
        (DOCUMENT_TYPE_RESOLUTION, "Resolution"),
        (DOCUMENT_TYPE_CIRCULAR, "Circular"),
        (DOCUMENT_TYPE_ACTIVITY_REPORT, "Activity Report"),
        (DOCUMENT_TYPE_FINANCIAL, "Financial Document"),
        (DOCUMENT_TYPE_CERTIFICATE, "Certificate"),
        (DOCUMENT_TYPE_OTHER, "Other"),
    ]

    document_id_PK = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPE_CHOICES)
    category = models.CharField(max_length=100, blank=True)
    keywords = models.CharField(max_length=500, blank=True)
    tags = models.CharField(max_length=500, blank=True)
    file_path = models.CharField(max_length=500)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(null=True, blank=True)
    file_type = models.CharField(max_length=50, blank=True)
    version = models.CharField(max_length=20, default="1.0")
    uploaded_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="uploaded_by_user_id_FK",
        related_name="uploaded_documents",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    retention_period = models.DateField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    is_public_visible = models.BooleanField(default=False)

    class Meta:
        db_table = "document"
        ordering = ["-uploaded_at"]


class Category(models.Model):
    category_id_PK = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    role = models.CharField(max_length=50, default='Secretary')  # Track which role created this category
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "category"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AnnouncementCategory(models.Model):
    category_id_PK = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "announcement_category"
        ordering = ["name"]

    def __str__(self):
        return self.name


class EventType(models.Model):
    event_type_id_PK = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "event_type"
        ordering = ["name"]

    def __str__(self):
        return self.name


class DocumentPin(models.Model):
    document_id_FK = models.ForeignKey(Document, on_delete=models.CASCADE, db_column="document_id_FK", related_name="pins")
    officer_id_FK = models.ForeignKey(OfficerUser, on_delete=models.CASCADE, db_column="officer_id_FK", related_name="document_pins")
    pinned_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "document_pin"
        unique_together = [["document_id_FK", "officer_id_FK"]]


class DocumentActivity(models.Model):
    activity_id = models.AutoField(primary_key=True)
    document_id_FK = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True, db_column="document_id_FK", related_name="activities")
    action = models.CharField(max_length=50)
    officer_id_FK = models.ForeignKey(OfficerUser, on_delete=models.SET_NULL, null=True, blank=True, db_column="officer_id_FK")
    officer_name = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "document_activity"
        ordering = ["-timestamp"]


class Minutes(models.Model):
    STATUS_DRAFT = "Draft"
    STATUS_PENDING = "Pending"
    STATUS_FINALIZED = "Finalized"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PENDING, "Pending"),
        (STATUS_FINALIZED, "Finalized"),
    ]

    minutes_id_PK = models.AutoField(primary_key=True)
    meeting_title = models.CharField(max_length=255)
    meeting_date = models.DateField()
    venue = models.CharField(max_length=255)
    attendees = models.TextField(blank=True)
    agenda = models.TextField(blank=True)
    minutes_content = models.TextField()
    prepared_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="prepared_by_user_id_FK",
        related_name="prepared_minutes",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    event_id_FK = models.ForeignKey(
        Event,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="event_id_FK",
        related_name="meeting_minutes",
    )
    document_id_FK = models.ForeignKey(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="document_id_FK",
        related_name="related_minutes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "minutes"
        ordering = ["-meeting_date"]


class Announcement(models.Model):
    CATEGORY_MEETING = "Meeting Notice"
    CATEGORY_EVENT = "Event Announcement"
    CATEGORY_GENERAL = "General Announcement"
    CATEGORY_UPDATE = "Organization Update"

    CATEGORY_CHOICES = [
        (CATEGORY_MEETING, "Meeting Notice"),
        (CATEGORY_EVENT, "Event Announcement"),
        (CATEGORY_GENERAL, "General Announcement"),
        (CATEGORY_UPDATE, "Organization Update"),
    ]

    announcement_id_PK = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField()
    attachment_path = models.CharField(max_length=500, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="announcements/%Y/%m/", null=True, blank=True)
    published_by_user_id_FK = models.ForeignKey(
        OfficerUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column="published_by_user_id_FK",
        related_name="published_announcements",
    )
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "announcement"
        ordering = ["-published_at"]


class CertificateSettings(models.Model):
    """Stores signature and certificate configuration for automatic generation"""
    settings_id_PK = models.AutoField(primary_key=True)
    president_name = models.CharField(max_length=255, help_text="Name of ISU-CAUFA President")
    president_position = models.CharField(max_length=255, default="ISU-CAUFA President")
    president_signature = models.ImageField(upload_to='signatures/', null=True, blank=True, help_text="Upload PNG with transparent background")
    secretary_name = models.CharField(max_length=255, help_text="Name of ISU-CAUFA Secretary")
    secretary_position = models.CharField(max_length=255, default="ISU CAUFA Secretary")
    secretary_signature = models.ImageField(upload_to='signatures/', null=True, blank=True, help_text="Upload PNG with transparent background")
    faculty_regent_name = models.CharField(max_length=255, blank=True, help_text="Name of Faculty Regent or Authorized Official")
    faculty_regent_position = models.CharField(max_length=255, default="Faculty Regent")
    faculty_regent_signature = models.ImageField(upload_to='signatures/', null=True, blank=True, help_text="Upload PNG with transparent background")
    organization_logo = models.ImageField(upload_to='logos/', null=True, blank=True, help_text="Organization logo for certificate")
    header_text = models.CharField(max_length=255, default="Republic of the Philippines")
    footer_text = models.TextField(blank=True, help_text="Optional footer text for certificate")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "certificate_settings"
        verbose_name_plural = "Certificate Settings"


class Certificate(models.Model):
    """Tracks generated certificates for events"""
    STATUS_PENDING = "Pending"
    STATUS_SENT = "Sent"
    STATUS_FAILED = "Failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    certificate_id_PK = models.AutoField(primary_key=True)
    certificate_number = models.CharField(max_length=50, unique=True)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        db_column="member_id_FK",
        related_name="certificates"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        db_column="event_id_FK",
        related_name="certificates"
    )
    pdf_file = models.FileField(upload_to='certificates/', null=True, blank=True)
    email_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "certificate"
        ordering = ["-generated_at"]
        unique_together = [['member', 'event']]


class Album(models.Model):
    album_id_PK = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_photo = models.ForeignKey(
        "Photo", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    event = models.ForeignKey(
        "Event", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="albums",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        OfficerUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_albums",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "album"
        ordering = ["-created_at"]


class Photo(models.Model):
    photo_id_PK = models.AutoField(primary_key=True)
    album = models.ForeignKey(
        Album, on_delete=models.CASCADE, related_name="photos",
    )
    image = models.ImageField(upload_to="gallery/%Y/%m/")
    caption = models.CharField(max_length=255, blank=True)
    is_featured = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey(
        OfficerUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="uploaded_photos",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "photo"
        ordering = ["-uploaded_at"]


class OfficerProfile(models.Model):
    """PIO-owned officer directory entry shown on the public Officers page.

    Independent from OfficerUser (dashboard login accounts managed by the
    President). The PIO manages these profiles directly.
    """

    officer_profile_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    position = models.CharField(max_length=100)
    category = models.CharField(
        max_length=50,
        choices=[
            ("Executive Officer", "Executive Officer"),
            ("Board of Directors", "Board of Directors"),
            ("Adviser", "Adviser"),
        ],
        default="Executive Officer",
    )
    department = models.CharField(max_length=255, null=True, blank=True)
    school_year = models.CharField(max_length=50, null=True, blank=True)
    term_start = models.DateField(null=True, blank=True)
    term_end = models.DateField(null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    facebook = models.URLField(null=True, blank=True)
    biography = models.TextField(null=True, blank=True)
    photo = models.ImageField(upload_to="officer_profiles/", null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("Active", "Active"), ("Inactive", "Inactive")],
        default="Active",
    )
    created_by = models.ForeignKey(
        OfficerUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_officer_profiles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "officer_profile"
        ordering = ["category", "position", "full_name"]


class NewsCategory(models.Model):
    """Categories for organizing News & Highlights content."""
    
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "news_category"
        ordering = ["order", "name"]
        verbose_name_plural = "News Categories"

    def __str__(self):
        return self.name


class NewsArticle(models.Model):
    """News & Highlights articles with full content, galleries, and videos."""
    
    news_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    category = models.ForeignKey(
        NewsCategory, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="articles",
    )
    summary = models.TextField(max_length=500, help_text="Brief summary for article cards")
    content = models.TextField(help_text="Full article content (supports HTML)")
    featured_image = models.ImageField(upload_to="news/%Y/%m/", null=True, blank=True)
    
    # Event information (optional)
    event_date = models.DateField(null=True, blank=True)
    event_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=255, blank=True)
    
    # Media
    video_url = models.URLField(blank=True, help_text="YouTube or other video platform URL")
    video_thumbnail = models.ImageField(upload_to="news/%Y/%m/", null=True, blank=True)
    
    # Publication settings
    is_featured = models.BooleanField(default=False, help_text="Show in featured news section")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Author tracking
    author = models.ForeignKey(
        OfficerUser, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="authored_news",
    )
    
    # Metadata
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "news_article"
        ordering = ["-published_at", "-created_at"]
        verbose_name = "News Article"
        verbose_name_plural = "News Articles"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or f"news-{self.news_id}"
            self.slug = base
            exists = NewsArticle.objects.filter(slug=self.slug).exists()
            suffix = 2
            while exists:
                self.slug = f"{base}-{suffix}"
                suffix += 1
                exists = NewsArticle.objects.filter(slug=self.slug).exists()
        super().save(*args, **kwargs)


class NewsGallery(models.Model):
    """Photo galleries associated with news articles."""
    
    gallery_id = models.AutoField(primary_key=True)
    article = models.ForeignKey(
        NewsArticle, on_delete=models.CASCADE, related_name="galleries",
    )
    caption = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="news/%Y/%m/")
    is_featured = models.BooleanField(default=False, help_text="Featured image in article gallery")
    order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_gallery"
        ordering = ["order", "-uploaded_at"]
        verbose_name_plural = "News Galleries"

    def __str__(self):
        return f"{self.article.title} - {self.caption or 'Untitled'}"


class HeroSlide(models.Model):
    """Standalone homepage hero carousel slides managed by the PIO."""

    hero_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    subtitle = models.TextField(max_length=500, blank=True, help_text="Short text shown on the slide")
    image = models.ImageField(upload_to="hero/%Y/%m/", null=True, blank=True)
    button_text = models.CharField(max_length=50, default="Read More")
    button_url = models.CharField(max_length=500, blank=True, help_text="Internal or external link for the slide button")
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Show on the homepage hero carousel")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hero_slide"
        ordering = ["sort_order", "-created_at"]
        verbose_name = "Hero Slide"
        verbose_name_plural = "Hero Slides"

    def __str__(self):
        return self.title

    def __str__(self):
        return self.full_name


