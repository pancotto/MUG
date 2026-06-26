"""ETL service boundary."""

from __future__ import annotations

from core.excel_reader import process_input_data
from core.models import InputData, ProcessedData


class DataProcessingService:
    def process(self, input_data: InputData) -> ProcessedData:
        return process_input_data(input_data)

