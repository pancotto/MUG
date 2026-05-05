# MUG

Desktop application for graphical analysis of electrical quantities.

## 🔧 Technologies

- Python
- PySide6 for the graphical user interface
- Plotly for data visualization
- Pandas for data processing
- PyInstaller for Windows executable generation
- Inno Setup for Windows installer generation

## 📊 Features

- Graphical visualization of electrical quantities:
  - Voltage
  - Current
  - Active power (kW)
  - Apparent power (kVA)
  - Power factor
  - Voltage harmonic distortion (THD)
  - Current harmonic distortion (THD)
  - Voltage imbalance
  - Current imbalance
  - Energy consumption (kWh)
  - Voltage x Current
  - kW x kVA

- Support for Primata and Embrasul measurement files
- Multi-tab graphical interface
- PDF export with selected graphs
- Default PDF graph selection
- Embedded Chromium support for PDF generation without relying on the client's installed Chrome
- Windows standalone distribution

## 🚀 Local execution

```bash
pip install -r requirements.txt
python app.py