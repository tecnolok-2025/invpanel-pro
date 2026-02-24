from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_state_ai_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannedMove",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "Pendiente"), ("DONE", "Hecho"), ("CANCELED", "Cancelado")],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("plan_text", models.TextField()),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "portfolio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plans",
                        to="core.portfolio",
                    ),
                ),
                (
                    "recommendation",
                    models.ForeignKey(
                        blank=True,
                        help_text="Oportunidad que originó este plan (si aplica).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="plans",
                        to="core.recommendation",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
