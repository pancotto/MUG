# MUG

Desktop application for graphical analysis of electrical quantities.

Current version: **v1.4.1**

v1.4.1 is an operational infrastructure release focused on background update-check reliability, safer release automation and preparation for future report/laudo architecture work. It does not introduce user-facing workflow changes.

---

# 🔧 Technologies

- Python
- PySide6 for the graphical user interface
- Plotly for data visualization
- Pandas for data processing
- PyInstaller for Windows executable generation
- Inno Setup for Windows installer generation
- Kaleido/Chromium-compatible static PDF and image export

---

# 📊 Features

## Electrical quantities visualization

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

# ⚙️ Equipment workflow

## Transformer mode

- Reference / Tag
- Transformer power (kVA)
- Automatic 380/220V or 220/127V title formatting
- PRODIST Module 8 compliance labels

## Circuit breaker mode

- Reference / Tag
- Current rating (A)
- Dedicated workflow for current-based analysis
- Dynamic graph subtitle generation

---

# 🔄 Automatic updates

The application supports automatic update checking using GitHub Releases.

Features:

- Automatic startup update verification
- Background update checks outside the startup/UI critical path
- Integrated About dialog update information
- Direct download access from the application
- Release version comparison
- Native desktop update workflow

---

# 🖥️ Interface features

- Dark mode interface
- Responsive graphical layout
- Global SELEÇÃO tab for measurement interval selection
- Detected days table with complete/incomplete status
- Measurement-date dropdowns and integration-based time dropdowns
- Maximized startup window
- Unified About dialog
- Automatic uppercase formatting for operational fields
- Clickable application version
- “New Analysis” workflow without restarting the software
- Consistent visual identity across dialogs and pages

---

# 📄 PDF export

- Export selected graphs only
- Export respects the active selected measurement interval
- A4 landscape layout
- One graph per page
- Default graph preset selection
- Kaleido/Chromium-compatible rendering support
- Professional report-oriented layout

---

# 📦 Distribution

- Windows standalone executable
- Native installer generated with Inno Setup
- No external dependencies required for end users
- Portable execution support

---

# 🚀 Local execution

```bash
pip install -r requirements.txt
python app.py
```

---

# 🚢 Release process

The v1.4.1 release workflow is documented in:

```bash
docs/releases/v1.4.1-release-process.md
```

Start with a safe dry-run style validation:

```bash
python scripts/publish_release.py --version v1.4.1 --skip-benchmark
```

Full release actions such as commit, tag, push and GitHub publication require explicit flags plus `--yes`.
