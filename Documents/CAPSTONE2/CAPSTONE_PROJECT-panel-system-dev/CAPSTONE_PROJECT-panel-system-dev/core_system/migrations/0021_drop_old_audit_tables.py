from django.db import migrations, connection


def copy_audit_log_to_global_trail(apps, schema_editor):
    """Copy any remaining AuditLog rows to GlobalAuditTrail.
    Gracefully skips if AUDIT_LOG table doesn't exist (fresh DB)."""
    table_names = connection.introspection.table_names()
    if "audit_log" not in table_names:
        return

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO `GLOBAL_AUDIT_TRAIL`
                (`table_name`, `record_id`, `action`, `actor_type`, `actor_id`, `actor_name`,
                 `ip_address`, `device_info`, `notes`, `timestamp`)
            SELECT
                CASE a.entity_type
                    WHEN 'MembershipFee' THEN 'membership_fee'
                    WHEN 'MonthlyDues' THEN 'monthly_dues'
                    WHEN 'MedicalAid' THEN 'medical_aid'
                    WHEN 'DeathAid' THEN 'death_aid'
                    ELSE LOWER(a.entity_type)
                END,
                a.entity_id,
                UPPER(LEFT(COALESCE(a.action, ''), 20)),
                COALESCE(a.actor_type, ''),
                a.actor_id,
                '',
                a.ip_address,
                COALESCE(a.device_info, ''),
                CONCAT('Migrated from AuditLog. Original action: ', a.action),
                a.timestamp
            FROM `AUDIT_LOG` a;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0020_merge_audit_tables'),
    ]

    operations = [
        migrations.RunPython(copy_audit_log_to_global_trail, reverse_code=migrations.RunPython.noop),
        # Drop deprecated tables
        migrations.RunSQL(
            "DROP TABLE IF EXISTS `AUDITOR_PAYMENT_VERIFICATION`;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP TABLE IF EXISTS `AUDITOR_AID_VERIFICATION`;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "DROP TABLE IF EXISTS `AUDIT_LOG`;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
