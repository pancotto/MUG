# Arquitetura do MUG

Este documento descreve a arquitetura atual do MUG, com foco no fluxo de dados desde a leitura dos arquivos até a geração dos gráficos e a exportação em PDF.

## Visão Geral

O MUG é uma aplicação desktop PySide6 para análise gráfica de grandezas elétricas. A arquitetura é organizada em duas áreas principais:

- `core/`: regras de leitura, ETL, modelos de dados, geração de gráficos e exportação PDF.
- `ui/`: interface desktop, navegação, formulários, renderização interativa e orquestração de tarefas em segundo plano.

Fluxo principal:

```text
ui.input_page.InputPage
  -> core.models.InputData
  -> core.excel_reader.process_input_data()
  -> core.models.ProcessedData
  -> ui.main_window.MainWindow.set_processed_data()
  -> ui.graph_page.GraphPage.load_processed_data()
  -> core.graph_builder.create_*_graph()
  -> Plotly HTML em QWebEngineView
  -> ui.graph_page.PdfExportTab
  -> core.pdf_exporter.export_figures_to_pdf()
```

## Fluxo ETL

O ETL fica concentrado em `core/excel_reader.py`.

### Entrada

A tela inicial coleta dados operacionais e o caminho do arquivo selecionado pelo usuário. Esses dados são empacotados em um `InputData`.

Arquivos aceitos:

- `.xlsx` exportado pelo Primata P55;
- `.txt` exportado pelo Primata P55;
- `.txt` exportado pelo Embrasul RE7080.

### Extração

`process_input_data()` identifica a extensão do arquivo e escolhe a rotina adequada:

- `read_primata_excel()` para Primata `.xlsx`;
- `read_primata_txt()` para Primata `.txt`;
- `read_embrasul_txt_as_primata_dataframe()` para Embrasul `.txt`.

Para arquivos `.txt`, a função `detect_txt_type()` inspeciona o conteúdo inicial do arquivo e decide se o formato é Primata, Embrasul ou desconhecido.

### Transformação

A transformação tem duas responsabilidades centrais:

1. Normalizar arquivos de origens diferentes para um formato interno comum.
2. Preparar os dados para consumo direto pelos gráficos.

O Embrasul é convertido para um DataFrame compatível com o padrão interno usado pelos gráficos, com nomes de colunas equivalentes ao padrão Primata. Essa decisão evita que os gráficos precisem conhecer detalhes da origem do arquivo.

Depois da leitura específica, `prepare_common_dataframe()`:

- valida a existência das colunas `Data` e `Hora `;
- cria a coluna `Datetime`;
- remove registros com data/hora inválidas;
- ordena os registros por `Datetime`;
- converte colunas numéricas, aceitando formatos com vírgula ou ponto decimal.

### Enriquecimento

Após a normalização comum, o ETL infere dados técnicos usados em gráficos e relatórios:

- `infer_integration_time()`: calcula o intervalo típico entre medições;
- `infer_nominal_tension()`: estima a tensão nominal a partir das colunas de tensão disponíveis.

O resultado final do ETL é um `ProcessedData`.

## Fluxo ProcessedData

`ProcessedData`, definido em `core/models.py`, é o contrato principal entre a camada de processamento, os gráficos e a exportação PDF.

Ele carrega:

- dados de identificação do relatório, como empresa, cidade, local e revisão;
- informações do equipamento;
- caminho do arquivo original;
- DataFrame normalizado;
- tempo de integração inferido;
- tensão nominal inferida;
- tipo de equipamento, como transformador ou disjuntor.

Também encapsula cálculos e textos usados por gráficos:

- corrente nominal;
- potência aparente nominal ou equivalente;
- limite de referência para potência;
- descrição do equipamento;
- texto de tensão exibido em títulos;
- anotação de potência nominal ou equivalente.

Essa arquitetura permite que `core/graph_builder.py` e `core/pdf_exporter.py` trabalhem com um pacote de dados único e estável, sem depender da UI ou do formato original do arquivo.

## Geração de Gráficos

A geração de gráficos fica em `core/graph_builder.py`.

Cada função `create_*_graph()` recebe um `ProcessedData` e retorna um `plotly.graph_objects.Figure`.

Gráficos atuais:

- tensão;
- corrente;
- potência ativa;
- potência aparente;
- fator de potência;
- desequilíbrio de tensão;
- desequilíbrio de corrente;
- DHT de tensão;
- DHT de corrente;
- consumo;
- tensão x corrente;
- kW x kVA.

Os gráficos usam `ProcessedData.dataframe` como fonte e os metadados do `ProcessedData` para títulos, subtítulos, limites, referências nominais e anotações.

`apply_common_layout()` centraliza parte do padrão visual:

- fundo branco;
- formatação de eixo X;
- margens;
- fonte;
- legenda;
- logo opcional.

Alguns gráficos possuem regras específicas, como:

- faixas adequadas/críticas de tensão;
- corrente nominal;
- potência nominal ou equivalente;
- pontos máximos e mínimos;
- agrupamento diário de consumo;
- composição de gráficos combinados a partir de gráficos existentes.

## Renderização Plotly

A renderização interativa acontece em `ui/graph_page.py`.

`GraphPage.load_processed_data()` recebe um `ProcessedData` e chama `_rebuild_figures_for_range()`, que cria todas as figuras Plotly para o intervalo atual.

