from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetPrice",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("date", models.DateField()),
                ("close", models.DecimalField(decimal_places=6, max_digits=18)),
                (
                    "asset",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prices", to="core.asset"),
                ),
            ],
            options={
                "ordering": ["asset", "date"],
                "unique_together": {("asset", "date")},
            },
        ),
    ]
