-- ============================================================================
-- ISU CauFA Portal - Database Schema
-- Generated from Django models (core_system/models.py)
-- Engine: MySQL 8+ | Charset: utf8mb4 | Collation: utf8mb4_unicode_ci
-- ============================================================================

CREATE DATABASE IF NOT EXISTS capstone_project_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE capstone_project_db;

-- ----------------------------------------------------------------------------
-- 1. OFFICER_USER
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS OFFICER_USER;

CREATE TABLE OFFICER_USER (
    user_id_PK       INT            NOT NULL AUTO_INCREMENT,
    full_name        VARCHAR(255)   NOT NULL,
    username         VARCHAR(150)   NOT NULL,
    password_hash    VARCHAR(255)   NOT NULL,
    role             VARCHAR(50)    NOT NULL,
    account_status   VARCHAR(50)    NOT NULL,
    term_start       DATE           NULL,
    term_end         DATE           NULL,
    mfa_secret       VARCHAR(255)   NULL,
    created_at       DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at       DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (user_id_PK),
    UNIQUE KEY uk_officer_user_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2. MEMBER
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS MEMBER;

CREATE TABLE MEMBER (
    member_id_PK       INT            NOT NULL AUTO_INCREMENT,
    full_name          VARCHAR(255)   NOT NULL,
    employee_id        VARCHAR(50)    NULL,
    department         VARCHAR(100)   NULL,
    position           VARCHAR(100)   NULL,
    contact_number     VARCHAR(50)    NULL,
    email              VARCHAR(255)   NULL,
    employment_status  VARCHAR(50)    NOT NULL,
    membership_status  VARCHAR(50)    NOT NULL,
    member_type        VARCHAR(50)    NOT NULL DEFAULT '',
    date_joined        DATE           NOT NULL,
    PRIMARY KEY (member_id_PK)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 3. LOGIN_ATTEMPT_LOG
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS LOGIN_ATTEMPT_LOG;

CREATE TABLE LOGIN_ATTEMPT_LOG (
    attempt_id_PK   INT            NOT NULL AUTO_INCREMENT,
    user_id_FK      INT            NULL,
    username_used   VARCHAR(150)   NOT NULL,
    ip_address      VARCHAR(39)    NOT NULL,
    device_info     VARCHAR(255)   NULL,
    result          VARCHAR(50)    NOT NULL,
    attempted_at    DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (attempt_id_PK),
    KEY fk_login_attempt_user (user_id_FK),
    CONSTRAINT fk_login_attempt_user FOREIGN KEY (user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 4. ACCESS_SESSION
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS ACCESS_SESSION;

CREATE TABLE ACCESS_SESSION (
    session_id_PK   INT            NOT NULL AUTO_INCREMENT,
    user_id_FK      INT            NOT NULL,
    token_id        VARCHAR(255)   NOT NULL,
    ip_address      VARCHAR(39)    NOT NULL,
    device_info     VARCHAR(255)   NULL,
    issued_at       DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    expires_at      DATETIME(6)    NOT NULL,
    revoked_at      DATETIME(6)    NULL,
    session_status  VARCHAR(50)    NOT NULL,
    PRIMARY KEY (session_id_PK),
    UNIQUE KEY uk_access_session_token (token_id),
    KEY fk_access_session_user (user_id_FK),
    CONSTRAINT fk_access_session_user FOREIGN KEY (user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 5. SENSITIVE_READ_LOG
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS SENSITIVE_READ_LOG;

CREATE TABLE SENSITIVE_READ_LOG (
    read_id_PK   INT            NOT NULL AUTO_INCREMENT,
    user_id_FK   INT            NOT NULL,
    module       VARCHAR(100)   NOT NULL,
    record_id    INT            NOT NULL,
    purpose      VARCHAR(255)   NOT NULL,
    timestamp    DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (read_id_PK),
    KEY fk_sensitive_read_user (user_id_FK),
    CONSTRAINT fk_sensitive_read_user FOREIGN KEY (user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 6. NOTIFICATION
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS NOTIFICATION;

CREATE TABLE NOTIFICATION (
    notification_id_PK   INT            NOT NULL AUTO_INCREMENT,
    recipient_type       VARCHAR(50)    NOT NULL,
    recipient_id         INT            NOT NULL,
    recipient_name       VARCHAR(255)   NOT NULL,
    recipient_contact    VARCHAR(255)   NULL,
    notification_type    VARCHAR(50)    NOT NULL,
    message              LONGTEXT       NOT NULL,
    delivery_status      VARCHAR(50)    NOT NULL,
    sent_at              DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (notification_id_PK)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 7. PUSH_SUBSCRIPTION
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS PUSH_SUBSCRIPTION;

CREATE TABLE PUSH_SUBSCRIPTION (
    subscription_id_PK   INT            NOT NULL AUTO_INCREMENT,
    officer_id_FK        INT            NOT NULL,
    endpoint             VARCHAR(500)   NOT NULL,
    p256dh_key           VARCHAR(256)   NOT NULL,
    auth_key             VARCHAR(128)   NOT NULL,
    user_agent           VARCHAR(500)   NULL,
    created_at           DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at           DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (subscription_id_PK),
    UNIQUE KEY uk_push_subscription (officer_id_FK, endpoint),
    KEY fk_push_subscription_officer (officer_id_FK),
    CONSTRAINT fk_push_subscription_officer FOREIGN KEY (officer_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 8. FINANCIAL_DOCUMENT_ARCHIVE
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS FINANCIAL_DOCUMENT_ARCHIVE;

CREATE TABLE FINANCIAL_DOCUMENT_ARCHIVE (
    document_id_PK          INT            NOT NULL AUTO_INCREMENT,
    related_module          VARCHAR(100)   NOT NULL,
    related_record_id       INT            NOT NULL,
    document_type           VARCHAR(100)   NOT NULL,
    file_path               VARCHAR(500)   NOT NULL,
    file_hash               VARCHAR(255)   NOT NULL,
    verification_status     VARCHAR(50)    NOT NULL,
    uploaded_by_user_id_FK  INT            NOT NULL,
    uploaded_at             DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (document_id_PK),
    KEY fk_financial_doc_uploader (uploaded_by_user_id_FK),
    CONSTRAINT fk_financial_doc_uploader FOREIGN KEY (uploaded_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 9. MONTHLY_DUES
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS MONTHLY_DUES;

CREATE TABLE MONTHLY_DUES (
    dues_id_PK                INT              NOT NULL AUTO_INCREMENT,
    member_id_FK              INT              NOT NULL,
    month_covered             VARCHAR(50)      NOT NULL,
    amount                    DECIMAL(10,2)    NOT NULL,
    payment_method            VARCHAR(50)      NOT NULL,
    payment_status            VARCHAR(50)      NOT NULL,
    payment_date              DATE             NULL,
    receipt_number            VARCHAR(100)     NULL,
    deduction_batch_reference VARCHAR(100)     NULL,
    remittance_reference      VARCHAR(100)     NULL,
    recorded_by_user_id_FK    INT              NOT NULL,
    PRIMARY KEY (dues_id_PK),
    KEY fk_monthly_dues_member (member_id_FK),
    KEY fk_monthly_dues_recorder (recorded_by_user_id_FK),
    CONSTRAINT fk_monthly_dues_member FOREIGN KEY (member_id_FK)
        REFERENCES MEMBER (member_id_PK)
        ON DELETE RESTRICT,
    CONSTRAINT fk_monthly_dues_recorder FOREIGN KEY (recorded_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 10. MEMBERSHIP_FEE
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS MEMBERSHIP_FEE;

CREATE TABLE MEMBERSHIP_FEE (
    fee_id_PK                INT              NOT NULL AUTO_INCREMENT,
    member_id_FK             INT              NOT NULL,
    amount                   DECIMAL(10,2)    NOT NULL,
    payment_method           VARCHAR(50)      NOT NULL,
    payment_status           VARCHAR(50)      NOT NULL,
    month_covered            VARCHAR(50)      NULL,
    payment_date             DATE             NOT NULL,
    receipt_number           VARCHAR(100)     NULL,
    deposit_reference        VARCHAR(100)     NULL,
    recorded_by_user_id_FK   INT              NOT NULL,
    PRIMARY KEY (fee_id_PK),
    UNIQUE KEY uk_membership_fee (member_id_FK, receipt_number),
    KEY fk_membership_fee_recorder (recorded_by_user_id_FK),
    CONSTRAINT fk_membership_fee_member FOREIGN KEY (member_id_FK)
        REFERENCES MEMBER (member_id_PK)
        ON DELETE RESTRICT,
    CONSTRAINT fk_membership_fee_recorder FOREIGN KEY (recorded_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 11. CLAIMANT
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS CLAIMANT;

CREATE TABLE CLAIMANT (
    claimant_id_PK       INT            NOT NULL AUTO_INCREMENT,
    member_id_FK         INT            NOT NULL,
    full_name            VARCHAR(255)   NOT NULL,
    contact_number       VARCHAR(50)    NULL,
    relationship_to_member VARCHAR(100) NOT NULL,
    relationship_group   VARCHAR(20)    NOT NULL DEFAULT '',
    authorization_status VARCHAR(50)    NOT NULL,
    PRIMARY KEY (claimant_id_PK),
    KEY fk_claimant_member (member_id_FK),
    CONSTRAINT fk_claimant_member FOREIGN KEY (member_id_FK)
        REFERENCES MEMBER (member_id_PK)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 12. MEDICAL_AID
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS MEDICAL_AID;

CREATE TABLE MEDICAL_AID (
    medical_aid_id_PK                  INT              NOT NULL AUTO_INCREMENT,
    member_id_FK                       INT              NOT NULL,
    request_date                       DATE             NOT NULL,
    requested_amount                   DECIMAL(10,2)    NULL,
    hospital_name                      VARCHAR(255)     NOT NULL DEFAULT '',
    hospital_date                      DATE             NULL,
    hospital_bill_amount               DECIMAL(10,2)    NOT NULL,
    claim_year                         INT              NOT NULL,
    document_status                    VARCHAR(50)      NOT NULL,
    policy_record_status               VARCHAR(50)      NOT NULL,
    validated_aid_amount               DECIMAL(10,2)    NOT NULL,
    status                             VARCHAR(50)      NOT NULL,
    treasurer_validated_by_user_id_FK  INT              NULL,
    auditor_verified_by_user_id_FK     INT              NULL,
    president_decided_by_user_id_FK    INT              NULL,
    president_decision                 VARCHAR(50)      NULL,
    released_by_user_id_FK             INT              NULL,
    release_reference                  VARCHAR(100)     NULL,
    acknowledgement_reference          VARCHAR(100)     NULL,
    PRIMARY KEY (medical_aid_id_PK),
    KEY fk_medical_aid_member (member_id_FK),
    KEY fk_medical_aid_treasurer (treasurer_validated_by_user_id_FK),
    KEY fk_medical_aid_auditor (auditor_verified_by_user_id_FK),
    KEY fk_medical_aid_president (president_decided_by_user_id_FK),
    KEY fk_medical_aid_releaser (released_by_user_id_FK),
    CONSTRAINT fk_medical_aid_member FOREIGN KEY (member_id_FK)
        REFERENCES MEMBER (member_id_PK)
        ON DELETE RESTRICT,
    CONSTRAINT fk_medical_aid_treasurer FOREIGN KEY (treasurer_validated_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_medical_aid_auditor FOREIGN KEY (auditor_verified_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_medical_aid_president FOREIGN KEY (president_decided_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
    -- released_by_user_id_FK has db_constraint=False in Django (no FK constraint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 13. DEATH_AID
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS DEATH_AID;

CREATE TABLE DEATH_AID (
    death_aid_id_PK                    INT              NOT NULL AUTO_INCREMENT,
    member_id_FK                       INT              NOT NULL,
    claimant_id_FK                     INT              NOT NULL,
    claim_date                         DATE             NOT NULL,
    claim_type                         VARCHAR(50)      NOT NULL,
    deceased_name                      VARCHAR(255)     NOT NULL,
    relationship_to_member             VARCHAR(100)     NOT NULL,
    relationship_group                 VARCHAR(20)      NOT NULL DEFAULT '',
    funeral_location                   VARCHAR(255)     NOT NULL DEFAULT '',
    interment_date                     DATE             NULL,
    benefit_amount                     DECIMAL(10,2)    NOT NULL,
    bill_amount                        DECIMAL(10,2)    NULL,
    document_status                    VARCHAR(50)      NOT NULL,
    status                             VARCHAR(50)      NOT NULL,
    treasurer_validated_by_user_id_FK  INT              NULL,
    auditor_verified_by_user_id_FK     INT              NULL,
    president_decided_by_user_id_FK    INT              NULL,
    president_decision                 VARCHAR(50)      NULL,
    released_by_user_id_FK             INT              NULL,
    release_reference                  VARCHAR(100)     NULL,
    acknowledgement_reference          VARCHAR(100)     NULL,
    PRIMARY KEY (death_aid_id_PK),
    KEY fk_death_aid_member (member_id_FK),
    KEY fk_death_aid_claimant (claimant_id_FK),
    KEY fk_death_aid_treasurer (treasurer_validated_by_user_id_FK),
    KEY fk_death_aid_auditor (auditor_verified_by_user_id_FK),
    KEY fk_death_aid_president (president_decided_by_user_id_FK),
    KEY fk_death_aid_releaser (released_by_user_id_FK),
    CONSTRAINT fk_death_aid_member FOREIGN KEY (member_id_FK)
        REFERENCES MEMBER (member_id_PK)
        ON DELETE RESTRICT,
    CONSTRAINT fk_death_aid_claimant FOREIGN KEY (claimant_id_FK)
        REFERENCES CLAIMANT (claimant_id_PK)
        ON DELETE RESTRICT,
    CONSTRAINT fk_death_aid_treasurer FOREIGN KEY (treasurer_validated_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_death_aid_auditor FOREIGN KEY (auditor_verified_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_death_aid_president FOREIGN KEY (president_decided_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
    -- released_by_user_id_FK has db_constraint=False in Django (no FK constraint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 14. AUDIT_FINDINGS_REPORT
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS AUDIT_FINDINGS_REPORT;

CREATE TABLE AUDIT_FINDINGS_REPORT (
    audit_report_id_PK          INT            NOT NULL AUTO_INCREMENT,
    report_title                VARCHAR(255)   NOT NULL,
    report_period               VARCHAR(100)   NOT NULL,
    findings_summary            LONGTEXT       NOT NULL,
    report_status               VARCHAR(50)    NOT NULL,
    prepared_by_user_id_FK      INT            NOT NULL,
    prepared_date               DATE           NOT NULL,
    board_submission_date       DATE           NULL,
    board_meeting_reference     VARCHAR(255)   NULL,
    presentation_status         VARCHAR(50)    NOT NULL,
    certification_status        VARCHAR(50)    NOT NULL,
    certified_by_user_id_FK     INT            NULL,
    PRIMARY KEY (audit_report_id_PK),
    KEY fk_audit_report_preparer (prepared_by_user_id_FK),
    KEY fk_audit_report_certifier (certified_by_user_id_FK),
    CONSTRAINT fk_audit_report_preparer FOREIGN KEY (prepared_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE RESTRICT,
    CONSTRAINT fk_audit_report_certifier FOREIGN KEY (certified_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 15. django_content_type  (Django system table, required by GenericForeignKey)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS django_content_type;

CREATE TABLE django_content_type (
    id         INT           NOT NULL AUTO_INCREMENT,
    app_label  VARCHAR(100)  NOT NULL,
    model      VARCHAR(100)  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_django_content_type (app_label, model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 16. SUPPORTING_PROOF
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS SUPPORTING_PROOF;

CREATE TABLE SUPPORTING_PROOF (
    proof_id_PK            INT            NOT NULL AUTO_INCREMENT,
    content_type_id        INT            NOT NULL,
    object_id              INT UNSIGNED   NOT NULL,
    file_path              VARCHAR(500)   NOT NULL,
    file_name              VARCHAR(255)   NOT NULL,
    file_type              VARCHAR(100)   NOT NULL,
    file_sha256            VARCHAR(64)    NOT NULL,
    row_signature          VARCHAR(64)    NOT NULL,
    uploaded_at            DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    uploaded_by_user_id_FK INT            NULL,
    PRIMARY KEY (proof_id_PK),
    KEY fk_supporting_proof_content_type (content_type_id, object_id),
    KEY idx_supporting_proof_uploaded_at (uploaded_at),
    KEY fk_supporting_proof_uploader (uploaded_by_user_id_FK),
    CONSTRAINT fk_supporting_proof_content_type FOREIGN KEY (content_type_id)
        REFERENCES django_content_type (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_supporting_proof_uploader FOREIGN KEY (uploaded_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 17. revision_log
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS revision_log;

CREATE TABLE revision_log (
    log_id          INT            NOT NULL AUTO_INCREMENT,
    content_type_id INT            NOT NULL,
    object_id       INT UNSIGNED   NOT NULL,
    rejection_reason LONGTEXT      NOT NULL,
    snapshot_data   JSON           NOT NULL,
    auditor_id_FK   INT            NULL,
    created_at      DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (log_id),
    KEY fk_revision_log_content_type (content_type_id, object_id),
    KEY idx_revision_log_created_at (created_at),
    KEY fk_revision_log_auditor (auditor_id_FK),
    CONSTRAINT fk_revision_log_content_type FOREIGN KEY (content_type_id)
        REFERENCES django_content_type (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_revision_log_auditor FOREIGN KEY (auditor_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 18. transaction_verification
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS transaction_verification;

CREATE TABLE transaction_verification (
    verification_id            INT            NOT NULL AUTO_INCREMENT,
    table_name                 VARCHAR(50)    NOT NULL,
    record_id                  INT            NOT NULL,
    target_category            VARCHAR(50)    NULL,
    verification_status        VARCHAR(50)    NOT NULL DEFAULT 'Pending Verification',
    auditor_id_FK              INT            NULL,
    auditor_remarks            LONGTEXT       NULL,
    evidence_file_path         VARCHAR(500)   NULL,
    evidence_file_hash         VARCHAR(255)   NULL,
    returned_by_auditor_id_FK  INT            NULL,
    returned_reason            LONGTEXT       NULL,
    return_count               INT            NOT NULL DEFAULT 0,
    president_id_FK            INT            NULL,
    verified_at                DATETIME(6)    NULL,
    approved_at                DATETIME(6)    NULL,
    PRIMARY KEY (verification_id),
    KEY fk_trans_ver_auditor (auditor_id_FK),
    KEY fk_trans_ver_returner (returned_by_auditor_id_FK),
    KEY fk_trans_ver_president (president_id_FK),
    CONSTRAINT fk_trans_ver_auditor FOREIGN KEY (auditor_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_trans_ver_returner FOREIGN KEY (returned_by_auditor_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_trans_ver_president FOREIGN KEY (president_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 19. transaction_archive
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS transaction_archive;

CREATE TABLE transaction_archive (
    archive_id_PK            INT              NOT NULL AUTO_INCREMENT,
    transaction_type         VARCHAR(50)      NOT NULL,
    record_id                INT              NOT NULL,
    member_id_FK             INT              NULL,
    member_name              VARCHAR(255)     NOT NULL,
    amount                   DECIMAL(10,2)    NOT NULL,
    validated_amount         DECIMAL(10,2)    NULL,
    status                   VARCHAR(50)      NOT NULL,
    payment_method           VARCHAR(50)      NULL,
    release_reference        VARCHAR(100)     NULL,
    released_by_user_id_FK   INT              NULL,
    verified_at              DATETIME(6)      NULL,
    archived_at              DATETIME(6)      NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    archived_by_user_id_FK   INT              NULL,
    PRIMARY KEY (archive_id_PK),
    KEY idx_trans_archive_type_record (transaction_type, record_id),
    KEY idx_trans_archive_status (status),
    KEY fk_trans_archive_member (member_id_FK),
    KEY fk_trans_archive_releaser (released_by_user_id_FK),
    KEY fk_trans_archive_archiver (archived_by_user_id_FK),
    CONSTRAINT fk_trans_archive_member FOREIGN KEY (member_id_FK)
        REFERENCES MEMBER (member_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_trans_archive_releaser FOREIGN KEY (released_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL,
    CONSTRAINT fk_trans_archive_archiver FOREIGN KEY (archived_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 20. AID_TRACKING_POST
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS AID_TRACKING_POST;

CREATE TABLE AID_TRACKING_POST (
    post_id_PK             INT              NOT NULL AUTO_INCREMENT,
    archive_id_FK          INT              NOT NULL,
    aid_type               VARCHAR(50)      NOT NULL,
    target_month           VARCHAR(7)       NOT NULL,
    total_expected         DECIMAL(10,2)    NOT NULL DEFAULT 0,
    total_collected        DECIMAL(10,2)    NOT NULL DEFAULT 0,
    is_active              TINYINT(1)       NOT NULL DEFAULT 1,
    notes                  LONGTEXT         NOT NULL DEFAULT (''),
    created_by_user_id_FK  INT              NULL,
    created_at             DATETIME(6)      NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at             DATETIME(6)      NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (post_id_PK),
    KEY fk_aid_tracking_archive (archive_id_FK),
    KEY fk_aid_tracking_creator (created_by_user_id_FK),
    CONSTRAINT fk_aid_tracking_archive FOREIGN KEY (archive_id_FK)
        REFERENCES transaction_archive (archive_id_PK)
        ON DELETE CASCADE,
    CONSTRAINT fk_aid_tracking_creator FOREIGN KEY (created_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 21. CONTRIBUTION
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS CONTRIBUTION;

CREATE TABLE CONTRIBUTION (
    contribution_id_PK         INT              NOT NULL AUTO_INCREMENT,
    aid_tracking_post_id_FK    INT              NOT NULL,
    member_id_FK               INT              NOT NULL,
    expected_amount            DECIMAL(10,2)    NOT NULL,
    paid_amount                DECIMAL(10,2)    NOT NULL DEFAULT 0,
    payment_date               DATE             NULL,
    status                     VARCHAR(20)      NOT NULL DEFAULT 'NOT_PAID',
    is_manually_overridden     TINYINT(1)       NOT NULL DEFAULT 0,
    notes                      LONGTEXT         NOT NULL DEFAULT (''),
    updated_by_user_id_FK      INT              NULL,
    updated_at                 DATETIME(6)      NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (contribution_id_PK),
    UNIQUE KEY uk_contribution (aid_tracking_post_id_FK, member_id_FK),
    KEY fk_contribution_member (member_id_FK),
    KEY fk_contribution_updater (updated_by_user_id_FK),
    CONSTRAINT fk_contribution_post FOREIGN KEY (aid_tracking_post_id_FK)
        REFERENCES AID_TRACKING_POST (post_id_PK)
        ON DELETE CASCADE,
    CONSTRAINT fk_contribution_member FOREIGN KEY (member_id_FK)
        REFERENCES MEMBER (member_id_PK)
        ON DELETE RESTRICT,
    CONSTRAINT fk_contribution_updater FOREIGN KEY (updated_by_user_id_FK)
        REFERENCES OFFICER_USER (user_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 22. GLOBAL_AUDIT_TRAIL
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS GLOBAL_AUDIT_TRAIL;

CREATE TABLE GLOBAL_AUDIT_TRAIL (
    trail_id                INT            NOT NULL AUTO_INCREMENT,
    table_name              VARCHAR(100)   NOT NULL,
    record_id               INT            NOT NULL,
    action                  VARCHAR(20)    NOT NULL,
    document_archive_id_FK  INT            NULL,
    old_values              JSON           NULL,
    new_values              JSON           NULL,
    actor_type              VARCHAR(50)    NOT NULL,
    actor_id                INT            NULL,
    actor_name              VARCHAR(255)   NOT NULL,
    ip_address              VARCHAR(39)    NULL,
    device_info             VARCHAR(255)   NULL,
    notes                   LONGTEXT       NULL,
    timestamp               DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (trail_id),
    KEY idx_audit_trail_lookup (table_name, record_id, timestamp),
    KEY fk_audit_trail_document (document_archive_id_FK),
    CONSTRAINT fk_audit_trail_document FOREIGN KEY (document_archive_id_FK)
        REFERENCES FINANCIAL_DOCUMENT_ARCHIVE (document_id_PK)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS SENSITIVE_READ_LOG;

CREATE TABLE SENSITIVE_READ_LOG (
    read_id                            INT              NOT NULL AUTO_INCREMENT,
    table_name                         VARCHAR(100)     NOT NULL,
    record_id                          INT              NULL,
    reader_type                        VARCHAR(50)      NOT NULL,
    reader_id                          INT              NULL,
    reader_name                        VARCHAR(255)     NOT NULL,
    ip_address                         VARCHAR(39)      NULL,
    description                        TEXT             NULL,
    read_at                            DATETIME(6)      NOT NULL,
    PRIMARY KEY (read_id),
    INDEX sensitive_read_log_table_record_idx (table_name, record_id),
    INDEX sensitive_read_log_read_at_idx (read_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
