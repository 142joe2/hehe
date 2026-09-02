import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import hashlib
import hmac
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Sum
from django.db.utils import ProgrammingError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core_system import president_views, secretary_views

from core_system.auth_utils import create_access_session, hash_pin, verify_officer_password
from core_system.models import (
    AidTrackingPost,
    Contribution,
    DeathAid,
    Claimant,
    FundTransaction,
    GlobalAuditTrail,
    MedicalAid,
    Member,
    MemberLedger,
    MembershipFee,
    MonthlyDues,
    Notification,
    OfficerUser,
    SupportingProof,
    TransactionArchive,
    TransactionVerification,
)


def _create_zt_verified_session(officer, ip_address="127.0.0.1", device_info="tests"):
    session, token = create_access_session(
        officer=officer,
        ip_address=ip_address,
        device_info=device_info,
    )
    session.trusted_device = True
    session.device_info = ""
    policy = session.session_policy or {}
    policy["zt_verified_at"] = timezone.now().isoformat()
    session.session_policy = policy
    session.save()
    return session, token


class TreasurerApiClientMixin:
    def _login_treasurer(self):
        officer = OfficerUser.objects.create(
            full_name="Treasurer Test",
            username="treasurer_test",
            password_hash="unused",
            role="Treasurer",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer


class SecretaryAttendanceCheckinTests(TestCase):
    def test_secretary_checkin_accepts_valid_pin(self):
        officer = OfficerUser.objects.create(
            full_name="Secretary Test",
            username="secretary_checkin_test",
            password_hash="x",
            role="Secretary",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)

        member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-CHK-001",
            employment_status="Regular",
            membership_status="Active",
            date_joined=timezone.localdate(),
            email="member@example.com",
            pin_code=hash_pin("123456"),
        )

        request = RequestFactory().post(
            "/api/secretary/attendance/checkin/",
            data=json.dumps({"pin": "123456"}),
            content_type="application/json",
        )
        request.session = {
            "access_token": token,
            "officer_id": officer.user_id_PK,
            "role": officer.role,
        }

        response = secretary_views.secretary_attendance_checkin(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["member_name"], member.full_name)


