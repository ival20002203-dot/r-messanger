from django.db import migrations

def create_indexes(apps,schema_editor):
    if schema_editor.connection.vendor!="postgresql":return
    with schema_editor.connection.cursor() as cur:
        cur.execute("CREATE INDEX IF NOT EXISTS chat_message_body_fts_idx ON chat_message USING GIN (to_tsvector('simple', coalesce(body,'')))")
        cur.execute("CREATE INDEX IF NOT EXISTS chat_message_created_sender_idx ON chat_message (sender_id, created_at DESC)")

def drop_indexes(apps,schema_editor):
    if schema_editor.connection.vendor!="postgresql":return
    with schema_editor.connection.cursor() as cur:
        cur.execute("DROP INDEX IF EXISTS chat_message_body_fts_idx")
        cur.execute("DROP INDEX IF EXISTS chat_message_created_sender_idx")

class Migration(migrations.Migration):
    dependencies=[("chat","0005_localgram_v6")]
    operations=[migrations.RunPython(create_indexes,drop_indexes)]
