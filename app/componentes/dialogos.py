"""Diálogos padronizados."""

from PyQt5 import QtWidgets

from app.tema import *  # noqa: F401,F403


DIALOG_CSS = (f"QDialog {{ background: {BG}; }} QLabel {{ color: {TEXT}; }}"
              f"QTableWidget {{ background: {SURFACE}; color: {TEXT}; gridline-color: {BORDER};"
              f" border: 1px solid {BORDER}; font-size: 13px; }}"
              f"QHeaderView::section {{ background: {SURFACE_HI}; color: {MUTED};"
              f" border: none; padding: 6px; font-weight: 600; font-size: 13px; }}")


class ConfirmDialog(QtWidgets.QDialog):
    def __init__(self, title, text, confirm, cancel, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet(DIALOG_CSS)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(10)
        v.addWidget(label(title, 17, TEXT, bold=True))
        msg = label(text, 14, MUTED)
        msg.setWordWrap(True)
        v.addWidget(msg)
        v.addSpacing(8)
        row = QtWidgets.QHBoxLayout()
        row.addStretch()
        b_cancel = button(cancel, None, "secondary")
        b_ok = button(confirm, None, "primary")
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self.accept)
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        v.addLayout(row)
        self.setMinimumWidth(420)


class ExportDialog(QtWidgets.QDialog):
    """Escolha da exportação: planilha para o Excel (como antes) ou dataset para pesquisa
    (pseudonimizado), com as opções que aumentam o risco de reidentificação desmarcadas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar dados")
        check_css = f"QCheckBox, QRadioButton {{ color: {TEXT}; font-size: 13px; spacing: 8px; }}"
        self.setStyleSheet(DIALOG_CSS + check_css)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(8)
        v.addWidget(label("Exportar dados", 17, TEXT, bold=True))
        self.sheet = QtWidgets.QRadioButton("Planilha para o Excel (uma linha por avaliação e dedo)")
        self.dataset = QtWidgets.QRadioButton("Dataset para pesquisa (pseudonimizado)")
        self.sheet.setChecked(True)
        v.addWidget(self.sheet)
        note = label("Identificada: inclui a identificação do paciente, a condição e as datas.", 12, MUTED)
        note.setWordWrap(True)
        v.addWidget(note)
        v.addWidget(self.dataset)
        note = label("Pasta com pacientes, avaliações, dedos, repetições e quadros (CSV), dicionário de dados, "
                     "LEIA-ME e checksums. Sem nome nem data de nascimento; uso em pesquisa exige aprovação do "
                     "CEP e consentimento.", 12, MUTED)
        note.setWordWrap(True)
        v.addWidget(note)
        self.free_text = QtWidgets.QCheckBox("Incluir texto livre (condição / diagnóstico do cadastro)")
        self.exact_dates = QtWidgets.QCheckBox("Exportar datas exatas (padrão: dias desde a 1ª avaliação)")
        self.image = QtWidgets.QCheckBox("Incluir as coordenadas 2D dos pontos na imagem")
        options = QtWidgets.QVBoxLayout()
        options.setContentsMargins(24, 0, 0, 0)
        for box in (self.free_text, self.exact_dates, self.image):
            options.addWidget(box)
        v.addLayout(options)
        self.dataset.toggled.connect(self._sync)
        self._sync()
        v.addSpacing(8)
        row = QtWidgets.QHBoxLayout()
        row.addStretch()
        b_cancel = button("Cancelar", None, "secondary")
        b_ok = button("Escolher a pasta…", None, "primary")
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self.accept)
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        v.addLayout(row)
        self.setMinimumWidth(520)

    def _sync(self):
        for box in (self.free_text, self.exact_dates, self.image):
            box.setEnabled(self.dataset.isChecked())

    def choice(self):
        """("planilha", None) ou ("dataset", {"incluir_texto_livre", "datas_exatas", "incluir_imagem"})."""
        if not self.dataset.isChecked():
            return "planilha", None
        return "dataset", {"incluir_texto_livre": self.free_text.isChecked(),
                           "datas_exatas": self.exact_dates.isChecked(),
                           "incluir_imagem": self.image.isChecked()}
