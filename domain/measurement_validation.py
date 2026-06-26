"""Domain model for lightweight measurement-file validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


STATUS_VALID = "valid"
STATUS_INVALID = "invalid"
STATUS_CORRUPTED = "corrupted"
STATUS_UNSUPPORTED = "unsupported"

STATUS_LABELS = {
    STATUS_VALID: "Arquivo válido",
    STATUS_INVALID: "Arquivo inválido",
    STATUS_CORRUPTED: "Arquivo corrompido",
    STATUS_UNSUPPORTED: "Formato não suportado",
}


@dataclass(frozen=True)
class MeasurementValidationResult:
    path: Path
    status: str
    manufacturer: str = "Não identificado"
    file_type: str = ""
    period: str = "Não disponível"
    integration_interval: str = "Não disponível"
    records: int | None = None
    message: str = ""

    @property
    def is_valid(self) -> bool:
        return self.status == STATUS_VALID

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, "Arquivo inválido")

    @property
    def records_text(self) -> str:
        if self.records is None:
            return "Não disponível"
        return f"{self.records:,}".replace(",", ".")


def format_integration_interval(seconds: int | None) -> str:
    if not seconds or seconds <= 0:
        return "Não disponível"

    if seconds < 60:
        return f"{seconds} s"

    minutes, remaining_seconds = divmod(seconds, 60)
    if remaining_seconds == 0:
        return f"{minutes} min"

    return f"{minutes} min {remaining_seconds} s"
