from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

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
from core.models import EQUIPMENT_TYPE_TRAFO, ProcessedData


GRAPH_BUILDERS = [
    ("Tensão", create_tension_graph),
    ("Corrente", create_current_graph),
    ("Potência Ativa", create_active_power_graph),
    ("Potência Aparente", create_apparent_power_graph),
    ("Fator de Potência", create_pf_graph),
    ("DHT Tensão", create_dht_voltage_graph),
    ("DHT Corrente", create_dht_current_graph),
    ("Deseq. Tensão", create_tension_imbalance_graph),
    ("Deseq. Corrente", create_current_imbalance_graph),
    ("Consumo", create_consumption_graph),
    ("Tensão x Corrente", create_combined_vxi_graph),
    ("kW x kVA", create_combined_kwxkva_graph),
]


def small_processed_data() -> ProcessedData:
    datetimes = pd.date_range("2026-06-01 00:00:00", periods=16, freq="15s")
    index = pd.Series(range(len(datetimes)), dtype=float)

    dataframe = pd.DataFrame(
        {
            "Datetime": datetimes,
            "Data": datetimes.date,
            "Hora ": datetimes.time,
            "Tensao AB (médio)(V)": 380.0 + index * 0.4,
            "Tensao BC (médio)(V)": 379.0 + index * 0.3,
            "Tensao CA (médio)(V)": 381.0 - index * 0.2,
            "Tensão A (médio)(V)": 220.0 + index * 0.2,
            "Tensão B (médio)(V)": 219.0 + index * 0.1,
            "Tensão C (médio)(V)": 221.0 - index * 0.1,
            "Corrente A (médio)(A)": 120.0 + index,
            "Corrente B (médio)(A)": 118.0 + index * 0.8,
            "Corrente C (médio)(A)": 121.0 + index * 0.6,
            "Pot Ativa Cons. Trifásica Cons. (médio)(kW)": 65.0 + index * 0.5,
            "Pot Aparente Trifásica (médio)(kVA)": 78.0 + index * 0.6,
            "FP Trifásico (médio)(%)": 95.0 + (index % 4),
            "Deseq. Tensão (médio)(%)": 0.7 + index * 0.03,
            "Deseq. Corrente (médio)(%)": 1.2 + index * 0.04,
            "DHT VA (médio)(%)": 2.0 + index * 0.05,
            "DHT VB (médio)(%)": 2.1 + index * 0.04,
            "DHT VC (médio)(%)": 1.9 + index * 0.03,
            "DHT IA (médio)(%)": 4.0 + index * 0.05,
            "DHT IB (médio)(%)": 4.1 + index * 0.04,
            "DHT IC (médio)(%)": 3.9 + index * 0.03,
            "Energia TRI Cons. (médio)((Kwh))": 0.2 + index * 0.01,
        }
    )

    return ProcessedData(
        company="ASD",
        city="VITORIA/ES",
        trafo=500.0,
        local="BENCHMARK",
        revision="00",
        excel_path=Path("synthetic.txt"),
        dataframe=dataframe,
        integration_time=15,
        tension="380",
        equipment_type=EQUIPMENT_TYPE_TRAFO,
        equipment_reference="TR-01",
        equipment_value=500.0,
    )


@pytest.mark.parametrize("graph_name, builder", GRAPH_BUILDERS)
def test_graph_builder_smoke_does_not_mutate_processed_dataframe(graph_name, builder):
    processed = small_processed_data()
    original_dataframe = processed.dataframe.copy(deep=True)

    fig = builder(processed, show_logo=False)

    assert fig is not None, graph_name
    assert isinstance(fig, go.Figure), graph_name
    assert len(fig.data) > 0, graph_name
    assert fig.layout.title.text, graph_name
    pd.testing.assert_frame_equal(processed.dataframe, original_dataframe)
