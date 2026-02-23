from django.conf import settings
from django.db import models
from django.utils import timezone

class TimeStamped(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Portfolio(TimeStamped):
    CURRENCIES = [("ARS","ARS"),("USD","USD"),("EUR","EUR")]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    base_currency = models.CharField(max_length=3, choices=CURRENCIES, default="ARS")

    def __str__(self):
        return f"{self.name} ({self.owner})"

class Asset(TimeStamped):
    TYPES = [
        ("FCI", "FCI"),
        ("BOND", "BONO/ON"),
        ("STOCK", "ACCIÓN"),
        ("FX", "FX"),
        ("CASH", "EFECTIVO"),
        ("CRYPTO", "CRYPTO"),
        ("OTHER", "OTRO"),
    ]
    symbol = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    asset_type = models.CharField(max_length=12, choices=TYPES, default="FCI")
    currency = models.CharField(max_length=3, default="ARS")

    def __str__(self):
        return f"{self.symbol} - {self.name}"

class Transaction(TimeStamped):
    TX_TYPES = [
        ("BUY","COMPRA"),
        ("SELL","VENTA"),
        ("DEPOSIT","DEPÓSITO"),
        ("WITHDRAW","RETIRO"),
        ("DIVIDEND","RENDIMIENTO/DIVIDENDO"),
        ("FEE","COMISIÓN/GASTO"),
    ]
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    tx_type = models.CharField(max_length=10, choices=TX_TYPES)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    price = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    fee = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    tx_date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=240, blank=True)

class Recommendation(TimeStamped):
    """Recomendación / oportunidad para un portafolio.

    Nota: El proyecto original usaba strings ("OPEN", "ACCEPTED", "IGNORED").
    Para evitar errores de código y mantener consistencia en templates/vistas,
    definimos TextChoices con los mismos valores persistidos en DB.
    (No requiere migración: los valores son idénticos.)
    """

    class Severity(models.TextChoices):
        LOW = "LOW", "Baja"
        MED = "MED", "Media"
        HIGH = "HIGH", "Alta"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Abierta"
        ACCEPTED = "ACCEPTED", "Aceptada"
        IGNORED = "IGNORED", "Ignorada"

    # Compatibilidad hacia atrás (por si hay imports antiguos)
    SEV = Severity.choices
    STATUS = Status.choices
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    code = models.CharField(max_length=64)
    severity = models.CharField(max_length=8, choices=Severity.choices, default=Severity.LOW)
    title = models.CharField(max_length=140)
    rationale = models.TextField()
    evidence = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    decision_note = models.CharField(max_length=240, blank=True)

    # --- IA (evaluación y gobernanza) ---
    # Importante: estos campos deben estar DENTRO del modelo Recommendation.
    # Si quedan a nivel módulo, Django NO los incluye en los INSERT y la DB
    # (que sí tiene columnas NOT NULL) dispara IntegrityError.
    ai_score = models.IntegerField(null=True, blank=True)
    ai_confidence = models.IntegerField(null=True, blank=True)
    ai_action = models.CharField(max_length=12, blank=True, default="HOLD")
    ai_summary = models.TextField(blank=True, default="")
    ai_reasons = models.JSONField(default=dict, blank=True)
    ai_evaluated_at = models.DateTimeField(null=True, blank=True)


class Simulation(TimeStamped):
    PRESETS = [("CONS","Conservador"),("BAL","Balanceado"),("AGR","Agresivo")]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    preset = models.CharField(max_length=4, choices=PRESETS, default="BAL")
    virtual_cash = models.DecimalField(max_digits=18, decimal_places=2, default=1000000)
    current_day = models.IntegerField(default=0)
    seed = models.IntegerField(default=12345)

class SimPosition(TimeStamped):
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=32)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    avg_price = models.DecimalField(max_digits=18, decimal_places=6, default=0)

    class Meta:
        unique_together = ("simulation", "symbol")

class SimTrade(TimeStamped):
    SIDE = [("BUY","BUY"),("SELL","SELL")]
    simulation = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=32)
    side = models.CharField(max_length=4, choices=SIDE)
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    price = models.DecimalField(max_digits=18, decimal_places=6)
    day = models.IntegerField(default=0)

class AssetPrice(models.Model):
    """Serie historica de precios para analisis estadistico (uso educativo).

    Se carga por CSV (fecha y precio). El sistema calcula metricas como
    rendimiento, volatilidad anualizada, drawdown y Sharpe simple.
    """

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="prices")
    date = models.DateField()
    close = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        unique_together = ("asset", "date")
        ordering = ["asset", "date"]

    def __str__(self):
        return f"{self.asset.symbol} {self.date} = {self.close}"


class AuditEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=40)
    ip_address = models.CharField(max_length=64, null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"{self.created_at} {self.event_type}"
