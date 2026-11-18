"""Barra do topo da avaliação: etapa e mão, qualidade da captura, estado do rastreamento
e tempo (a qualidade é calculada em captura/qualidade.py)."""

from PyQt5 import QtWidgets

from manumetria.interface.glossario import tip
from manumetria.interface.icones import pixmap
from manumetria.interface.tema import BG, BORDER, FAIR, GOOD, MUTED, ON_WARN, POOR, TEXT, WARN, label


class TopBar(QtWidgets.QFrame):
    """Só informação (nada clicável): etapa e mão, qualidade da captura,
    estado do rastreamento e tempo de sessão."""

    STATES = {
        # estado: (ícone, texto, cor do texto, fundo da barra)
        "tracking": ("dot", "Rastreando", GOOD, BG),
        "waiting": ("ring", "Aguardando a mão", MUTED, BG),
        "paused": ("pause", "Sessão pausada", FAIR, BG),
        "lost": ("alert", "Mão fora do quadro", ON_WARN, WARN),
        "other_hand": ("alert", "Outra mão na câmera", ON_WARN, WARN),
        "bad_view": ("alert", "Mão de lado: medição pausada", ON_WARN, WARN),
    }

    def __init__(self):
        super().__init__()
        self.setFixedHeight(48)
        self.setObjectName("top")
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(6)
        self.title = label("", 15, TEXT, bold=True)
        self.quality = QtWidgets.QLabel()
        self.status_icon = QtWidgets.QLabel()
        self.status = QtWidgets.QLabel()
        self.clock_icon = QtWidgets.QLabel()
        self.clock = QtWidgets.QLabel()
        for w in (self.status_icon, self.clock_icon):
            w.setStyleSheet("background: transparent;")   # a barra fica amarela no alerta
        h.addWidget(self.title)
        h.addStretch()
        h.addWidget(self.quality)
        h.addSpacing(24)
        h.addWidget(self.status_icon)
        h.addWidget(self.status)
        h.addSpacing(20)
        h.addWidget(self.clock_icon)
        h.addWidget(self.clock)
        self._state = self._quality = None
        self.set_state("waiting")

    def set_quality(self, level, text, details):
        """Qualidade da captura: "boa" / "regular" / "ruim" + motivo."""
        if (level, text) == self._quality:
            return
        self._quality = (level, text)
        self.quality.setText(text)
        self.quality.setToolTip(tip("qualidade_captura") + ("\n\n" + details if details else ""))
        self._style_quality()

    def _style_quality(self):
        dark = self._state in ("lost", "other_hand", "bad_view")
        level = self._quality[0] if self._quality else "boa"
        color = ON_WARN if dark else {"boa": MUTED, "regular": FAIR, "ruim": POOR}[level]
        self.quality.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")

    def set_state(self, state):
        """Estado do rastreamento (chave de STATES): ícone, texto e cor da barra."""
        if state == self._state:
            return
        self._state = state
        icon_name, text, color, bg = self.STATES[state]
        dark = bg == WARN
        fg = ON_WARN if dark else TEXT
        self.setStyleSheet(f"#top {{ background: {bg}; border-bottom: 1px solid {BORDER}; }}")
        self.status_icon.setPixmap(pixmap(icon_name, color, 16))
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600;"
                                  " background: transparent;")
        self.title.setStyleSheet(f"color: {fg}; font-size: 15px; font-weight: 700; background: transparent;")
        self.clock_icon.setPixmap(pixmap("clock", fg, 16))
        self.clock.setStyleSheet(f"color: {fg}; font-size: 15px; background: transparent;")
        self._style_quality()
