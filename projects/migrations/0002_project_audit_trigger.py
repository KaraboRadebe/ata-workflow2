from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION prevent_project_audit_mutation()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'Project audit events are immutable and cannot be modified or deleted.';
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER trg_project_audit_immutable
                BEFORE UPDATE OR DELETE ON projects_projectauditevent
                FOR EACH ROW EXECUTE FUNCTION prevent_project_audit_mutation();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS trg_project_audit_immutable ON projects_projectauditevent;
                DROP FUNCTION IF EXISTS prevent_project_audit_mutation();
            """,
        ),
    ]
