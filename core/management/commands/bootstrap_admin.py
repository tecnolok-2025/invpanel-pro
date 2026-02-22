import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = (
        "Crea el usuario administrador inicial (solo si NO existe ningún superusuario aún). "
        "Pensado para Render FREE sin acceso a Shell."
    )

    def handle(self, *args, **options):
        # Aceptamos los nombres que suelen usarse en Render y en Django
        username = (
            os.environ.get("ADMIN_USERNAME")
            or os.environ.get("ADMIN_USER")
            or os.environ.get("DJANGO_SUPERUSER_USERNAME")
        )
        password = os.environ.get("ADMIN_PASSWORD") or os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = (
            os.environ.get("ADMIN_EMAIL")
            or os.environ.get("DJANGO_SUPERUSER_EMAIL")
            or "admin@example.com"
        )

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "bootstrap_admin: faltan variables de entorno para crear el admin. "
                    "Definí ADMIN_USERNAME (o ADMIN_USER) y ADMIN_PASSWORD. "
                    "No se creó ningún usuario."
                )
            )
            return

        User = get_user_model()

        # Requisito del usuario: crear SOLO la primera vez.
        # Interpretación segura: si ya hay algún superusuario, no tocamos nada.
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.SUCCESS("bootstrap_admin: ya existe un superusuario; no se realizan cambios.")
            )
            return

        force_reset = (os.environ.get("ADMIN_FORCE_RESET") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
        }

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        # Si el usuario existía pero no era superuser, lo promovemos.
        # La contraseña SOLO se setea si se creó el usuario o si ADMIN_FORCE_RESET=1.
        changed = False

        if user.email != email:
            user.email = email
            changed = True

        if not user.is_staff:
            user.is_staff = True
            changed = True

        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if not user.is_active:
            user.is_active = True
            changed = True

        if created or force_reset:
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"bootstrap_admin: Admin inicial creado: '{username}'."))
        else:
            if force_reset:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"bootstrap_admin: '{username}' ya existía. Se promovió/actualizó y se reseteó la contraseña (ADMIN_FORCE_RESET=1)."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"bootstrap_admin: '{username}' ya existía. Se promovió a admin (sin cambiar contraseña)."
                    )
                )
