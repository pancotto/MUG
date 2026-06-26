"""Dependency-injection container for the desktop application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from infrastructure.event_bus import EventBus
from infrastructure.logging_config import configure_logging
from services.error_service import ErrorService


@dataclass
class ServiceContainer:
    event_bus: EventBus = field(default_factory=EventBus)
    error_service: ErrorService = field(default_factory=ErrorService)
    _instances: dict[str, Any] = field(default_factory=dict)

    @property
    def assets(self):
        if "assets" not in self._instances:
            from core.paths import get_app_assets

            self._instances["assets"] = get_app_assets()
        return self._instances["assets"]

    @property
    def data_processing_service(self):
        if "data_processing_service" not in self._instances:
            from services.data_processing_service import DataProcessingService

            self._instances["data_processing_service"] = DataProcessingService()
        return self._instances["data_processing_service"]

    @property
    def graph_service(self):
        if "graph_service" not in self._instances:
            from services.graph_service import GraphService

            self._instances["graph_service"] = GraphService()
        return self._instances["graph_service"]

    @property
    def pdf_export_service(self):
        if "pdf_export_service" not in self._instances:
            from services.pdf_export_service import PdfExportService

            self._instances["pdf_export_service"] = PdfExportService()
        return self._instances["pdf_export_service"]

    @property
    def update_service(self):
        if "update_service" not in self._instances:
            from services.update_service import UpdateService

            self._instances["update_service"] = UpdateService()
        return self._instances["update_service"]


_container: ServiceContainer | None = None


def create_service_container() -> ServiceContainer:
    configure_logging()
    return ServiceContainer()


def get_service_container() -> ServiceContainer:
    global _container
    if _container is None:
        _container = create_service_container()
    return _container
