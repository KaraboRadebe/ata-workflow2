from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("trf", "0002_seed_approvers"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'Audit events are immutable and cannot be modified or deleted.';
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER trg_audit_event_immutable
                BEFORE UPDATE OR DELETE ON trf_auditevent
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS trg_audit_event_immutable ON trf_auditevent;
                DROP FUNCTION IF EXISTS prevent_audit_event_mutation();
            """,
        ),
    ]