class PublicRegistrationValidationTests(TestCase):
    def test_middle_initial_longer_than_one_character_is_rejected(self):
        response = self.client.post(
            "/api/public/membership-registration/",
            {
                "first_name": "John",
                "middle_initial": "AB",
                "last_name": "Doe",
                "username": "johndoe",
                "email": "john@example.com",
                "department": "Engineering",
                "position": "Software Engineer",
                "membership_category": "Permanent",
                "payment_method": "Bank Transfer",
                "amount": "100.00",
                "payment_date": "2026-07-23",
                "password": "TestPass123!",
                "confirm_password": "TestPass123!",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertIn("Middle Initial", response.json()["error"])

    def test_homepage_renders_with_missing_database_tables(self):
        from core_system.models import Announcement, Event, HeroSlide, NewsArticle

        with patch.object(Announcement.objects, "filter", side_effect=ProgrammingError("missing table")), \
             patch.object(Event.objects, "filter", side_effect=ProgrammingError("missing table")), \
             patch.object(NewsArticle.objects, "filter", side_effect=ProgrammingError("missing table")), \
             patch.object(HeroSlide.objects, "filter", side_effect=ProgrammingError("missing table")):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)


class MembershipFeeUploadTests(TreasurerApiClientMixin, TestCase):
    def setUp(self):
        self.member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-TEST-001",
            department="College of Education",
            position="Professor",
            contact_number="09170000000",
            email="member@example.com",
            employment_status="Active",
            membership_status="Permanent",
            member_type="EMP-TEST-001",
            date_joined=timezone.now().date(),
        )

    def test_membership_fee_upload_creates_proof(self):
        self._login_treasurer()
        img = SimpleUploadedFile("receipt.jpg", b"fake-image-content", content_type="image/jpeg")

        response = self.client.post(
            "/api/treasurer/membership-fees/add/",
            {
                "fee_member": str(self.member.member_id_PK),
                "fee_amount": "500.00",
                "fee_date": "2026-06-16",
                "fee_month": "2026-06",
                "fee_method": "OTC",
                "fee_ref": "RECV-1001",
                "fee_encoder": "Encoder",
                "fee_photo_file": img,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        fee = MembershipFee.objects.get(receipt_number="RECV-1001")
        proof = SupportingProof.objects.filter(
            content_type__model="membershipfee",
            object_id=fee.fee_id_PK,
        ).first()

        self.assertIsNotNone(proof)
        self.assertTrue(Path(proof.file.path).exists())
        self.assertEqual(proof.file_name, "receipt.jpg")
        self.assertEqual(proof.file_type, "image/jpeg")
        self.assertEqual(len(proof.file_sha256), 64)
        self.assertEqual(len(proof.row_signature), 64)

    def test_membership_fee_accepts_full_date_month_value(self):
        self._login_treasurer()
        response = self.client.post(
            "/api/treasurer/membership-fees/add/",
            {
                "fee_member": str(self.member.member_id_PK),
                "fee_amount": "500.00",
                "fee_date": "2026-06-16",
                "fee_month": "2026-06-01",
                "fee_method": "OTC",
                "fee_ref": "RECV-1003",
                "fee_encoder": "Encoder",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        fee = MembershipFee.objects.get(receipt_number="RECV-1003")

    def test_membership_fee_without_file_still_works(self):
        self._login_treasurer()
        response = self.client.post(
            "/api/treasurer/membership-fees/add/",
            {
                "fee_member": str(self.member.member_id_PK),
                "fee_amount": "500.00",
                "fee_date": "2026-06-16",
                "fee_month": "2026-06",
                "fee_method": "OTC",
                "fee_ref": "RECV-1002",
                "fee_encoder": "Encoder",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        fee = MembershipFee.objects.get(receipt_number="RECV-1002")
        self.assertFalse(SupportingProof.objects.exists())


class PresidentClaimSummaryTests(TestCase):
    def test_oversight_summary_counts_live_claim_statuses(self):
        officer = OfficerUser.objects.create(
            full_name="President Test",
            username="president_test",
            password_hash="unused",
            role="President",
            account_status="Active",
        )
        member = Member.objects.create(
            full_name="Sample Member",
            employee_id="EMP-PRES-001",
            department="CCSICT",
            position="Professor",
            contact_number="09170000000",
            email="sample@example.com",
            employment_status="Active",
            membership_status="Permanent",
            member_type="EMP-PRES-001",
            date_joined=timezone.now().date(),
        )
        claimant = Claimant.objects.create(
            member_id_FK=member,
            full_name="Claimant One",
            contact_number="09170000001",
            relationship_to_member="Spouse",
            relationship_group="member",
            authorization_status="Approved",
        )

        MedicalAid.objects.create(
            member_id_FK=member,
            request_date=timezone.now().date(),
            hospital_bill_amount="1200.00",
            claim_year=timezone.now().year,
            document_status="Verified",
            policy_record_status="Complete",
            validated_aid_amount="1200.00",
            status="Auditor Verified",
        )
        DeathAid.objects.create(
            member_id_FK=member,
            claimant_id_FK=claimant,
            claim_date=timezone.now().date(),
            claim_type="Death",
            date_of_death=timezone.now().date(),
            deceased_name="Sample Deceased",
            relationship_to_member="Spouse",
            relationship_group="member",
            funeral_location="City",
            benefit_amount="2500.00",
            bill_amount="2500.00",
            document_status="Verified",
            status="Approved",
        )
        MedicalAid.objects.create(
            member_id_FK=member,
            request_date=timezone.now().date(),
            hospital_bill_amount="800.00",
            claim_year=timezone.now().year,
            document_status="Verified",
            policy_record_status="Complete",
            validated_aid_amount="800.00",
            status="Completed",
        )
        DeathAid.objects.create(
            member_id_FK=member,
            claimant_id_FK=claimant,
            claim_date=timezone.now().date(),
            claim_type="Death",
            date_of_death=timezone.now().date(),
            deceased_name="Another Deceased",
            relationship_to_member="Parent",
            relationship_group="parent_child",
            funeral_location="City",
            benefit_amount="1800.00",
            bill_amount="1800.00",
            document_status="Verified",
            status="Released",
        )

        request = RequestFactory().get("/api/president/oversight/summary/")
        request.session = {"officer_id": officer.user_id_PK, "role": "President"}

        response = president_views.oversight_summary(request)
        data = json.loads(response.content)

        self.assertTrue(data["ok"])
        self.assertGreater(data["summary"]["claims"]["pending_medical"], 0)
        self.assertGreater(data["summary"]["claims"]["pending_death"], 0)
        self.assertGreater(data["summary"]["claims"]["total_released"], 0)


class RowSignatureIntegrityTests(TestCase):
    def test_row_signature_is_deterministic(self):
        officer = OfficerUser.objects.create(
            full_name="Treasurer Test",
            username="treasurer_test_sig",
            password_hash="unused",
            role="Treasurer",
            account_status="Active",
        )
        member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-SIG-001",
            department="College of Education",
            position="Professor",
            contact_number="09170000000",
            email="member@example.com",
            employment_status="Active",
            membership_status="Permanent",
            member_type="EMP-SIG-001",
            date_joined=timezone.now().date(),
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(b"test-bytes")
            tmp.flush()
            tmp_path = tmp.name

        try:
            digest = hashlib.sha256(b"test-bytes").hexdigest()
            sig1 = hmac.new(
                settings.SECRET_KEY.encode(),
                f"{digest}:{member.member_id_PK}:{settings.SECRET_KEY}".encode(),
                hashlib.sha256,
            ).hexdigest()
            sig2 = hmac.new(
                settings.SECRET_KEY.encode(),
                f"{digest}:{member.member_id_PK}:{settings.SECRET_KEY}".encode(),
                hashlib.sha256,
            ).hexdigest()
            self.assertEqual(sig1, sig2)
            self.assertEqual(len(sig1), 64)
        finally:
            os.unlink(tmp_path)


# ==========================================================================
# AID TRACKING POST TESTS
# ==========================================================================

class AuditorLoginMixin:
    def _login_auditor(self):
        officer = OfficerUser.objects.create(
            full_name="Auditor Test",
            username="auditor_test",
            password_hash="unused",
            role="Auditor",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer


class PresidentLoginMixin:
    def _login_president(self):
        officer = OfficerUser.objects.create(
            full_name="President Test",
            username="president_test",
            password_hash="unused",
            role="President",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer


class SelfEnrollmentTests(TestCase):
    def _login_president(self):
        officer = OfficerUser.objects.create(
            full_name="President Test",
            username="pres_self_enroll",
            password_hash="unused",
            role="President",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer

    def test_self_enrollment_creates_login_ready_officer_account(self):
        president = self._login_president()

        response = self.client.post(
            "/api/president/officers/self-enroll/",
            json.dumps({
                "employee_id": "EMP-SELF-001",
                "position": "Secretary",
                "contact_number": "09170000001",
                "email": "selfenroll@example.com",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

        officer = OfficerUser.objects.get(username="pres_self_enroll")
        self.assertEqual(officer.role, "Secretary")
        self.assertEqual(officer.email, "selfenroll@example.com")
        self.assertTrue(verify_officer_password(officer=officer, password_input="pres_self_enroll"))

        member = Member.objects.get(employee_id="EMP-SELF-001")
        self.assertEqual(member.position, "Secretary")
        self.assertEqual(member.officer_user_id_FK.user_id_PK, president.user_id_PK)


class MonthlyDuesWorkflowTests(TestCase):
    def setUp(self):
        self.member = Member.objects.create(
            full_name="Workflow Member",
            employee_id="EMP-WF-001",
            department="Finance",
            position="Staff",
            membership_status="Active",
            employment_status="Active",
            member_type="REG",
            date_joined=timezone.now().date(),
        )

    def _login_president(self):
        officer = OfficerUser.objects.create(
            full_name="President Test",
            username="pres_workflow_" + str(timezone.now().timestamp()),
            password_hash="unused",
            role="President",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer

    def test_president_approval_marks_monthly_dues_terminal(self):
        officer = self._login_president()
        dues = MonthlyDues.objects.create(
            member_id_FK=self.member,
            month_covered="2026-07",
            amount=50,
            payment_method="OTC",
            payment_status="Pending",
            treasurer_status="Treasurer Verified",
            auditor_status="Auditor Verified",
            president_status="Pending President Approval",
            recorded_by_user_id_FK=officer,
        )
        TransactionVerification.objects.create(
            table_name="monthly_dues",
            record_id=dues.dues_id_PK,
            verification_status="Auditor Verified",
        )

        response = self.client.post(
            "/api/president/monthly-dues/approve/",
            json.dumps({"dues_id": dues.dues_id_PK, "action": "approve", "remarks": "OK"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        dues.refresh_from_db()
        self.assertEqual(dues.president_status, "President Approved")
        self.assertEqual(dues.payment_status, "Full Payment")
        self.assertEqual(dues.treasurer_status, "Treasurer Verified")
        self.assertNotEqual(dues.treasurer_status, "Pending Treasurer Review")

    def test_member_unpaid_months_excludes_months_with_existing_dues_records(self):
        member = self.member
        MonthlyDues.objects.create(
            member_id_FK=member,
            month_covered="2026-07",
            amount=50,
            payment_method="OTC",
            payment_status="Pending",
            treasurer_status="Pending Treasurer Review",
            recorded_by_user_id_FK=OfficerUser.objects.create(
                full_name="Treasurer",
                username="treasurer_unpaid_" + str(timezone.now().timestamp()),
                password_hash="unused",
                role="Treasurer",
                account_status="Active",
            ),
        )

        officer = OfficerUser.objects.create(
            full_name="Member Session",
            username="member_session_" + str(timezone.now().timestamp()),
            password_hash="unused",
            role="Member",
            account_status="Active",
        )
        member.officer_user_id_FK = officer
        member.save(update_fields=["officer_user_id_FK"])

        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = "Member"
        test_session.save()

        response = self.client.get("/api/member/unpaid-months/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotIn("2026-07", [item["month"] for item in payload["unpaid_months"]])
        self.assertIn("2026-07", payload["covered_months"])


class AidTrackingPostCreationTests(TestCase):
    """Tests that posts and contributions are auto-created on presidential approval."""

    def setUp(self):
        self.member = Member.objects.create(
            full_name="Aid Recipient",
            employee_id="EMP-AID-001",
            department="IT",
            position="Staff",
            membership_status="Active",
            employment_status="Active",
            member_type="REG",
            date_joined=timezone.now().date(),
        )
        self.active_member = Member.objects.create(
            full_name="Paying Member",
            employee_id="EMP-PAY-001",
            department="Finance",
            position="Staff",
            membership_status="Active",
            employment_status="Active",
            member_type="REG",
            date_joined=timezone.now().date(),
        )

    def _login_president(self):
        officer = OfficerUser.objects.create(
            full_name="President Test",
            username="pres_test_" + str(timezone.now().timestamp()),
            password_hash="unused",
            role="President",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer

    def test_medical_aid_approval_creates_post_and_contributions(self):
        officer = self._login_president()

        med = MedicalAid.objects.create(
            member_id_FK=self.member,
            request_date=timezone.now().date(),
            requested_amount=20000,
            hospital_name="Test Hospital",
            hospital_bill_amount=25000,
            claim_year=2026,
            document_status="Complete",
            policy_record_status="Verified",
            validated_aid_amount=20000,
            status="Auditor Verified",
        )

        response = self.client.post(
            "/api/aids/presidential-decision/",
            json.dumps({
                "target_id": "medical-" + str(med.medical_aid_id_PK),
                "decision": "Approved",
                "approved_amount": 20000,
                "remarks": "Approved",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        posts = AidTrackingPost.objects.filter(aid_type="medical_aid")
        self.assertEqual(posts.count(), 1)

        post = posts.first()
        self.assertEqual(post.total_expected, 200)
        self.assertEqual(post.total_collected, 0)

        contributions = Contribution.objects.filter(aid_tracking_post_id_FK=post)
        self.assertEqual(contributions.count(), 2)

        for c in contributions:
            self.assertEqual(float(c.expected_amount), 100)
            self.assertEqual(c.status, "NOT_PAID")

    def test_death_aid_approval_creates_post_with_correct_amount(self):
        officer = self._login_president()

        claimant = Claimant.objects.create(
            member_id_FK=self.member,
            full_name="Claimant Person",
            contact_number="09170000001",
            relationship_to_member="Spouse",
            authorization_status="Authorized",
        )

        death = DeathAid.objects.create(
            member_id_FK=self.member,
            claimant_id_FK=claimant,
            claim_date=timezone.now().date(),
            claim_type="spouse",
            deceased_name="Deceased Person",
            relationship_to_member="spouse",
            benefit_amount=50000,
            document_status="Complete",
            status="Auditor Verified",
        )

        response = self.client.post(
            "/api/aids/presidential-decision/",
            json.dumps({
                "target_id": "death-" + str(death.death_aid_id_PK),
                "decision": "Approved",
                "approved_amount": 50000,
                "remarks": "Approved",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        posts = AidTrackingPost.objects.filter(aid_type="death_aid")
        self.assertEqual(posts.count(), 1)

        contributions = Contribution.objects.filter(aid_tracking_post_id_FK=posts.first())
        self.assertEqual(contributions.count(), 2)

        for c in contributions:
            self.assertEqual(float(c.expected_amount), 300)


class AidTrackingReadTests(TestCase):
    """Tests that auditor can view posts and member contributions."""

    def setUp(self):
        self.member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-001",
            department="IT",
            position="Staff",
            membership_status="Active",
            employment_status="Active",
            member_type="REG",
            date_joined=timezone.now().date(),
        )
        self.archive = TransactionArchive.objects.create(
            transaction_type="medical_aid",
            record_id=1,
            member_id_FK=self.member,
            member_name=self.member.full_name,
            amount=10000,
            validated_amount=10000,
            status="Approved",
            verified_at=timezone.now(),
        )
        self.post = AidTrackingPost.objects.create(
            archive_id_FK=self.archive,
            aid_type="medical_aid",
            target_month="2026-01",
            total_expected=500,
            total_collected=200,
            is_active=True,
        )
        self.contribution = Contribution.objects.create(
            aid_tracking_post_id_FK=self.post,
            member_id_FK=self.member,
            expected_amount=100,
            paid_amount=100,
            payment_date=timezone.now().date(),
            status="PAID",
        )

    def _login_auditor(self):
        officer = OfficerUser.objects.create(
            full_name="Auditor Test",
            username="aud_rd_" + str(timezone.now().timestamp()),
            password_hash="unused",
            role="Auditor",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer

    def test_list_posts(self):
        self._login_auditor()
        response = self.client.get("/api/auditor/approved-aid-posts/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["posts"]), 1)
        self.assertEqual(data["posts"][0]["aid_type"], "medical_aid")
        self.assertEqual(data["posts"][0]["member_name"], "Test Member")

    def test_view_members_for_post(self):
        self._login_auditor()
        response = self.client.get(f"/api/auditor/aid-post-members/{self.post.post_id_PK}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["members"]), 1)
        self.assertEqual(data["members"][0]["status"], "PAID")
        self.assertEqual(data["members"][0]["member_name"], "Test Member")

    def test_inactive_post_not_returned(self):
        self._login_auditor()
        self.post.is_active = False
        self.post.save()

        response = self.client.get(f"/api/auditor/aid-post-members/{self.post.post_id_PK}/")
        self.assertEqual(response.status_code, 404)


class AidTrackingActionTests(TestCase):
    """Tests that auditor can mark PAID, SKIPPED, and send notifications."""

    def setUp(self):
        self.member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-002",
            department="HR",
            position="Staff",
            membership_status="Active",
            employment_status="Active",
            member_type="REG",
            date_joined=timezone.now().date(),
        )
        self.archive = TransactionArchive.objects.create(
            transaction_type="death_aid",
            record_id=1,
            member_id_FK=self.member,
            member_name=self.member.full_name,
            amount=50000,
            validated_amount=50000,
            status="Approved",
        )
        self.post = AidTrackingPost.objects.create(
            archive_id_FK=self.archive,
            aid_type="death_aid",
            target_month="2026-06",
            total_expected=1000,
            total_collected=0,
            is_active=True,
        )
        self.contribution = Contribution.objects.create(
            aid_tracking_post_id_FK=self.post,
            member_id_FK=self.member,
            expected_amount=500,
            paid_amount=0,
            status="NOT_PAID",
        )

    def _login_auditor(self):
        officer = OfficerUser.objects.create(
            full_name="Auditor Test",
            username="aud_act_" + str(timezone.now().timestamp()),
            password_hash="unused",
            role="Auditor",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer

    def test_mark_as_paid(self):
        self._login_auditor()
        response = self.client.post(
            "/api/auditor/aid-post-member-pay/",
            {"contribution_id": str(self.contribution.contribution_id_PK)},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, "PAID")
        self.assertEqual(float(self.contribution.paid_amount), 500)

        self.post.refresh_from_db()
        self.assertEqual(float(self.post.total_collected), 500)

    def test_mark_as_skipped(self):
        self._login_auditor()
        response = self.client.post(
            "/api/auditor/aid-post-member-skip/",
            {"contribution_id": str(self.contribution.contribution_id_PK), "notes": "On leave"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])

        self.contribution.refresh_from_db()
        self.assertEqual(self.contribution.status, "SKIPPED")
        self.assertTrue(self.contribution.is_manually_overridden)
        self.assertEqual(self.contribution.notes, "On leave")

    def test_unauthenticated_requests_rejected(self):
        response = self.client.get("/api/auditor/approved-aid-posts/")
        self.assertNotEqual(response.status_code, 200)


class FullWorkflowSmokeTests(TestCase):
    """End-to-end smoke tests for the complete CAUFA portal workflow."""

    # ------------------------------------------------------------------
    # shared helpers
    # ------------------------------------------------------------------
    def _create_officer(self, role, suffix=""):
        return OfficerUser.objects.create(
            full_name=f"{role} {suffix}",
            username=f"{role.lower()}_{suffix}",
            password_hash="unused",
            role=role,
            account_status="Active",
        )

    def _login(self, officer):
        session, token = _create_zt_verified_session(officer, device_info="smoke_test")
        s = self.client.session
        s["access_token"] = token
        s["officer_id"] = officer.user_id_PK
        s["role"] = officer.role
        s.save()
        return officer

    def _create_member(self, tag):
        return Member.objects.create(
            full_name=f"SmokeTest Member {tag}",
            employee_id=f"SMK-{tag}-001",
            department="College of Education",
            position="Professor",
            contact_number="09170000000",
            email="smoketest@example.com",
            employment_status="Active",
            membership_status="Permanent",
            member_type=f"SMK-{tag}-001",
            date_joined=timezone.now().date(),
        )

    # ------------------------------------------------------------------
    # 1) Full membership fee flow: Treasurer → Auditor → President
    # ------------------------------------------------------------------
    def test_membership_fee_full_flow(self):
        trez = self._create_officer("Treasurer", "MF1")
        self._login(trez)
        member = self._create_member("MF1")

        # Treasurer adds fee
        resp = self.client.post("/api/treasurer/membership-fees/add/", {
            "fee_member": str(member.member_id_PK),
            "fee_amount": "500.00",
            "fee_date": "2026-07-03",
            "fee_month": "2026-07",
            "fee_method": "OTC",
            "fee_ref": "SMK-RECV-MF1",
            "fee_encoder": "Encoder",
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertTrue(resp.json()["ok"])
        fee = MembershipFee.objects.get(receipt_number="SMK-RECV-MF1")

        # Auditor verifies
        aud = self._create_officer("Auditor", "MF1")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-membership-fee/", {
            "mfAuditID": str(fee.fee_id_PK),
            "mfAuditResult": "Verified",
            "mfAuditRemarks": "Looks good",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        tv = TransactionVerification.objects.get(table_name="membership_fee", record_id=fee.fee_id_PK)
        self.assertEqual(tv.verification_status, "Auditor Verified")

        # President approves
        prez = self._create_officer("President", "MF1")
        self._login(prez)
        resp = self.client.post("/api/payments/presidential-decision/",
            {"target_id": str(tv.verification_id), "decision": "Approved", "remarks": "Approved"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Approved")

        # Audit trail entry exists
        self.assertTrue(
            GlobalAuditTrail.objects.filter(table_name="membership_fee", record_id=fee.fee_id_PK).exists()
        )

    # ------------------------------------------------------------------
    # 2) Full monthly dues flow: Treasurer → Auditor → President
    # ------------------------------------------------------------------
    def test_monthly_dues_full_flow(self):
        trez = self._create_officer("Treasurer", "MD1")
        self._login(trez)
        member = self._create_member("MD1")

        resp = self.client.post("/api/treasurer/monthly-dues/otc/add/", {
            "otc_member": str(member.member_id_PK),
            "otc_month": "2026-07",
            "otc_amount": "50.00",
            "otc_date": "2026-07-03",
            "otc_method": "OTC",
            "otc_ref": "SMK-MD1",
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertTrue(resp.json()["ok"])
        dues = MonthlyDues.objects.get(receipt_number="SMK-MD1")

        # Treasurer approves (forwards to Auditor) before Auditor can verify
        resp = self.client.post("/api/treasurer/monthly-dues/approve/",
            {"dues_id": dues.dues_id_PK, "action": "approve", "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        tv = TransactionVerification.objects.get(table_name="monthly_dues", record_id=dues.dues_id_PK)
        self.assertEqual(tv.verification_status, "Pending Auditor Review")

        aud = self._create_officer("Auditor", "MD1")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-payment/", {
            "pAuditID": str(dues.dues_id_PK),
            "pAuditResult": "Verified",
            "pAuditRemarks": "OK",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        tv = TransactionVerification.objects.get(table_name="monthly_dues", record_id=dues.dues_id_PK)
        self.assertEqual(tv.verification_status, "Auditor Verified")

        prez = self._create_officer("President", "MD1")
        self._login(prez)
        resp = self.client.post("/api/payments/presidential-decision/",
            {"target_id": str(tv.verification_id), "decision": "Approved", "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Approved")

    # ------------------------------------------------------------------
    # 3) Full medical aid flow: Treasurer → Auditor → President
    # ------------------------------------------------------------------
    def test_medical_aid_full_flow(self):
        trez = self._create_officer("Treasurer", "MA1")
        self._login(trez)
        member = self._create_member("MA1")

        resp = self.client.post("/api/treasurer/medical-aid/add/", {
            "med_member": str(member.member_id_PK),
            "med_date": "2026-07-03",
            "med_req_amount": "20000",
            "med_hospital": "SmokeTest Hospital",
            "med_bill": "25000",
            "med_validation": "Verified",
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertTrue(resp.json()["ok"])
        med = MedicalAid.objects.filter(member_id_FK=member).latest("medical_aid_id_PK")

        aud = self._create_officer("Auditor", "MA1")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-aid/", {
            "aAuditID": f"medical-{med.medical_aid_id_PK}",
            "aAuditResult": "Verified",
            "aAuditRemarks": "OK",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        tv = TransactionVerification.objects.get(table_name="medical_aid", record_id=med.medical_aid_id_PK)
        self.assertEqual(tv.verification_status, "Auditor Verified")

        prez = self._create_officer("President", "MA1")
        self._login(prez)
        resp = self.client.post("/api/aids/presidential-decision/",
            {"target_id": f"medical-{med.medical_aid_id_PK}", "decision": "Approved", "approved_amount": 20000, "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Approved")

    # ------------------------------------------------------------------
    # 4) Death aid full flow
    # ------------------------------------------------------------------
    def test_death_aid_full_flow(self):
        trez = self._create_officer("Treasurer", "DA1")
        self._login(trez)
        member = self._create_member("DA1")

        resp = self.client.post("/api/treasurer/death-aid/add/", {
            "death_member": str(member.member_id_PK),
            "death_deceased": "Deceased Spouse",
            "death_rel": "spouse",
            "death_rel_group": "immediate",
            "death_type": "spouse",
            "death_claimant": "Claimant Person",
            "death_contact": "09170000001",
            "death_date": "2026-07-03",
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertTrue(resp.json()["ok"])
        death = DeathAid.objects.filter(member_id_FK=member).latest("death_aid_id_PK")
        self.assertEqual(death.benefit_amount, 300)  # spouse maps to death_aid_spouse (₱300)
        self.assertEqual(death.relationship_group, "immediate")

        aud = self._create_officer("Auditor", "DA1")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-aid/", {
            "aAuditID": f"death-{death.death_aid_id_PK}",
            "aAuditResult": "Verified",
            "aAuditRemarks": "OK",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        tv = TransactionVerification.objects.get(table_name="death_aid", record_id=death.death_aid_id_PK)
        self.assertEqual(tv.verification_status, "Auditor Verified")

        prez = self._create_officer("President", "DA1")
        self._login(prez)
        resp = self.client.post("/api/aids/presidential-decision/",
            {"target_id": f"death-{death.death_aid_id_PK}", "decision": "Approved", "approved_amount": 50000, "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Approved")

    # ------------------------------------------------------------------
    # 5) Resubmission loop: Treasurer → Auditor (Return) → Treasurer (Resubmit) → Auditor (Verify)
    # ------------------------------------------------------------------
    def test_resubmission_loop(self):
        trez = self._create_officer("Treasurer", "RS1")
        self._login(trez)
        member = self._create_member("RS1")

        resp = self.client.post("/api/treasurer/membership-fees/add/", {
            "fee_member": str(member.member_id_PK),
            "fee_amount": "500.00",
            "fee_date": "2026-07-03",
            "fee_month": "2026-07",
            "fee_method": "OTC",
            "fee_ref": "SMK-RECV-RS1",
            "fee_encoder": "Encoder",
        })
        self.assertTrue(resp.json()["ok"])
        fee = MembershipFee.objects.get(receipt_number="SMK-RECV-RS1")

        # Auditor returns it
        aud = self._create_officer("Auditor", "RS1")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-membership-fee/", {
            "mfAuditID": str(fee.fee_id_PK),
            "mfAuditResult": "Returned",
            "mfAuditRemarks": "Missing receipt",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        tv = TransactionVerification.objects.get(table_name="membership_fee", record_id=fee.fee_id_PK)
        self.assertEqual(tv.verification_status, "Returned for Revision")
        self.assertEqual(tv.returned_by_auditor_id_FK, aud)
        self.assertEqual(tv.returned_reason, "Missing receipt")
        self.assertEqual(tv.return_count, 1)

        # Treasurer resubmits
        self._login(trez)
        resp = self.client.post(f"/api/treasurer/resubmit/membership_fee/{fee.fee_id_PK}/", {
            "fee_ref": "SMK-RECV-RS1",
            "fee_encoder": "Encoder",
            "fee_method": "OTC",
            "fee_date": "2026-07-03",
            "fee_month": "2026-07",
            "fee_status": "Pending",
            "fee_amount": "500.00",
            "same_auditor": "true",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        data = resp.json()
        self.assertTrue(data.get("ok") or data.get("success"), data)
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Pending")

        # Auditor verifies again
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-membership-fee/", {
            "mfAuditID": str(fee.fee_id_PK),
            "mfAuditResult": "Verified",
            "mfAuditRemarks": "Now OK",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Auditor Verified")
        # return_count should still be 1
        self.assertEqual(tv.return_count, 1)

    # ------------------------------------------------------------------
    # 6) Batch operations
    # ------------------------------------------------------------------
    def test_auditor_batch_verify(self):
        trez = self._create_officer("Treasurer", "BT1")
        self._login(trez)
        member = self._create_member("BT1")

        # Create 3 fees
        ids = []
        for i in range(3):
            resp = self.client.post("/api/treasurer/membership-fees/add/", {
                "fee_member": str(member.member_id_PK),
                "fee_amount": f"{500 + i * 100}.00",
                "fee_date": "2026-07-03",
                "fee_month": "2026-07",
                "fee_method": "OTC",
                "fee_ref": f"SMK-BATCH-{i}",
                "fee_encoder": "Encoder",
            })
            self.assertTrue(resp.json()["ok"])
            fee = MembershipFee.objects.get(receipt_number=f"SMK-BATCH-{i}")
            ids.append(fee.fee_id_PK)

        # Auditor batch verifies
        aud = self._create_officer("Auditor", "BT1")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-membership-fee/batch/",
            json.dumps({"ids": ids, "result": "Verified", "remarks": "Batch OK"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        data = resp.json()
        self.assertTrue(data.get("ok") or data.get("success"), data)

        # All 3 should be Auditor Verified
        for fid in ids:
            tv = TransactionVerification.objects.get(table_name="membership_fee", record_id=fid)
            self.assertEqual(tv.verification_status, "Auditor Verified")

        # President batch approves
        prez = self._create_officer("President", "BT1")
        self._login(prez)
        tv_ids = list(
            TransactionVerification.objects.filter(table_name="membership_fee", record_id__in=ids)
            .values_list("verification_id", flat=True)
        )
        resp = self.client.post("/api/payments/presidential-decision/batch/",
            {"ids": tv_ids, "decision": "Approved", "remarks": "Batch approve"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        for fid in ids:
            tv = TransactionVerification.objects.get(table_name="membership_fee", record_id=fid)
            self.assertEqual(tv.verification_status, "Approved")

    # ------------------------------------------------------------------
    # 7) Bulk salary deduction preview + process
    # ------------------------------------------------------------------
    def test_salary_bulk_preview(self):
        trez = self._create_officer("Treasurer", "BP1")
        self._login(trez)
        m1 = self._create_member("BP1")
        m2 = self._create_member("BP2")
        m3 = self._create_member("BP3")
        m3.membership_status = "retired"
        m3.save()

        resp = self.client.post("/api/treasurer/monthly-dues/salary/bulk-preview/",
            {"sal_month": "2026-07"})
        self.assertEqual(resp.status_code, 200, resp.json())
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["month"], "2026-07")
        self.assertEqual(data["total_active"], 2)
        self.assertEqual(data["already_processed"], 0)
        member_ids = [m["member_id"] for m in data["members"]]
        self.assertIn(m1.member_id_PK, member_ids)
        self.assertIn(m2.member_id_PK, member_ids)
        self.assertNotIn(m3.member_id_PK, member_ids)
        for m in data["members"]:
            self.assertTrue(m["default_checked"])

    def test_salary_bulk_process(self):
        trez = self._create_officer("Treasurer", "BP2")
        self._login(trez)
        m1 = self._create_member("BP4")
        m2 = self._create_member("BP5")

        resp = self.client.post("/api/treasurer/monthly-dues/salary/bulk-process/", {
            "sal_month": "2026-07",
            "batch_ref": "TXN-BP2-0726",
            "summary": "Payroll batch test",
            "member_ids": json.dumps([m1.member_id_PK, m2.member_id_PK]),
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["processed"], 2)
        self.assertEqual(data["skipped"], 0)
        self.assertEqual(data["batch_ref"], "ISU-CAUFA-26-1")

        for m in [m1, m2]:
            dues = MonthlyDues.objects.get(member_id_FK=m, month_covered="2026-07")
            self.assertEqual(dues.payment_method, "Salary Deduction")
            self.assertEqual(dues.remittance_reference, "ISU-CAUFA-26-1")
            self.assertEqual(dues.deduction_batch_reference, "Payroll batch test")
            tv = TransactionVerification.objects.get(table_name="monthly_dues", record_id=dues.dues_id_PK)
            self.assertEqual(tv.verification_status, "Pending Treasurer Review")

    def test_salary_bulk_skips_duplicates(self):
        trez = self._create_officer("Treasurer", "BP3")
        self._login(trez)
        m1 = self._create_member("BP6")
        m2 = self._create_member("BP7")

        # Process first time
        resp = self.client.post("/api/treasurer/monthly-dues/salary/bulk-process/", {
            "sal_month": "2026-07",
            "batch_ref": "TXN-BP3A",
            "member_ids": json.dumps([m1.member_id_PK, m2.member_id_PK]),
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertEqual(resp.json()["processed"], 2)

        # Process same month again — app now rejects duplicate months with 409
        resp = self.client.post("/api/treasurer/monthly-dues/salary/bulk-process/", {
            "sal_month": "2026-07",
            "batch_ref": "TXN-BP3B",
            "member_ids": json.dumps([m1.member_id_PK, m2.member_id_PK]),
        })
        self.assertEqual(resp.status_code, 409, resp.json())
        self.assertFalse(resp.json()["ok"])

        # Still only 2 records total
        self.assertEqual(MonthlyDues.objects.filter(month_covered="2026-07", payment_method="Salary Deduction").count(), 2)

    def test_salary_bulk_creates_member_facing_records(self):
        trez = self._create_officer("Treasurer", "BP9")
        self._login(trez)
        member = self._create_member("BP9")

        resp = self.client.post("/api/treasurer/monthly-dues/salary/bulk-process/", {
            "sal_month": "2026-09",
            "summary": "Member-facing notice test",
            "member_ids": json.dumps([member.member_id_PK]),
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertTrue(resp.json()["ok"])

        dues = MonthlyDues.objects.get(member_id_FK=member, month_covered="2026-09")

        # The member-facing payment notification should not be created until the
        # payment is fully approved by the President.
        self.assertFalse(
            Notification.objects.filter(
                recipient_type="member",
                recipient_id=member.member_id_PK,
                category="payment",
            ).exists()
        )

        # Regression (C3): the MemberLedger entry is NOT written at the Treasurer
        # record stage. Money was withheld, but the ledger entry is written once —
        # at President approval — so MemberLedger and FundTransaction always agree.
        self.assertFalse(
            MemberLedger.objects.filter(
                member_id_FK=member,
                reference_id=dues.dues_id_PK,
                reference_type="MonthlyDues",
            ).exists()
        )
        self.assertFalse(
            FundTransaction.objects.filter(
                source_type="monthly_dues",
                source_id=dues.dues_id_PK,
            ).exists()
        )

        # Drive the record through the rest of the chain: Treasurer → Auditor → President.
        resp = self.client.post("/api/treasurer/monthly-dues/approve/",
            {"dues_id": dues.dues_id_PK, "action": "approve", "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())

        aud = self._create_officer("Auditor", "BP9")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-payment/", {
            "pAuditID": str(dues.dues_id_PK),
            "pAuditResult": "Verified",
            "pAuditRemarks": "OK",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        prez = self._create_officer("President", "BP9")
        self._login(prez)
        tv = TransactionVerification.objects.get(table_name="monthly_dues", record_id=dues.dues_id_PK)
        resp = self.client.post("/api/payments/presidential-decision/",
            {"target_id": str(tv.verification_id), "decision": "Approved", "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())

        # At President approval both the FundTransaction and the MemberLedger are
        # created together and exactly once (idempotent (C3)).
        self.assertTrue(
            FundTransaction.objects.filter(
                source_type="monthly_dues",
                source_id=dues.dues_id_PK,
            ).exists()
        )
        self.assertTrue(
            MemberLedger.objects.filter(
                member_id_FK=member,
                reference_id=dues.dues_id_PK,
                reference_type="MonthlyDues",
            ).exists()
        )

    def test_salary_bulk_full_workflow(self):
        """Complete lifecycle: bulk create → auditor verify → president approve."""
        trez = self._create_officer("Treasurer", "BP8")
        self._login(trez)
        m1 = self._create_member("BP8")

        resp = self.client.post("/api/treasurer/monthly-dues/salary/bulk-process/", {
            "sal_month": "2026-08",
            "batch_ref": "TXN-BP8-0826",
            "summary": "Full workflow test",
            "member_ids": json.dumps([m1.member_id_PK]),
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        self.assertEqual(resp.json()["processed"], 1)
        self.assertEqual(resp.json()["batch_ref"], "ISU-CAUFA-26-1")

        dues = MonthlyDues.objects.get(member_id_FK=m1, month_covered="2026-08")
        self.assertEqual(dues.remittance_reference, "ISU-CAUFA-26-1")

        # Treasurer approves (forwards to Auditor) before Auditor can verify
        resp = self.client.post("/api/treasurer/monthly-dues/approve/",
            {"dues_id": dues.dues_id_PK, "action": "approve", "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        tv = TransactionVerification.objects.get(table_name="monthly_dues", record_id=dues.dues_id_PK)
        self.assertEqual(tv.verification_status, "Pending Auditor Review")

        # Auditor verifies
        aud = self._create_officer("Auditor", "BP8")
        self._login(aud)
        resp = self.client.post("/api/auditor/verify-payment/", {
            "pAuditID": str(dues.dues_id_PK),
            "pAuditResult": "Verified",
            "pAuditRemarks": "Bulk OK",
        })
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Auditor Verified")

        # President approves
        prez = self._create_officer("President", "BP8")
        self._login(prez)
        resp = self.client.post("/api/payments/presidential-decision/",
            {"target_id": str(tv.verification_id), "decision": "Approved", "remarks": "OK"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        tv.refresh_from_db()
        self.assertEqual(tv.verification_status, "Approved")


class RemittanceDoubleCountRegressionTests(TestCase):
    """Regression: recording a salary-deduction remittance must NOT book a
    FundTransaction inflow. The remittance is the same money as the member
    contributions, which are booked at Auditor verify (source_type
    'contribution'). Previously an extra 'salary_deduction_remittance' inflow
    double-counted the funds."""

    def setUp(self):
        self.member = Member.objects.create(
            full_name="Test Member",
            employee_id="EMP-REM-001",
            department="HR",
            position="Staff",
            membership_status="Active",
            employment_status="Active",
            member_type="REG",
            date_joined=timezone.now().date(),
        )
        self.archive = TransactionArchive.objects.create(
            transaction_type="death_aid",
            record_id=1,
            member_id_FK=self.member,
            member_name=self.member.full_name,
            amount=20000,
            validated_amount=20000,
            status="Approved",
        )
        self.post = AidTrackingPost.objects.create(
            archive_id_FK=self.archive,
            aid_type="death_aid",
            target_month="2026-06",
            total_expected=20000,
            total_collected=0,
            is_active=True,
        )

    def _login_treasurer(self):
        officer = OfficerUser.objects.create(
            full_name="Treasurer Test",
            username="trez_remit_" + str(timezone.now().timestamp()),
            password_hash="unused",
            role="Treasurer",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(officer)
        test_session = self.client.session
        test_session["access_token"] = token
        test_session["officer_id"] = officer.user_id_PK
        test_session["role"] = officer.role
        test_session.save()
        return officer

    def test_recording_remittance_creates_no_fund_transaction(self):
        self._login_treasurer()
        response = self.client.post(
            "/api/treasurer/aid-post-record-remittance/",
            {
                "post_id": str(self.post.post_id_PK),
                "remitted_amount": "20000",
                "remittance_reference": "BATCH-REM-001",
                "remitted_date": "2026-06-30",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()
        self.assertTrue(data["ok"])

        # The remittance is a deposit reference only — no fund inflow is booked.
        self.assertEqual(
            FundTransaction.objects.filter(
                source_type="salary_deduction_remittance",
            ).count(),
            0,
            "Recording a remittance must not create a FundTransaction inflow.",
        )

        # The post's remittance fields are still persisted.
        self.post.refresh_from_db()
        self.assertEqual(float(self.post.deduction_remitted_amount), 20000)
        self.assertEqual(self.post.deduction_remittance_reference, "BATCH-REM-001")
        self.assertIsNotNone(self.post.deduction_remitted_date)

    def test_end_to_end_net_is_zero(self):
        """Two members pay ₱10,000 each, an equal remittance is recorded,
        then the full amount is disbursed. Inflow must match outflow (net 0)."""
        self._login_treasurer()

        member2 = Member.objects.create(
            full_name="Member Two",
            employee_id="EMP-REM-002",
            department="HR",
            position="Staff",
            membership_status="Active",
            employment_status="Active",
            member_type="REG",
            date_joined=timezone.now().date(),
        )
        for m, amt in ((self.member, 10000), (member2, 10000)):
            Contribution.objects.create(
                aid_tracking_post_id_FK=self.post,
                member_id_FK=m,
                expected_amount=amt,
                paid_amount=amt,
                status="RECORDED",
            )

        # Remittance reference only — no inflow booked (the fix).
        response = self.client.post(
            "/api/treasurer/aid-post-record-remittance/",
            {
                "post_id": str(self.post.post_id_PK),
                "remitted_amount": "20000",
                "remittance_reference": "BATCH-REM-002",
                "remitted_date": "2026-06-30",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertFalse(
            FundTransaction.objects.filter(
                source_type="salary_deduction_remittance"
            ).exists()
        )

        # Upload the salary deduction sheet (required before Auditor can verify).
        response = self.client.post(
            "/api/treasurer/aid-post-upload-deduction-sheet/",
            {
                "post_id": str(self.post.post_id_PK),
                "batch_reference": "BATCH-REM-002",
                "payroll_period": "2026-06",
                "deduction_sheet": SimpleUploadedFile(
                    "deduction_sheet.xlsx", b"fake-sheet", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            },
        )
        self.assertEqual(response.status_code, 200, response.json())

        # The Auditor verify endpoint only accepts posts in pending_auditor state.
        self.post.finish_status = "pending_auditor"
        self.post.save(update_fields=["finish_status"])

        # Auditor verify books the per-contribution inflows (single source of truth).
        audit_officer = OfficerUser.objects.create(
            full_name="Auditor Test",
            username="aud_remit_" + str(timezone.now().timestamp()),
            password_hash="unused",
            role="Auditor",
            account_status="Active",
        )
        session, token = _create_zt_verified_session(audit_officer)
        s = self.client.session
        s["access_token"] = token
        s["officer_id"] = audit_officer.user_id_PK
        s["role"] = audit_officer.role
        s.save()

        response = self.client.post(
            "/api/auditor/aid-post-verify-finish/",
            {
                "post_id": str(self.post.post_id_PK),
                "decision": "verified",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())

        # Net fund position after recording contributions + remittance = 0.
        total_in = FundTransaction.objects.filter(direction="inflow").aggregate(
            total=Sum("amount")
        )["total"] or 0
        total_out = FundTransaction.objects.filter(direction="outflow").aggregate(
            total=Sum("amount")
        )["total"] or 0
        self.assertEqual(float(total_in), 20000)
        self.assertEqual(float(total_out), 0)
        self.assertEqual(float(total_in) - float(total_out), 20000)

        # The Treasurer release endpoint only accepts posts in pending_release
        # state (normally set by the President's finish approval). Set it here.
        self.post.refresh_from_db()
        self.post.finish_status = "pending_release"
        self.post.save(update_fields=["finish_status"])

        # Disburse the full collected amount.
        response = self.client.post(
            "/api/treasurer/aid-post-release/",
            {"post_id": str(self.post.post_id_PK)},
        )
        self.assertEqual(response.status_code, 200, response.json())

        total_out_after = FundTransaction.objects.filter(direction="outflow").aggregate(
            total=Sum("amount")
        )["total"] or 0
        # Inflows (₱20k from contributions) − outflow (₱20k disbursement) = net 0.
        self.assertEqual(float(total_in), 20000)
        self.assertEqual(float(total_out_after), 20000)
        self.assertEqual(float(total_in) - float(total_out_after), 0)