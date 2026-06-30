from django.contrib.postgres.operations import CreateExtension
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [("chat_history", "0001_initial")]
    operations = [CreateExtension("vector")]