Depois, cada figura é renderizada por `_render_webview_figure()`:

```text
Plotly Figure
  -> fig.to_html()
  -> arquivo HTML temporário
  -> QWebEngineView.load()
```

O HTML gerado inclui JavaScript adicional para capturar eventos de zoom do Plotly. Esses eventos são enviados para Python usando `QWebChannel` e `PlotBridge`.

Quando o zoom muda:

```text
Plotly relayout event
  -> PlotBridge.onZoomChanged()
  -> GraphPage._on_zoom_changed()
  -> filtro por intervalo Datetime
  -> recriação dos gráficos
  -> recarregamento das abas
```

Essa abordagem mantém os gráficos sincronizados entre si. Quando o usuário aplica zoom em um gráfico, os demais são reconstruídos com o mesmo intervalo de tempo.

## Exportação PDF

A exportação PDF envolve `ui/graph_page.py` e `core/pdf_exporter.py`.

### Orquestração na UI

`PdfExportTab` permite selecionar quais gráficos serão exportados.

Ao exportar:

1. a UI valida se há gráficos selecionados;
2. o usuário escolhe a pasta de destino;
3. a UI verifica se há zoom ativo;
4. se houver zoom, cria um novo `ProcessedData` com o DataFrame filtrado;
5. inicia um `PdfExportWorker` em `QThread`.

O uso de `QThread` evita travar a interface durante a renderização estática e montagem do PDF.

### Geração do PDF

`export_figures_to_pdf()` executa o fluxo principal:

```text
selected_graphs
  -> build_pdf_figures()
  -> create_*_graph(show_logo=True)
  -> apply_pdf_visual_standard()
  -> save_figure_as_jpeg()
  -> FPDF.add_page()
  -> FPDF.image()
  -> PDF final
```

Características preservadas:

- exporta apenas gráficos selecionados;
- segue a ordem definida por `GRAPH_EXPORT_ORDER`;
- usa formato A4 horizontal;
- coloca um gráfico por página;
- usa imagens temporárias JPEG;
- remove imagens temporárias ao final;
- gera nome de arquivo com empresa, timestamp e revisão.

### Plotly, Kaleido e Chromium

Para colocar os gráficos no PDF, o Plotly precisa ser convertido em imagem estática. Isso é feito por Kaleido, via `plotly.io.to_image()`.

Como o Kaleido depende de Chrome/Chromium, `core/pdf_exporter.py` tenta localizar um navegador portátil empacotado com a aplicação e configura `BROWSER_PATH` quando possível. Esse comportamento é importante para builds PyInstaller, nos quais o usuário final não deve precisar configurar manualmente um navegador.

## Responsabilidades dos Módulos

### `core/models.py`

Define os contratos de dados:

- `InputData`;
- `ProcessedData`;
- constantes de tipo de equipamento;
- helpers de formatação e normalização.

Também concentra cálculos derivados ligados ao equipamento e ao relatório.

### `core/excel_reader.py`

Responsável por:

- detectar tipo de arquivo;
- ler Primata `.xlsx`;
- ler Primata `.txt`;
- ler Embrasul `.txt`;
- converter Embrasul para o padrão interno;
- normalizar datas, horas e números;
- inferir tempo de integração;
- inferir tensão nominal;
- produzir `ProcessedData`.

### `core/graph_builder.py`

Responsável por:

- criar figuras Plotly;
- aplicar layout comum;
- adicionar limites, referências e anotações;
- compor gráficos combinados;
- manter regras visuais e técnicas dos gráficos.

Não deve ler arquivos diretamente nem depender de widgets da UI.

### `core/pdf_exporter.py`

Responsável por:

- definir a ordem de exportação;
- reconstruir gráficos para PDF;
- aplicar padrão visual específico do PDF;
- configurar Chromium/Kaleido quando possível;
- converter figuras Plotly em imagens;
- montar o PDF A4 horizontal com FPDF;
- limpar arquivos temporários.

### `ui/input_page.py`

Responsável por:

- construir o formulário inicial;
- validar entradas do usuário;
- selecionar arquivo de dados;
- montar `InputData`;
- executar o processamento em worker thread;
- enviar `ProcessedData` para a janela principal.

### `ui/main_window.py`

Responsável por:

- criar a janela principal;
- alternar entre entrada e gráficos;
- armazenar o `ProcessedData` atual;
- iniciar nova análise;
- verificar atualizações.

### `ui/graph_page.py`

Responsável por:

- criar abas de gráficos;
- renderizar figuras Plotly em `QWebEngineView`;
- sincronizar zoom entre gráficos;
- recriar gráficos para intervalos filtrados;
- gerenciar a aba de exportação PDF;
- executar exportação PDF em worker thread.

## Diretrizes de Evolução

Ao evoluir a arquitetura:

- preserve `ProcessedData` como fronteira entre ETL, gráficos e PDF;
- mantenha parsing e normalização dentro de `core/excel_reader.py`;
- mantenha gráficos sem dependência da UI;
- mantenha exportação PDF sem dependência de widgets;
- evite refactors amplos sem necessidade clara;
- preserve compatibilidade com PyInstaller;
- preserve o fluxo Kaleido/Chromium para PDF;
- mantenha tarefas pesadas fora da thread principal da UI.
