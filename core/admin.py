from django.contrib import admin
from .models import (
    Portfolio,
    Asset,
    Transaction,
    Recommendation,
    Simulation,
    SimPosition,
    SimTrade,
    AssetPrice,
    AuditEvent,
)

admin.site.register(Portfolio)
admin.site.register(Asset)
admin.site.register(Transaction)
admin.site.register(Recommendation)
admin.site.register(Simulation)
admin.site.register(SimPosition)
admin.site.register(SimTrade)
admin.site.register(AssetPrice)
admin.site.register(AuditEvent)
