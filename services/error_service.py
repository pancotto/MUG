"""Centralized exception logging and user-message formatting."""

from __future__ import annotations

from infrastructure.logging_config import get_logger


class ErrorService:
    def __init__(self):
        self._logger = get_logger(__name__)

    def log_exception(self, exc: BaseException, context: str = "") -> None:
        message = context or "Unhandled application exception"
        self._logger.exception("%s: %s", message, exc)

    def format_user_message(self, title: str, details: str | BaseException) -> str:
        detail_text = str(details).strip()
        if not detail_text:
            return title
        return f"{title}\n\n{detail_text}"

    def friendly_startup_message(self, log_path: str | None = None) -> str:
        message = (
            "O MUG encontrou um erro inesperado durante a inicialização.\n\n"
            "O erro foi registrado no log.\n\n"
            "Se o problema persistir, entre em contato com o suporte e envie o arquivo de log."
        )
        if log_path:
            message += f"\n\nArquivo de log:\n{log_path}"
        return message

    def friendly_processing_message(self) -> str:
        return (
            "A medição selecionada não pôde ser processada.\n\n"
            "Verifique se o arquivo é válido e tente novamente."
        )

    def friendly_graph_rendering_message(self) -> str:
        return (
            "Os dados foram processados, mas os gráficos não puderam ser montados.\n\n"
            "A medição selecionada foi preservada. Tente gerar os gráficos novamente. "
            "Se o problema persistir, consulte o arquivo de log."
        )

    def friendly_filter_message(self) -> str:
        return (
            "Não foi possível aplicar o intervalo selecionado.\n\n"
            "Verifique as datas e horários informados e tente novamente."
        )

    def friendly_zoom_message(self) -> str:
        return (
            "Não foi possível sincronizar o zoom dos gráficos.\n\n"
            "Tente restaurar a visualização ou aplicar a seleção novamente."
        )

    def friendly_export_message(self) -> str:
        return (
            "Não foi possível concluir a exportação.\n\n"
            "Verifique a pasta de destino, confirme que há espaço disponível "
            "e tente novamente. Os detalhes técnicos foram registrados no log."
        )
