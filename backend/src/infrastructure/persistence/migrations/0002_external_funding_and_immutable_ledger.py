from uuid import UUID

from django.db import migrations


FUNDING_ID = UUID("00000000-0000-0000-0000-000000000001")


def create_funding(apps, schema_editor):
    accounts = apps.get_model("persistence", "AccountModel")
    accounts.objects.using(schema_editor.connection.alias).create(
        id=FUNDING_ID, handle="EXTERNAL_FUNDING", display_name="External funding",
        allows_negative_balance=True,
    )


def remove_funding(apps, schema_editor):
    apps.get_model("persistence", "AccountModel").objects.using(schema_editor.connection.alias).filter(pk=FUNDING_ID).delete()


class Migration(migrations.Migration):
    dependencies = [("persistence", "0001_initial")]

    operations = [
        migrations.RunPython(create_funding, remove_funding),
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION reject_ledger_mutation() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'Ledger entries are append-only';
                END;
                $$ LANGUAGE plpgsql;
                CREATE TRIGGER ledger_append_only
                BEFORE UPDATE OR DELETE ON persistence_ledgerentrymodel
                FOR EACH ROW EXECUTE FUNCTION reject_ledger_mutation();
            """,
            reverse_sql="""
                DROP TRIGGER ledger_append_only ON persistence_ledgerentrymodel;
                DROP FUNCTION reject_ledger_mutation();
            """,
        ),
    ]
