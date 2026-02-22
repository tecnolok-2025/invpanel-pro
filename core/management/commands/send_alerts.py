import os

from django.core.management.base import BaseCommand

from core.alerts import send_daily_alert


class Command(BaseCommand):
    help = "Envía el email de alerta (ranking + procedimiento)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            dest="base_url",
            default=os.getenv("INV_BASE_URL", ""),
            help="Base URL pública (ej: https://invpanel-pro.onrender.com)",
        )

    def handle(self, *args, **options):
        base_url = (options.get("base_url") or "").strip()
        if not base_url:
            self.stderr.write(self.style.ERROR("Falta base URL. Pasá --base-url o setea INV_BASE_URL"))
            return

        ok, msg = send_daily_alert(base_url)
        if ok:
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stderr.write(self.style.ERROR(msg))
