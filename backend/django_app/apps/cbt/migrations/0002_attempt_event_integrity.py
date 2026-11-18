"""Add retry-safe client event identifiers and PostgreSQL immutability."""

from django.db import migrations, models


def install_event_immutability_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION cbt_reject_attempt_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'CBT attempt events are append-only'
                USING ERRCODE = '23514';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    schema_editor.execute(
        """
        CREATE TRIGGER cbt_attempt_event_immutable
        BEFORE UPDATE OR DELETE ON cbt_exam_attempt_event
        FOR EACH ROW EXECUTE FUNCTION cbt_reject_attempt_event_mutation();
        """
    )


def remove_event_immutability_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "DROP TRIGGER IF EXISTS cbt_attempt_event_immutable ON cbt_exam_attempt_event;"
    )
    schema_editor.execute(
        "DROP FUNCTION IF EXISTS cbt_reject_attempt_event_mutation();"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="examattemptevent",
            name="client_event_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="examattemptevent",
            constraint=models.UniqueConstraint(
                fields=("attempt", "client_event_id"),
                name="uq_cbt_event_attempt_client_id",
            ),
        ),
        migrations.RunPython(
            install_event_immutability_trigger,
            reverse_code=remove_event_immutability_trigger,
        ),
    ]
