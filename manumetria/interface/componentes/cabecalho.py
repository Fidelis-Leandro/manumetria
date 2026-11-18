"""Cabeçalho padrão das telas: voltar (opcional), título, subtítulo e ações à direita."""

from PyQt5 import QtCore, QtWidgets

from manumetria.interface.tema import BG, BORDER, MUTED, TEXT, button, label


class ScreenHeader(QtWidgets.QFrame):
    """Cabeçalho das telas: botão de voltar (sinal back), título e ações à direita."""

    back = QtCore.pyqtSignal()

    def __init__(self, title, back_text=None):
        super().__init__()
        self.setObjectName("header")
        self.setStyleSheet(f"#header {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}")
        self.setFixedHeight(64)
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(12)
        if back_text:
            b = button(back_text, "back", "quiet")
            b.clicked.connect(self.back.emit)
            h.addWidget(b)
            h.addSpacing(4)
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(0)
        self.title = label(title, 18, TEXT, bold=True)
        self.subtitle = label("", 13, MUTED)
        col.addWidget(self.title)
        col.addWidget(self.subtitle)
        h.addLayout(col)
        h.addStretch()
        self.actions = QtWidgets.QHBoxLayout()
        self.actions.setSpacing(8)
        h.addLayout(self.actions)

    def add_action(self, widget):
        """Põe um widget (ex.: botão) nas ações do cabeçalho e o devolve."""
        self.actions.addWidget(widget)
        return widget
