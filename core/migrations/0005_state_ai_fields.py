from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_recommendation_ai_action_default'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='recommendation',
                    name='ai_action',
                    field=models.CharField(default='HOLD', max_length=12, blank=True),
                ),
                migrations.AddField(
                    model_name='recommendation',
                    name='ai_summary',
                    field=models.TextField(default='', blank=True),
                ),
            ],
        ),
    ]
