"""Configurações: relatório (instituição, título, logotipo, profissional padrão),
interface (tema escuro ou claro) e medição (suavização do sinal: calculo/filtros.py).

O logotipo aparece apenas no relatório final (PDF); aqui só o nome e o tamanho do arquivo.
O tema é lido ao abrir o programa: ao trocar, oferece reiniciar."""

import html
import os
import shutil

from PyQt5 import QtCore, QtGui, QtWidgets

from manumetria.calculo import filtros
from manumetria.dados import configuracoes as cfgmod, recalculo
from manumetria.formato import fmt_datetime, fmt_num, fmt_pct
from manumetria.interface.componentes.cabecalho import ScreenHeader
from manumetria.interface.componentes.dialogos import ConfirmDialog, DIALOG_CSS
from manumetria.interface.glossario import explain
from manumetria.interface.tema import (BORDER, FAIR, GOOD, INPUT_CSS, MUTED, SCALE, SCALES, TEXT, THEME,
                                       button, card, label, qcolor, table)
from manumetria.relatorios.pdf import LOGO_H


def _section(text):
    return label(text, 14, TEXT, bold=True)


class RecalcDialog(QtWidgets.QDialog):
    """Mostra o que muda ao recalcular as avaliações e só grava se confirmar."""

    COLUMNS = ["Data", "Paciente", "% normal antes", "depois", "Maior diferença", "Situação"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db, self.items = db, []
        self.setWindowTitle("Recalcular avaliações")
        self.setStyleSheet(DIALOG_CSS)
        self.resize(900, 520)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(label("Recalcular avaliações", 17, TEXT, bold=True))
        text = label("Passa os pontos da mão gravados em cada avaliação pelo cálculo atual do sistema. "
                     "Data, duração e observações não mudam, e os resultados anteriores ficam guardados "
                     "na própria avaliação. Cada avaliação usa o filtro de suavização registrado nela "
                     "(sem registro: Desligada). Avaliações salvas antes de 15/10/2026 não têm pontos "
                     "gravados.",
                     13, MUTED)
        text.setWordWrap(True)
        v.addWidget(text)
        self.table = table(self.COLUMNS, stretch=(1, 5))     # paciente e situação dividem a sobra
        v.addWidget(self.table, stretch=1)
        self.status = label("Calculando…", 13, TEXT)
        v.addWidget(self.status)
        row = QtWidgets.QHBoxLayout()
        row.addStretch()
        b_close = button("Fechar", None, "secondary")
        b_close.clicked.connect(self.reject)
        self.b_apply = button("Atualizar", "check", "primary")
        self.b_apply.setEnabled(False)
        self.b_apply.clicked.connect(self._apply)
        row.addWidget(b_close)
        row.addWidget(self.b_apply)
        v.addLayout(row)
        QtCore.QTimer.singleShot(50, self._compute)     # mostra a janela antes de calcular

    def _progress(self, i, total):
        self.status.setText(f"Calculando {i + 1} de {total}…")
        QtWidgets.QApplication.processEvents()

    def _compute(self):
        self.items = recalculo.preparar(self.db, self._progress)
        self.table.setRowCount(len(self.items))
        for r, it in enumerate(self.items):
            diff = it["maior_diferenca"]
            cells = [fmt_datetime(it["sessao"]["inicio"]), it["paciente"], fmt_pct(it["antes"]),
                     fmt_pct(it["depois"]) if it["novo"] else "--",
                     "--" if diff is None else fmt_num(diff, 1, "°"), it["motivo"]]
            for c, value in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(value)
                if c != 1:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                if c == 5 and it["novo"] is None:
                    item.setForeground(QtGui.QBrush(qcolor(MUTED)))
                self.table.setItem(r, c, item)
        ready = sum(it["novo"] is not None for it in self.items)
        self.status.setText(f"{ready} de {len(self.items)} avaliações têm pontos gravados e podem ser "
                            "recalculadas." if ready else "Nenhuma avaliação tem pontos gravados.")
        self.b_apply.setEnabled(ready > 0)

    def _apply(self):
        done = recalculo.aplicar(self.db, self.items)
        self.status.setText(f"{done} {'avaliação atualizada' if done == 1 else 'avaliações atualizadas'}. "
                            "Os resultados anteriores ficam guardados em cada uma.")
        self.b_apply.setEnabled(False)


class SettingsScreen(QtWidgets.QWidget):
    """Tela de Configurações; save() grava e emite `saved` (e `restart_requested` se
    o tema ou o tamanho mudou e o usuário quis reiniciar)."""

    back = QtCore.pyqtSignal()
    saved = QtCore.pyqtSignal(dict)
    restart_requested = QtCore.pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.header = ScreenHeader("Configurações", back_text="Pacientes")
        self.header.subtitle.setText("Relatório em PDF, aparência da interface e medição")
        self.header.back.connect(self.back.emit)
        v.addWidget(self.header)

        box = card("settingsCard")
        box.setMaximumWidth(760)
        f = QtWidgets.QFormLayout(box)
        f.setContentsMargins(22, 18, 22, 18)
        f.setHorizontalSpacing(16)
        f.setVerticalSpacing(12)
        f.setLabelAlignment(QtCore.Qt.AlignRight)
        f.addRow(_section("Relatório em PDF"))
        self.institution = QtWidgets.QLineEdit()
        self.title = QtWidgets.QLineEdit()
        self.professional = QtWidgets.QLineEdit()
        self.professional.setPlaceholderText("Preenche o campo Profissional no cadastro de pacientes")
        for w in (self.institution, self.title, self.professional):
            w.setStyleSheet(INPUT_CSS)
        f.addRow(label("Instituição", 13, MUTED), self.institution)
        f.addRow(label("Título do relatório", 13, MUTED), self.title)
        f.addRow(label("Profissional padrão", 13, MUTED), self.professional)

        self.logo_info = label("", 13, TEXT)
        self.logo_info.setTextFormat(QtCore.Qt.RichText)
        self.logo_info.setWordWrap(True)
        f.addRow(label("Logotipo", 13, MUTED), self.logo_info)
        logo_row = QtWidgets.QHBoxLayout()
        logo_row.setSpacing(8)
        b_choose = button("Escolher arquivo", "file", "secondary")
        b_remove = button("Remover", "trash", "secondary")
        b_choose.clicked.connect(self.choose_logo)
        b_remove.clicked.connect(self.remove_logo)
        logo_row.addWidget(b_choose)
        logo_row.addWidget(b_remove)
        logo_row.addStretch()
        f.addRow("", logo_row)
        hint = label("O logotipo aparece apenas no relatório final (PDF). Use o arquivo oficial, de "
                     "preferência PNG com fundo transparente. Sem logotipo, o PDF mostra o nome da "
                     "instituição em texto.", 12, MUTED)
        hint.setWordWrap(True)
        f.addRow("", hint)

        line = QtWidgets.QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {BORDER};")
        f.addRow(line)
        f.addRow(_section("Interface"))
        theme_row = QtWidgets.QHBoxLayout()
        theme_row.setSpacing(6)
        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        self.theme_buttons = {}
        for key, text in (("escuro", "Escuro"), ("claro", "Claro")):
            b = button(text, None, "quiet", checkable=True)
            b.setMinimumWidth(96)
            group.addButton(b)
            theme_row.addWidget(b)
            self.theme_buttons[key] = b
        theme_row.addStretch()
        f.addRow(label("Tema", 13, MUTED), theme_row)
        scale_row = QtWidgets.QHBoxLayout()
        scale_row.setSpacing(6)
        scale_group = QtWidgets.QButtonGroup(self)
        scale_group.setExclusive(True)
        self.scale_buttons = {}
        for value, text in SCALES.items():
            b = button(f"{text} ({value * 100:.0f}%)", None, "quiet", checkable=True)
            scale_group.addButton(b)
            scale_row.addWidget(b)
            self.scale_buttons[value] = b
        scale_row.addStretch()
        f.addRow(label("Tamanho", 13, MUTED), scale_row)
        theme_hint = label("Tamanho aumenta texto, botões e ícones juntos. As trocas valem ao reiniciar "
                           "o programa. A área da câmera e do modelo 3D continua escura nos dois temas, "
                           "como uma tela de vídeo.", 12, MUTED)
        theme_hint.setWordWrap(True)
        f.addRow("", theme_hint)

        line_m = QtWidgets.QFrame()
        line_m.setFixedHeight(1)
        line_m.setStyleSheet(f"background: {BORDER};")
        f.addRow(line_m)
        f.addRow(_section("Medição"))
        smooth_row = QtWidgets.QHBoxLayout()
        smooth_row.setSpacing(6)
        smooth_group = QtWidgets.QButtonGroup(self)
        smooth_group.setExclusive(True)
        self.smooth_buttons = {}
        for key, text in filtros.MODOS.items():
            b = button(text, None, "quiet", checkable=True)
            b.setMinimumWidth(96)
            smooth_group.addButton(b)
            smooth_row.addWidget(b)
            self.smooth_buttons[key] = b
        smooth_row.addStretch()
        smooth_label = label("Suavização do sinal", 13, MUTED)
        explain(smooth_label, "suavizacao")
        f.addRow(smooth_label, smooth_row)
        self.smooth_measures = QtWidgets.QCheckBox(
            "Aplicar a suavização também nas medidas (como no pipeline do artigo)")
        self.smooth_measures.setStyleSheet(f"QCheckBox {{ color: {TEXT}; font-size: 13px; spacing: 8px; }}")
        explain(self.smooth_measures, "suavizacao_medidas")
        f.addRow("", self.smooth_measures)
        smooth_hint = label(
            "Filtro aplicado aos ângulos de cada articulação, como no artigo EMA × Kalman: reduz a tremedeira "
            "da câmera, mas atrasa um pouco o sinal (EMA + Kalman: cerca de "
            f"{fmt_num(filtros.atraso_quadros(filtros.registro(filtros.CASCATA)), 0)} quadros). Padrão: "
            f"{filtros.MODOS[filtros.PADRAO]} só na exibição ao vivo (valor \"Agora\", gráfico do TAM e dica "
            "da mão 3D); as medidas da avaliação usam os dados brutos. Com a caixa marcada, o filtro entra "
            "também nas medidas e achata os picos (menos flexão máxima, velocidade de pico e repetições). "
            "Vale para as avaliações novas; cada avaliação guarda o filtro usado, e o recálculo usa sempre "
            "o da própria avaliação.", 12, MUTED)
        smooth_hint.setWordWrap(True)
        f.addRow("", smooth_hint)

        actions = QtWidgets.QHBoxLayout()
        self.status = label("", 12, GOOD)
        actions.addWidget(self.status)
        actions.addStretch()
        b_save = button("Salvar", "check", "primary")
        b_save.clicked.connect(self.save)
        actions.addWidget(b_save)
        f.addRow("", actions)

        line2 = QtWidgets.QFrame()
        line2.setFixedHeight(1)
        line2.setStyleSheet(f"background: {BORDER};")
        f.addRow(line2)
        f.addRow(_section("Dados"))
        b_recalc = button("Recalcular avaliações…", "refresh", "secondary")
        b_recalc.clicked.connect(lambda: RecalcDialog(self.db, self).exec_())
        recalc_row = QtWidgets.QHBoxLayout()
        recalc_row.addWidget(b_recalc)
        recalc_row.addStretch()
        f.addRow(label("Avaliações salvas", 13, MUTED), recalc_row)
        recalc_hint = label("Use depois de uma atualização do sistema que corrija um cálculo ou traga uma "
                            "medida nova: as avaliações antigas passam a ser medidas do mesmo jeito que as "
                            "novas. Antes de gravar, mostra o que muda.", 12, MUTED)
        recalc_hint.setWordWrap(True)
        f.addRow("", recalc_hint)

        content = QtWidgets.QWidget()
        wrap = QtWidgets.QHBoxLayout(content)
        wrap.setContentsMargins(24, 20, 24, 20)
        wrap.addWidget(box, alignment=QtCore.Qt.AlignTop)
        wrap.addStretch()
        scroll = QtWidgets.QScrollArea()             # rola em telas baixas / interface grande
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidget(content)
        v.addWidget(scroll, stretch=1)
        self.cfg = {}

    def load(self):
        """Preenche a tela com as configurações salvas."""
        self.cfg = cfgmod.load()
        self.institution.setText(self.cfg["instituicao"])
        self.title.setText(self.cfg["titulo"])
        self.professional.setText(self.cfg["profissional_padrao"])
        self.theme_buttons.get(self.cfg.get("tema"), self.theme_buttons["escuro"]).setChecked(True)
        scale = min(SCALES, key=lambda s: abs(s - float(self.cfg.get("escala", 1.0))))
        self.scale_buttons[scale].setChecked(True)
        smooth = self.cfg.get("suavizacao")
        self.smooth_buttons.get(smooth, self.smooth_buttons[filtros.PADRAO]).setChecked(True)
        self.smooth_measures.setChecked(bool(self.cfg.get("suavizacao_medidas", False)))
        self.status.setText("")
        self._show_logo()

    def _show_logo(self):
        path = cfgmod.logo_path(self.cfg)
        img = QtGui.QImage(path) if path else QtGui.QImage()
        if img.isNull():
            self.logo_info.setText(f"<span style='color:{MUTED};'>Nenhum logotipo escolhido.</span>")
            return
        text = f"{html.escape(os.path.basename(path))}  ·  {img.width()} × {img.height()} px"
        if img.height() < LOGO_H * 1.5:          # menos de ~180 dpi no papel
            text += f"<br><span style='color:{FAIR};'>Resolução baixa: pode sair borrado no PDF.</span>"
        self.logo_info.setText(text)

    def choose_logo(self):
        """Escolhe uma imagem e a copia para dados_locais; o relatório passa a usá-la ao
        salvar as configurações."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Escolher logotipo", "",
                                                        "Imagens (*.png *.jpg *.jpeg)")
        if not path:
            return
        os.makedirs(cfgmod.LOGO_DIR, exist_ok=True)
        dest = os.path.join(cfgmod.LOGO_DIR, "logo_relatorio" + os.path.splitext(path)[1].lower())
        shutil.copyfile(path, dest)                   # cópia em dados_locais; o padrão fica intacto
        self.cfg["logo"] = os.path.relpath(dest, cfgmod.ROOT).replace(os.sep, "/")
        self._show_logo()

    def remove_logo(self):
        """Relatório sem logotipo (vale ao salvar)."""
        self.cfg["logo"] = ""
        self._show_logo()

    def save(self):
        """Grava as configurações; se o tema ou o tamanho mudou, oferece reiniciar."""
        theme = next(k for k, b in self.theme_buttons.items() if b.isChecked())
        scale = next(k for k, b in self.scale_buttons.items() if b.isChecked())
        smooth = next(k for k, b in self.smooth_buttons.items() if b.isChecked())
        self.cfg.update(instituicao=self.institution.text().strip() or cfgmod.DEFAULTS["instituicao"],
                        titulo=self.title.text().strip() or cfgmod.DEFAULTS["titulo"],
                        profissional_padrao=self.professional.text().strip(), tema=theme, escala=scale,
                        suavizacao=smooth, suavizacao_medidas=self.smooth_measures.isChecked())
        cfgmod.save(self.cfg)
        self.saved.emit(self.cfg)
        if theme == THEME and abs(scale - SCALE) < 0.01:   # aparência em uso não mudou
            self.status.setText("Configurações salvas.")
            return
        self.status.setText("Configurações salvas. A aparência muda ao reiniciar o programa.")
        dlg = ConfirmDialog("Reiniciar o programa agora?",
                            "O tema e o tamanho da interface são aplicados ao abrir o programa de novo.",
                            "Reiniciar agora", "Depois", self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.restart_requested.emit()
