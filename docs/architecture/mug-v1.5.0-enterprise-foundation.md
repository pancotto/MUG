# MUG v1.5.0 Enterprise Foundation

## Architecture Diagram

```mermaid
flowchart TD
    App["app.py startup"] --> Container["ServiceContainer"]
    App --> Splash["ui.splash_screen"]
    Container --> Config["config/*"]
    Container --> Logging["infrastructure.logging_config"]
    Container --> EventBus["infrastructure.event_bus"]
    Container --> ErrorService["services.error_service"]
    UI["ui/*"] --> Container
    UI --> Domain["domain/input_rules"]
    UI --> Services["services/*"]
    Services --> Core["core ETL / graph / PDF / update engines"]
    Core --> Assets["assets/*"]
    Reports["reports/*"] -. future .-> Services
```

## Dependency Graph Before

```mermaid
flowchart TD
    App["app.py"] --> UI["ui.main_window"]
    App --> Splash["ui.splash_screen"]
    UI --> Input["ui.input_page"]
    UI --> Graph["ui.graph_page"]
    UI --> Update["core.update_checker"]
    Input --> ETL["core.excel_reader"]
    Input --> Models["core.models"]
    Graph --> Builders["core.graph_builder"]
    Graph --> PDF["core.pdf_exporter"]
    Graph --> Time["core.time_filter"]
    Builders --> Paths["core.paths"]
```

## Dependency Graph After

```mermaid
flowchart TD
    App["app.py"] --> Startup["infrastructure.startup"]
    App --> Versions["config.versions"]
    App --> Container["services.container"]
    App --> Splash["ui.splash_screen"]
    Container --> Logging["infrastructure.logging_config"]
    Container --> Events["infrastructure.event_bus"]
    Container --> Errors["services.error_service"]
    UI["ui.main_window/input_page/graph_page"] --> Container
    Input["ui.input_page"] --> Rules["domain.input_rules"]
    Input --> DataService["services.data_processing_service"]
    Graph["ui.graph_page"] --> GraphService["services.graph_service"]
    Graph --> PdfService["services.pdf_export_service"]
    Main["ui.main_window"] --> UpdateService["services.update_service"]
    DataService --> ETL["core.excel_reader"]
    GraphService --> Builders["core.graph_builder"]
    PdfService --> PDF["core.pdf_exporter"]
    UpdateService --> Update["core.update_checker"]
```

## Moved Modules

- Startup single-instance guard moved from `app.py` to `infrastructure/startup.py`.
- Version/path concerns moved from UI duplicates into `config/versions.py` and `config/paths.py`.
- Input form business validation moved from `ui/input_page.py` into `domain/input_rules.py`.
- ETL, graph, PDF and update calls now flow through service boundaries in `services/`.
- Asset lookup remains backward-compatible through `core/paths.py`, with canonical categorized locations under `assets/`.

## Migration Notes

- Existing `core` behavior modules remain in place for compatibility and test stability.
- UI classes now receive a service container and use service boundaries for business operations.
- Logging is centralized through Python `logging` with rotating files under the user-local MUG log directory.
- The event bus is synchronous and intentionally lightweight; it prepares for future UI/report decoupling without threading changes.
- `reports/` is scaffolded for v2.0.0 report engine work without changing current PDF export.

## Maintainability Improvements

- Single version/path implementation for runtime and PyInstaller.
- Service container enables dependency injection in tests and future report workflows.
- Error handling has a central service for exception logging and future diagnostics.
- Splash and startup behavior remain isolated from heavy imports.
- Future report engine packages exist without being coupled to the current UI.
