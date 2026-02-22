from __future__ import annotations

from decimal import Decimal
from django import forms

from .models import Asset, Portfolio, Simulation, Transaction


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ["name", "base_currency"]


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ["symbol", "name", "asset_type", "currency"]


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["asset", "tx_type", "quantity", "price", "fee", "tx_date", "note"]


class SimulationForm(forms.ModelForm):
    class Meta:
        model = Simulation
        fields = ["name", "preset", "virtual_cash", "seed"]


class SimTradeForm(forms.Form):
    symbol = forms.CharField(max_length=32, help_text="Ej: AAPL, FCI_MM, BONO_CER (solo entrenamiento).")
    side = forms.ChoiceField(choices=[("BUY", "BUY"), ("SELL", "SELL")])
    quantity = forms.DecimalField(max_digits=18, decimal_places=6, min_value=Decimal("0.000001"))
    # Precio es opcional: si lo dejás vacío, el sistema usa un precio determinístico (educativo)
    # o el último precio cargado en Históricos (si existe).
    price = forms.DecimalField(
        max_digits=18,
        decimal_places=6,
        required=False,
        min_value=Decimal("0.000001"),
        help_text="Opcional. Si está vacío, usa precio educativo o histórico.",
    )


class AdvanceDaysForm(forms.Form):
    days = forms.IntegerField(min_value=1, max_value=365, initial=1)


class PriceUploadForm(forms.Form):
    # El usuario puede cargar CSV "por activo" (date,close) o "multi-activo" (date,symbol,close).
    asset = forms.ModelChoiceField(
        queryset=Asset.objects.all().order_by("symbol"),
        required=False,
        help_text="Opcional. Si elegís un activo, el CSV puede ser date,close. Si lo dejás vacío, el CSV debe incluir symbol.",
    )
    csv_file = forms.FileField(
        help_text=(
            "CSV con columnas: date,close (o fecha,precio). "
            "Si NO seleccionás un activo arriba, usar: date,symbol,close (y opcional name). "
            "Separador: coma o punto y coma."
        )
    )
