"""Refuse production/FlightSim DSNs for I14 rehearsal tools."""
from __future__ import annotations

FLIGHTSIM_MARKERS = ("flightsim", "100.121.90.127")


class ProductionDSNError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def refuse_live_dsn(dsn: str | None, dbname: str | None = None) -> None:
    blob = (dsn or "").strip().lower()
    if any(m in blob for m in FLIGHTSIM_MARKERS):
        raise ProductionDSNError("refused_flightsim_dsn")
    if (dbname or "").strip().lower() == "memorybox":
        raise ProductionDSNError("refused_memorybox_dbname")
