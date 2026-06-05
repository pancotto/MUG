from pathlib import Path

from ui.graph_page import (
    format_export_canceled_message,
    format_export_error_message,
    format_pdf_success_message,
)


def test_format_pdf_success_message_single_pdf():
    message = format_pdf_success_message([r"C:\saida\GR - ASD - 20260605-082832 - REV00.pdf"])

    assert "1 PDF gerado com sucesso." in message
    assert "Local:" in message
    assert "PDF(s)" not in message
    assert r"C:\saida\GR - ASD - 20260605-082832 - REV00.pdf" in message


def test_format_pdf_success_message_multiple_pdfs():
    message = format_pdf_success_message(
        ["a.pdf", "b.pdf", "c.pdf"],
        Path(r"C:\saida\graficos"),
    )

    assert "3 PDFs gerados com sucesso." in message
    assert "Pasta:" in message
    assert "PDF(s)" not in message
    assert r"C:\saida\graficos" in message
    assert "a.pdf" not in message


def test_format_export_canceled_message():
    assert (
        format_export_canceled_message()
        == "A exportação foi interrompida pelo usuário."
    )


def test_format_export_error_message():
    message = format_export_error_message("falha de teste")

    assert "Não foi possível concluir a exportação." in message
    assert "falha de teste" in message
