from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_assetprice"),
    ]

    operations = [
        migrations.AddField(
            model_name="recommendation",
            name="ai_score",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="recommendation",
            name="ai_confidence",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="recommendation",
            name="ai_action",
            field=models.CharField(blank=True, max_length=12),
        ),
        migrations.AddField(
            model_name="recommendation",
            name="ai_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="recommendation",
            name="ai_reasons",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="recommendation",
            name="ai_evaluated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
