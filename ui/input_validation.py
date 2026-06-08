from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit


def enable_uppercase_input(line_edit: QLineEdit):
    def force_uppercase(value: str):
        cursor_position = line_edit.cursorPosition()
        upper_value = value.upper()
        if value != upper_value:
            line_edit.setText(upper_value)
            line_edit.setCursorPosition(cursor_position)

    line_edit.textEdited.connect(force_uppercase)


def set_digits_only_validator(line_edit: QLineEdit):
    line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d*"), line_edit))


def set_decimal_number_validator(line_edit: QLineEdit):
    line_edit.setValidator(
        QRegularExpressionValidator(QRegularExpression(r"\d*([,.]\d*)?"), line_edit)
    )
