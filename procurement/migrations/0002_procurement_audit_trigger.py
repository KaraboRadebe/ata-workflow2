from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("procurement", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION prevent_procurement_audit_mutation()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'Procurement audit events are immutable and cannot be modified or deleted.';
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER trg_procurement_audit_immutable
                BEFORE UPDATE OR DELETE ON procurement_procurementauditevent
                FOR EACH ROW EXECUTE FUNCTION prevent_procurement_audit_mutation();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS trg_procurement_audit_immutable ON procurement_procurementauditevent;
                DROP FUNCTION IF EXISTS prevent_procurement_audit_mutation();
            """,
        ),
    ]
