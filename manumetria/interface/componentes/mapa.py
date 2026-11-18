"""Mapa da evolução: todas as articulações (linhas) em todas as avaliações
(colunas), cada célula colorida pela flexão máxima em % do normal da
articulação. Mostra de relance qual articulação está atrasada."""

from PyQt5 import QtCore, QtGui, QtWidgets

from manumetria.calculo import goniometria
from manumetria.formato import fmt_date
from manumetria.interface.tema import (FAIR, GOOD, GRADE_COLOR, MUTED, POOR, TABLE_BASE_CSS, label,
                                       qcolor, swatch, table)

ROWS = [(f, i, name) for f in goniometria.FINGERS for i, (name, _) in enumerate(goniometria.JOINTS[f])]


class EvolutionMap(QtWidgets.QWidget):
    """Clicar numa célula emite open_joint(dedo, índice da articulação)."""

    open_joint = QtCore.pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self.table = table(["Articulação"])
        self.table.setStyleSheet(TABLE_BASE_CSS)             # deixa a cor de fundo de cada célula aparecer
        self.table.setShowGrid(True)                         # grade fina separa as células coloridas
        self.table.cellClicked.connect(self._clicked)
        v.addWidget(self.table, stretch=1)
        legend = label(f"{swatch(POOR)} abaixo de {goniometria.GRADE_FAIR * 100:.0f}% &nbsp; "
                       f"{swatch(FAIR)} {goniometria.GRADE_FAIR * 100:.0f}–{goniometria.GRADE_GOOD * 100:.0f}% &nbsp; "
                       f"{swatch(GOOD)} acima de {goniometria.GRADE_GOOD * 100:.0f}% &nbsp;·&nbsp; "
                       "flexão máxima em % do normal da articulação  ·  clique numa célula para ver o gráfico",
                       12, MUTED)
        legend.setWordWrap(True)
        v.addWidget(legend)

    def set_data(self, sessions):
        """Preenche o mapa: uma coluna por avaliação, uma linha por articulação."""
        t = self.table
        t.clear()
        t.setColumnCount(1 + len(sessions))
        t.setHorizontalHeaderLabels(["Articulação"] + [fmt_date(s["inicio"])[:5] for s in sessions])
        t.setRowCount(len(ROWS))
        for r, (f, i, name) in enumerate(ROWS):
            first = name == goniometria.JOINTS[f][0][0]              # nome do dedo só na primeira linha dele
            head = QtWidgets.QTableWidgetItem(f"{goniometria.NAME[f] if first else ''}  {name}".strip())
            head.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            t.setItem(r, 0, head)
            normal = goniometria.NORMAL_JOINT[f][name]
            for c, s in enumerate(sessions, start=1):
                value = s["resultados"]["dedos"][f]["articulacoes"][i]["max"]
                item = QtWidgets.QTableWidgetItem("--" if value is None else f"{value / normal * 100:.0f}%")
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if value is not None:
                    color = GRADE_COLOR[goniometria.grade(value / normal)]
                    item.setBackground(QtGui.QBrush(qcolor(color, 110)))
                    item.setToolTip(f"{name} do {goniometria.NAME[f].lower()}, {fmt_date(s['inicio'])}:\n"
                                    f"flexão máxima {value:.0f}° de {normal:.0f}° (normal)")
                t.setItem(r, c, item)
            t.setRowHeight(r, 26)
        if sessions:
            t.scrollToItem(t.item(0, len(sessions)))          # avaliações mais recentes à vista

    def _clicked(self, row, col):
        if col > 0:
            f, i, _ = ROWS[row]
            self.open_joint.emit(f, i)
