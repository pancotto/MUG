"""Graph generation service boundary."""

from __future__ import annotations

from typing import Callable

from core.models import ProcessedData


class GraphService:
    def __init__(self):
        from core.graph_builder import (
            create_active_power_graph,
            create_apparent_power_graph,
            create_combined_kwxkva_graph,
            create_combined_vxi_graph,
            create_consumption_graph,
            create_current_graph,
            create_current_imbalance_graph,
            create_dht_current_graph,
            create_dht_voltage_graph,
            create_pf_graph,
            create_tension_graph,
            create_tension_imbalance_graph,
        )

        self._builders: dict[str, Callable[..., object]] = {
            "Tensão": create_tension_graph,
            "Corrente": create_current_graph,
            "Potência Ativa": create_active_power_graph,
            "Potência Aparente": create_apparent_power_graph,
            "Fator de Potência": create_pf_graph,
            "Deseq. Tensão": create_tension_imbalance_graph,
            "Deseq. Corrente": create_current_imbalance_graph,
            "Consumo": create_consumption_graph,
            "DHT Tensão": create_dht_voltage_graph,
            "DHT Corrente": create_dht_current_graph,
            "Tensão x Corrente": create_combined_vxi_graph,
            "kW x kVA": create_combined_kwxkva_graph,
        }

    def supported_graphs(self) -> tuple[str, ...]:
        return tuple(self._builders.keys())

    def build_figure(self, graph_name: str, processed: ProcessedData, show_logo: bool = False):
        return self._builders[graph_name](processed, show_logo=show_logo)

