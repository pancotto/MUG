# MUG

Desktop application for graphical analysis of electrical quantities.

Current version: **v1.2.0**

## 🔧 Technologies

- Python
- PySide6 for the graphical user interface
- Plotly for data visualization
- Pandas for data processing
- PyInstaller for Windows executable generation
- Inno Setup for Windows installer generation
- Embedded Chromium for PDF rendering

---

## 📊 Features

### Electrical quantities visualization

- Voltage (V)
- Current (I)
- Active Power (kW)
- Apparent Power (kVA)
- Power Factor
- Voltage THD
- Current THD
- Voltage Imbalance
- Current Imbalance
- Energy Consumption (kWh)
- Voltage x Current
- kW x kVA

---

## ⚙️ Equipment workflow

### Transformer mode

- Reference / Tag
- Transformer power (kVA)
- Automatic 380/220V or 220/127V title formatting
- PRODIST Module 8 compliance labels

### Circuit breaker mode

- Reference / Tag
- Current rating (A)
- Dedicated workflow for current-based analysis
- Dynamic graph subtitle generation

---

## 🖥️ Interface features

- Dark mode interface
- Responsive graphical layout
- Maximized startup window
- About window integrated with application theme
- Automatic uppercase formatting for operational fields
- Clickable application version
- “New Analysis” workflow without restarting the software

---

## 📄 PDF export

- Export selected graphs only
- A4 landscape layout
- One graph per page
- Default graph preset selection
- Embedded Chromium rendering support

---

## 📦 Distribution

- Windows standalone executable
- Native installer generated with Inno Setup
- No external dependencies required for end users

---

## 🚀 Local execution

```bash
pip install -r requirements.txt
python app.py