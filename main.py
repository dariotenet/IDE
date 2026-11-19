from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QFileDialog, QMessageBox, QFrame, QDockWidget,
    QTextEdit, QToolBar, QStackedWidget, QTabWidget, QAction, QMenu,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QTableWidget, QTableWidgetItem,
    QProxyStyle, QStyle
)
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, QSize, QPointF, QRect
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QPolygonF, QPixmap, QIcon
import sys
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from code_editor import LexicalHighlighter
from lexico import AnalizadorLexico
from sintactico import AnalizadorSintactico
from semantico import AnalizadorSemantico
from generador_tm import GeneradorTM
from generador_ci import GeneradorCodigoIntermedio


class TreeBranchStyle(QProxyStyle):
    """Dibuja las flechas de expansión/colapso de los QTreeWidget con estilo moderno."""
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorBranch:
            if option.state & QStyle.State_Children:
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing, True)
                color = QColor("#ffffff") if (option.state & QStyle.State_MouseOver) else QColor("#9cdcfe")
                pen = QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                cx = option.rect.center().x()
                cy = option.rect.center().y()
                if option.state & QStyle.State_Open:
                    puntos = QPolygonF([
                        QPointF(cx - 4.5, cy - 2.0),
                        QPointF(cx, cy + 2.5),
                        QPointF(cx + 4.5, cy - 2.0)
                    ])
                else:
                    puntos = QPolygonF([
                        QPointF(cx - 2.0, cy - 4.5),
                        QPointF(cx + 2.5, cy),
                        QPointF(cx - 2.0, cy + 4.5)
                    ])
                painter.drawPolyline(puntos)
                painter.restore()
            return
        super().drawPrimitive(element, option, painter, widget)


class Main(QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        ui_path = os.path.join(BASE_DIR, "main.ui")
        loadUi(ui_path, self)

        # Ocultar opciones innecesarias del menú View (Light Theme y Font Size)
        acciones_ocultar = []
        for attr in ("actionLight_Theme", "actionIncrease_font_size", "actionDecrease_Font_Size"):
            if hasattr(self, attr):
                act = getattr(self, attr)
                act.setVisible(False)
                acciones_ocultar.append(act)
                for widget in act.associatedWidgets():
                    widget.removeAction(act)

        if hasattr(self, "menuTheme"):
            self.menuTheme.menuAction().setVisible(False)
        if hasattr(self, "menuView"):
            for act_menu in self.menuView.actions():
                sub = act_menu.menu()
                if sub and all((a in acciones_ocultar or not a.isVisible()) for a in sub.actions()):
                    act_menu.setVisible(False)

        # =========================
        # VARIABLES
        # =========================
        self.current_path = None
        self.current_fontSize = 11
        self.is_dark_mode = True
        self.ultimo_archivo_tm = None
        self.ultimo_archivo_ci = None
        self.codigo_fuente_compilado = None
        self._ultimo_texto_analizado = None

        self.ignored_extensions = [
            '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.exe', '.dll',
            '.zip', '.rar', '.7z', '.tar', '.mp3', '.mp4'
        ]

        # =========================
        # EDITOR INITIAL SETUP
        # =========================
        fuente_editor = QFont("Consolas", self.current_fontSize)
        self.textEdit.document().setDefaultFont(fuente_editor)
        self.textEdit.setFont(fuente_editor)
        self.textEdit.setFrameShape(QFrame.NoFrame)
        self.highlighter = LexicalHighlighter(self.textEdit.document())
        self.textEdit.updateLineNumberAreaWidth(0)
        self.setWindowTitle("MaoIDE - Untitled")
        self.setWindowIcon(QIcon("red.svg"))

        self.textEdit.cursorPositionChanged.connect(self.update_cursor_position)
        self.textEdit.textChanged.connect(self._al_editar_codigo)
        self.update_cursor_position()

        # =========================
        # FILE ACTIONS
        # =========================
        self.actionNew.triggered.connect(self.newFile)
        self.actionOpen.triggered.connect(self.openFile)
        self.actionOpen_Folder.triggered.connect(self.openFolder)
        self.actionSave.triggered.connect(self.saveFile)
        self.actionSave_As.triggered.connect(self.saveFileAs)
        self.actionClose.triggered.connect(self.closeFile)
        self.actionExit.triggered.connect(self.close)

        # =========================
        # EDIT ACTIONS
        # =========================
        self.actionUndo.triggered.connect(self.textEdit.undo)
        self.actionRedo.triggered.connect(self.textEdit.redo)
        self.actionCut.triggered.connect(self.textEdit.cut)
        self.actionCopy.triggered.connect(self.textEdit.copy)
        self.actionPaste.triggered.connect(self.textEdit.paste)

        # =========================
        # VIEW ACTIONS
        # =========================
        self.actionDark_Theme.triggered.connect(self.setDarkTheme)
        self.actionTerminal.triggered.connect(self.showTerminal)

        # =========================
        # COMPILAR ACTIONS
        # =========================
        self.actionL_xico.triggered.connect(self.ejecutarAnalisisLexico)
        self.actionSint_ctico.triggered.connect(self.ejecutarAnalisisSintactico)
        self.actionSem_ntico.triggered.connect(self.ejecutarAnalisisSemantico)
        self.actionGenerar_c_digo_intermedio.triggered.connect(self.generarCodigoIntermedioAction)
        self.actionEjecutar.triggered.connect(self.ejecutarEnTM)

        # ==========================================
        # TERMINAL UNIFICADA
        # ==========================================
        self.terminalPanel = QDockWidget("Terminal", self)
        self.terminalPanel.setAllowedAreas(Qt.BottomDockWidgetArea)

        self.terminalOutput = QTextEdit()
        self.terminalOutput.setReadOnly(True)
        self.terminalOutput.setFrameShape(QFrame.NoFrame)

        self.terminalPanel.setWidget(self.terminalOutput)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.terminalPanel)
        self.resizeDocks([self.terminalPanel], [260], Qt.Vertical)
        self.terminalPanel.hide()

        # ==========================================
        # PANELES LATERALES UNIFICADOS
        # ==========================================
        self.opened_files_content = {}
        self.stackedPanels = QStackedWidget()
        self._tree_branch_style = TreeBranchStyle()
        fuente_paneles = QFont("Consolas", self.current_fontSize)

        estilo_arbol_unificado = """
            QTreeWidget {
                background-color: #252526;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 14px;
                border: none;
                padding: 4px 0px;
                outline: none;
            }
            QTreeWidget::item {
                padding: 3px 6px;
                border-radius: 3px;
            }
            QTreeWidget::item:hover {
                background-color: #2a2d2e;
            }
            QTreeWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
        """

        # 0. Explorador de archivos
        self.panelArchivos = QTreeWidget()
        self.panelArchivos.setStyle(self._tree_branch_style)
        self.panelArchivos.setHeaderHidden(True)
        self.panelArchivos.setFrameShape(QFrame.NoFrame)
        self.panelArchivos.setStyleSheet(estilo_arbol_unificado)
        self.panelArchivos.itemClicked.connect(self.switchToFile)
        self.panelArchivos.setContextMenuPolicy(Qt.CustomContextMenu)
        self.panelArchivos.customContextMenuRequested.connect(self.showFileContextMenu)
        self.tree_groups = {}

        # 1. Léxico
        self.panelLexico = QTextEdit()
        self.panelLexico.setReadOnly(True)
        self.panelLexico.setFrameShape(QFrame.NoFrame)
        self.panelLexico.setFont(fuente_paneles)
        self.panelLexico.setPlainText("")

        # 2. Sintáctico
        self.panelSintactico = QTreeWidget()
        self.panelSintactico.setStyle(self._tree_branch_style)
        self.panelSintactico.setHeaderHidden(True)
        self.panelSintactico.setFrameShape(QFrame.NoFrame)
        self.panelSintactico.setStyleSheet(estilo_arbol_unificado)
        self.panelSintactico.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.panelSintactico.header().setStretchLastSection(False)

        # 3. Semántico
        self.panelSemantico = QTreeWidget()
        self.panelSemantico.setStyle(self._tree_branch_style)
        self.panelSemantico.setHeaderHidden(True)
        self.panelSemantico.setFrameShape(QFrame.NoFrame)
        self.panelSemantico.setStyleSheet(estilo_arbol_unificado)
        self.panelSemantico.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.panelSemantico.header().setStretchLastSection(False)

        # 4. Tabla de Símbolos
        self.panelTabla = QTableWidget()
        self.panelTabla.setColumnCount(4)
        self.panelTabla.setHorizontalHeaderLabels(["Lexema", "Tipo", "Offset", "Líneas"])
        self.panelTabla.verticalHeader().setVisible(False)
        self.panelTabla.verticalHeader().setDefaultSectionSize(30)
        self.panelTabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.panelTabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.panelTabla.setAlternatingRowColors(True)
        self.panelTabla.setWordWrap(False)
        self.panelTabla.setFrameShape(QFrame.NoFrame)
        header = self.panelTabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setMinimumSectionSize(65)
        self.panelTabla.setColumnWidth(0, 100)
        self.panelTabla.setColumnWidth(1, 85)
        self.panelTabla.setColumnWidth(2, 80)
        self.panelTabla.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                alternate-background-color: #2a2a2d;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 14px;
                border: none;
                gridline-color: #3c3c3c;
                outline: none;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #9cdcfe;
                font-family: Consolas, monospace;
                font-size: 14px;
                font-weight: bold;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #3c3c3c;
                border-bottom: 1px solid #3c3c3c;
            }
        """)

        # 5. Panel de Código Intermedio (.tm y .ci)
        self.panelCodigo = QTabWidget()
        self.panelCodigo.setDocumentMode(False)
        self.panelCodigo.setElideMode(Qt.ElideNone)
        self.panelCodigo.setUsesScrollButtons(True)

        self.panelCodigoTM = QTextEdit()
        self.panelCodigoTM.setReadOnly(True)
        self.panelCodigoTM.setLineWrapMode(QTextEdit.NoWrap)
        self.panelCodigoTM.setFrameShape(QFrame.NoFrame)
        self.panelCodigoTM.setFont(fuente_paneles)

        self.panelCodigoCI = QTextEdit()
        self.panelCodigoCI.setReadOnly(True)
        self.panelCodigoCI.setLineWrapMode(QTextEdit.NoWrap)
        self.panelCodigoCI.setFrameShape(QFrame.NoFrame)
        self.panelCodigoCI.setFont(fuente_paneles)

        self.panelCodigo.addTab(self.panelCodigoTM, "Código Objeto TM (.tm)")
        self.panelCodigo.addTab(self.panelCodigoCI, "Código intermedio de tres direcciones (.ci)")

        self.stackedPanels.addWidget(self.panelArchivos)
        self.stackedPanels.addWidget(self.panelLexico)
        self.stackedPanels.addWidget(self.panelSintactico)
        self.stackedPanels.addWidget(self.panelSemantico)
        self.stackedPanels.addWidget(self.panelTabla)
        self.stackedPanels.addWidget(self.panelCodigo)

        self.sideBarDock = QDockWidget("EXPLORER", self)
        self.sideBarDock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.sideBarDock.setWidget(self.stackedPanels)
        self.sideBarDock.visibilityChanged.connect(self._sincronizar_activity_bar)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sideBarDock)
        self.resizeDocks([self.sideBarDock], [480], Qt.Horizontal)

        # Barra de actividades vertical con íconos e indicador activo
        self.activityBar = QToolBar("Barra de Actividades")
        self.activityBar.setMovable(False)
        self.activityBar.setFloatable(False)
        self.activityBar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.activityBar.setIconSize(QSize(20, 20))
        self.addToolBar(Qt.LeftToolBarArea, self.activityBar)

        self.actArchivos = QAction("Explorer", self)
        self.actLexico = QAction("Léxico", self)
        self.actSintactico = QAction("Sintáctico", self)
        self.actSemantico = QAction("Semántico", self)
        self.actTabla = QAction("Tabla Símb.", self)
        self.actCodigo = QAction("Código Int.", self)

        self.activity_actions = [
            self.actArchivos,
            self.actLexico,
            self.actSintactico,
            self.actSemantico,
            self.actTabla,
            self.actCodigo,
        ]

        for act in self.activity_actions:
            act.setCheckable(True)
            self.activityBar.addAction(act)

        self.actArchivos.triggered.connect(lambda: self.switchSidePanel(0, "EXPLORER"))
        self.actLexico.triggered.connect(lambda: self.switchSidePanel(1, "ANÁLISIS LÉXICO"))
        self.actSintactico.triggered.connect(lambda: self.switchSidePanel(2, "ANÁLISIS SINTÁCTICO"))
        self.actSemantico.triggered.connect(lambda: self.switchSidePanel(3, "ANÁLISIS SEMÁNTICO"))
        self.actTabla.triggered.connect(lambda: self.switchSidePanel(4, "TABLA DE SÍMBOLOS"))
        self.actCodigo.triggered.connect(lambda: self.switchSidePanel(5, "CÓDIGO INTERMEDIO"))

        self.setup_icons()
        self.setDarkTheme()
        self._sincronizar_activity_bar()

    def _sincronizar_activity_bar(self, *_):
        if not hasattr(self, "activity_actions"):
            return
        visible = self.sideBarDock.isVisible()
        indice_actual = self.stackedPanels.currentIndex()
        for i, act in enumerate(self.activity_actions):
            act.setChecked(visible and i == indice_actual)

    def _activar_panel(self, index, title):
        self.stackedPanels.setCurrentIndex(index)
        self.sideBarDock.setWindowTitle(title)
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()
        self._sincronizar_activity_bar()

    # =========================================================
    # FASES DE COMPILACIÓN (EN CASCADA)
    # =========================================================
    def _limpiar_fases_desde(self, fase):
        """Limpia los paneles de las fases posteriores para evitar datos desactualizados."""
        if fase <= 2:  # Desde Sintáctico en adelante
            self.panelSintactico.clear()
        if fase <= 3:  # Desde Semántico y Tabla de Símbolos en adelante
            self.panelSemantico.clear()
            self.panelTabla.setRowCount(0)
        if fase <= 5:  # Desde Código Intermedio en adelante
            self.panelCodigoTM.clear()
            self.panelCodigoCI.clear()
            self.ultimo_archivo_tm = None
            self.ultimo_archivo_ci = None
            self.codigo_fuente_compilado = None

    def _al_editar_codigo(self):
        if (
            self._ultimo_texto_analizado is not None
            and self.textEdit.toPlainText() != self._ultimo_texto_analizado
        ):
            self.limpiarPanelesAnalisis()

    def _invalidar_codigo_compilado(self):
        if (
            self.codigo_fuente_compilado is not None
            and self.textEdit.toPlainText() != self.codigo_fuente_compilado
        ):
            self._limpiar_fases_desde(5)

    def ejecutarAnalisisLexico(self, checked=False, *, activar_panel=True):
        self._limpiar_fases_desde(2)
        if activar_panel:
            self._activar_panel(1, "ANÁLISIS LÉXICO")

        texto = self.textEdit.toPlainText()
        self._ultimo_texto_analizado = texto
        analizador = AnalizadorLexico()
        tokens, errores = analizador.analizar(texto)

        c_res = "#c586c0"
        c_num = "#b5cea8"
        c_id = "#9cdcfe"
        c_rel = "#4ec9b0"
        c_cad = "#ce9178"
        c_sim = "#ffd700"
        c_def = "#dcdcaa"

        c_texto = "#ffffff"
        c_sub = "gray"
        c_err = "#f44747"

        html_tokens = ""
        for t in tokens:
            if t.tipo == "COMENTARIO":
                continue

            if t.tipo == "RESERVADA":
                color = c_res
            elif t.tipo in ["NUM_ENTERO", "NUM_REAL"]:
                color = c_num
            elif t.tipo == "ID":
                color = c_id
            elif t.tipo in ["RELACIONAL", "LOGICO"]:
                color = c_rel
            elif t.tipo in ["CADENA", "CARACTER"]:
                color = c_cad
            elif t.tipo == "SIMBOLO":
                color = c_sim
            else:
                color = c_def

            lexema_mostrar = t.lexema
            if t.tipo in ["RELACIONAL", "LOGICO", "ARITMETICO", "ASIGNACION"]:
                lexema_mostrar = lexema_mostrar.replace(" ", "").replace("\n", "").replace("\t", "")

            html_tokens += f"""
                <div style='margin-bottom: 6px; font-family: Consolas, monospace; font-size: 14px;'>
                    <span style='color: {color}; font-weight: bold;'>[{t.tipo}]</span><br>
                    <span style='color: {c_texto};'>Lexema: <b>'{lexema_mostrar}'</b></span><br>
                    <span style='color: {c_sub}; font-size: 12px;'>Ubicación: Línea {t.linea}, Columna {t.columna}</span>
                    <hr style='border: 0.5px solid #4a4a4a; margin-top: 6px;'>
                </div>
            """
        self.panelLexico.setHtml(html_tokens)

        self.terminalPanel.show()
        if errores:
            html_errores = f"<span style='color: {c_err}; font-weight: bold;'>Errores léxicos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores:
                html_errores += f"<li style='color: {c_err}; margin-bottom: 4px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
            return None, errores

        exito_msg = """
            <span style='color: #89d185; font-weight: bold;'>Análisis léxico finalizado con éxito.</span><br>
            <span style='color: #d4d4d4;'>0 errores léxicos encontrados en el código.</span>
        """
        self.terminalOutput.setHtml(exito_msg)
        return tokens, []

    def ejecutarAnalisisSintactico(self, checked=False, *, activar_panel=True):
        tokens, errores_lex = self.ejecutarAnalisisLexico(activar_panel=False)
        self._limpiar_fases_desde(3)

        if activar_panel:
            self._activar_panel(2, "ANÁLISIS SINTÁCTICO")

        if errores_lex:
            self.terminalPanel.show()
            html_errores = "<span style='color: #f44747; font-weight: bold;'>Errores léxicos impidieron el análisis sintáctico:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_lex:
                html_errores += f"<li style='color: #f44747; margin-bottom: 4px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
            return None, errores_lex

        if not tokens:
            self.terminalPanel.show()
            self.terminalOutput.setHtml("<span style='color: #f44747;'>No hay tokens para analizar.</span>")
            return None, ["No hay tokens para analizar."]

        tokens_limpios = [t for t in tokens if t.tipo != "COMENTARIO"]
        analizador_sint = AnalizadorSintactico(tokens_limpios)
        ast_raiz, errores_sint = analizador_sint.analizar()

        self.dibujarAST(ast_raiz, self.panelSintactico)
        self.panelSintactico.expandAll()

        self.terminalPanel.show()
        c_err = "#f44747"

        if errores_sint:
            html_errores = f"<span style='color: {c_err}; font-weight: bold;'>Errores sintácticos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_sint:
                html_errores += f"<li style='color: {c_err}; margin-bottom: 4px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
            return None, errores_sint

        exito_msg = """
            <span style='color: #89d185; font-weight: bold;'>Análisis sintáctico finalizado con éxito.</span><br>
            <span style='color: #d4d4d4;'>0 errores sintácticos encontrados en el código.</span>
        """
        self.terminalOutput.setHtml(exito_msg)
        self.generar_txt_ast(ast_raiz)
        return ast_raiz, []

    def dibujarAST(self, nodo_ast, parent_widget):
        if not nodo_ast:
            return
        texto_item = nodo_ast.etiqueta
        if nodo_ast.lexema:
            texto_item += f" : '{nodo_ast.lexema}'"
        item = QTreeWidgetItem(parent_widget, [texto_item])
        if len(nodo_ast.hijos) == 0:
            item.setForeground(0, QColor("#ce9178"))
        else:
            item.setForeground(0, QColor("#9cdcfe"))
        for hijo in nodo_ast.hijos:
            self.dibujarAST(hijo, item)

    def ejecutarAnalisisSemantico(self, checked=False, *, activar_panel=True):
        texto = self.textEdit.toPlainText()
        if not texto.strip():
            self._limpiar_fases_desde(2)
            self.panelLexico.clear()
            if activar_panel:
                self._activar_panel(3, "ANÁLISIS SEMÁNTICO")
            self.terminalPanel.show()
            self.terminalOutput.setHtml("<span style='color: #f44747;'>No hay código para analizar.</span>")
            return None, None

        ast_original, errores_previos = self.ejecutarAnalisisSintactico(activar_panel=False)
        self._limpiar_fases_desde(5)

        if activar_panel:
            self._activar_panel(3, "ANÁLISIS SEMÁNTICO")

        if errores_previos or not ast_original:
            return None, None

        analizador_sem = AnalizadorSemantico()
        ast_anotado, tabla_simbolos, errores_sem = analizador_sem.analizar(ast_original)

        self.dibujarASTAnotado(ast_anotado, self.panelSemantico)
        self.panelSemantico.expandAll()

        simbolos = tabla_simbolos.obtener_simbolos()
        self.panelTabla.setRowCount(len(simbolos))
        for row, s in enumerate(simbolos):
            lineas_str = ", ".join(map(str, sorted(s.lineas)))
            item_nom = QTableWidgetItem(s.nombre)
            item_tipo = QTableWidgetItem(s.tipo)
            item_off = QTableWidgetItem(str(s.desplazamiento))
            item_lin = QTableWidgetItem(lineas_str)

            item_nom.setForeground(QColor("#9cdcfe"))
            item_tipo.setForeground(QColor("#4ec9b0"))
            item_off.setForeground(QColor("#b5cea8"))
            item_lin.setForeground(QColor("#d4d4d4"))

            item_nom.setTextAlignment(Qt.AlignCenter)
            item_tipo.setTextAlignment(Qt.AlignCenter)
            item_off.setTextAlignment(Qt.AlignCenter)
            item_lin.setTextAlignment(Qt.AlignCenter)

            self.panelTabla.setItem(row, 0, item_nom)
            self.panelTabla.setItem(row, 1, item_tipo)
            self.panelTabla.setItem(row, 2, item_off)
            self.panelTabla.setItem(row, 3, item_lin)

        self.terminalPanel.show()
        c_err = "#f44747"

        if errores_sem:
            html = f"<span style='color: {c_err}; font-weight: bold;'>Errores semánticos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_sem:
                html += f"<li style='color: {c_err}; margin-bottom: 4px;'>{e}</li>"
            html += "</ul>"
            self.terminalOutput.setHtml(html)
            return None, None

        exito_msg = """
            <span style='color: #89d185; font-weight: bold;'>Análisis semántico finalizado con éxito.</span><br>
            <span style='color: #d4d4d4;'>0 errores semánticos encontrados en el código.</span>
        """
        self.terminalOutput.setHtml(exito_msg)
        return ast_anotado, tabla_simbolos

    def dibujarASTAnotado(self, nodo_ast, parent_widget):
        if not nodo_ast:
            return
        texto_item = nodo_ast.etiqueta
        if nodo_ast.lexema:
            texto_item += f" : '{nodo_ast.lexema}'"
        anotaciones = []
        if getattr(nodo_ast, 'dtype', None):
            anotaciones.append(f"tipo: {nodo_ast.dtype}")
        if getattr(nodo_ast, 'val', None) is not None:
            anotaciones.append(f"val: {nodo_ast.val}")
        if getattr(nodo_ast, 'desplazamiento', None) is not None:
            anotaciones.append(f"offset: {nodo_ast.desplazamiento}")
        if getattr(nodo_ast, 'coercion', None):
            anotaciones.append(f"coerción: {nodo_ast.coercion}")
        if anotaciones:
            texto_item += f"  [{', '.join(anotaciones)}]"

        item = QTreeWidgetItem(parent_widget, [texto_item])
        if getattr(nodo_ast, 'dtype', None) == 'ERROR':
            item.setForeground(0, QColor("#f44747"))
        elif len(nodo_ast.hijos) == 0:
            item.setForeground(0, QColor("#4ec9b0"))
        else:
            item.setForeground(0, QColor("#9cdcfe"))

        for hijo in nodo_ast.hijos:
            self.dibujarASTAnotado(hijo, item)

    # =========================================================
    # FASE 4: GENERACIÓN DE CÓDIGO (.tm Y .ci) Y EJECUCIÓN TM
    # =========================================================
    def generarCodigoIntermedioAction(self):
        self._limpiar_fases_desde(5)

        ast_anotado, tabla_simbolos = self.ejecutarAnalisisSemantico(activar_panel=False)
        if not ast_anotado or not tabla_simbolos:
            return False

        self._activar_panel(5, "CÓDIGO INTERMEDIO")
        if self.sideBarDock.width() < 480:
            self.resizeDocks([self.sideBarDock], [500], Qt.Horizontal)

        if self.current_path:
            base_sin_ext, _ = os.path.splitext(self.current_path)
            ruta_tm = base_sin_ext + ".tm"
            ruta_ci = base_sin_ext + ".ci"
        else:
            carpeta_salida = os.path.join(BASE_DIR, "salida_tm")
            os.makedirs(carpeta_salida, exist_ok=True)
            ruta_tm = os.path.join(carpeta_salida, "programa.tm")
            ruta_ci = os.path.join(carpeta_salida, "programa.ci")

        nombre_tm_corto = os.path.basename(ruta_tm)

        gen_ci = GeneradorCodigoIntermedio()
        codigo_ci = gen_ci.generar(ast_anotado)

        gen_tm = GeneradorTM(trace_code=True)
        codigo_tm, advertencias = gen_tm.generar(ast_anotado, tabla_simbolos, nombre_tm_corto)

        try:
            with open(ruta_ci, "w", encoding="utf-8") as f_ci:
                f_ci.write(codigo_ci)
            with open(ruta_tm, "w", encoding="ascii", errors="replace") as f_tm:
                f_tm.write(codigo_tm)
        except Exception as e:
            self.terminalPanel.show()
            self.terminalOutput.setHtml(
                f"<span style='color: #f44747;'>Error al escribir archivos de código generado: {e}</span>"
            )
            return False

        self.panelCodigoTM.setPlainText(codigo_tm)
        self.panelCodigoCI.setPlainText(codigo_ci)
        self.panelCodigo.setCurrentIndex(0)

        if self.current_path:
            self.addFileToTree(ruta_tm)
            self.addFileToTree(ruta_ci)

        self.ultimo_archivo_tm = ruta_tm
        self.ultimo_archivo_ci = ruta_ci
        self.codigo_fuente_compilado = self.textEdit.toPlainText()

        self.terminalPanel.show()
        msg_html = f"""
            <span style='color: #89d185; font-weight: bold;'>Generación de código finalizada con éxito.</span><br>
            <span style='color: #9cdcfe;'>• Archivo TM generado: {ruta_tm}</span><br>
            <span style='color: #4ec9b0;'>• Archivo CI (tres direcciones) generado: {ruta_ci}</span>
        """
        if advertencias:
            msg_html += "<ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for adv in advertencias:
                msg_html += f"<li style='color: #dcdcaa;'>{adv}</li>"
            msg_html += "</ul>"
        self.terminalOutput.setHtml(msg_html)
        return True

    def _obtener_ejecutable_tm(self):
        es_windows = (os.name == "nt")
        nombre_bin = "tm.exe" if es_windows else "tm"
        ruta_bin = os.path.join(BASE_DIR, nombre_bin)
        ruta_fuente_tm = os.path.join(BASE_DIR, "tm.c")

        if os.path.isfile(ruta_bin):
            return ruta_bin, None

        if not os.path.isfile(ruta_fuente_tm):
            return None, (
                f"No se encontró '{nombre_bin}' ni 'tm.c' en '{BASE_DIR}'. "
                "Copia 'tm.c' de la carpeta Tiny_Intermedio_TM a la carpeta del proyecto."
            )

        try:
            proc = subprocess.run(
                ["gcc", "-std=c11", "-O2", ruta_fuente_tm, "-o", ruta_bin],
                capture_output=True,
                text=True,
                cwd=BASE_DIR
            )
            if proc.returncode == 0 and os.path.isfile(ruta_bin):
                return ruta_bin, None
            return None, f"Error al compilar tm.c con GCC:\n{proc.stderr}"
        except FileNotFoundError:
            return None, (
                "No se encontró el compilador 'gcc' en el PATH para compilar tm.c. "
                "Compila tm.c manualmente (gcc tm.c -o tm.exe) o agrégalo al PATH."
            )

    def ejecutarEnTM(self):
        if not self.generarCodigoIntermedioAction():
            return

        ruta_tm = self.ultimo_archivo_tm
        if not ruta_tm or not os.path.isfile(ruta_tm):
            self.terminalPanel.show()
            self.terminalOutput.append(
                "<span style='color: #f44747;'>No se encontró un archivo .tm válido para ejecutar.</span>"
            )
            return

        tm_bin, error_tm = self._obtener_ejecutable_tm()
        if error_tm:
            self.terminalPanel.show()
            self.terminalOutput.append(f"<span style='color: #f44747;'>{error_tm}</span>")
            return

        try:
            carpeta_trabajo = os.path.dirname(ruta_tm)
            if os.name == "nt":
                subprocess.Popen(
                    [tm_bin, ruta_tm],
                    cwd=carpeta_trabajo,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen([tm_bin, ruta_tm], cwd=carpeta_trabajo)

            self.terminalPanel.show()
            self.terminalOutput.append("")
            self.terminalOutput.append(
                f"<span style='color: #89d185; font-weight: bold;'>Simulador TM iniciado con: {os.path.basename(ruta_tm)}</span>"
            )
            self.terminalOutput.append(
                "<span style='color: #dcdcaa;'>Comandos dentro de la consola TM: <b>g</b> (ejecutar programa), <b>v</b> (ver .ci), <b>r</b> (registros), <b>d 0 10</b> (memoria), <b>q</b> (salir).</span>"
            )
        except Exception as e:
            self.terminalPanel.show()
            self.terminalOutput.append(
                f"<span style='color: #f44747;'>Error al abrir el simulador TM: {e}</span>"
            )

    # =========================
    # STATUS BAR FUNCTION
    # =========================
    def update_cursor_position(self):
        cursor = self.textEdit.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.statusBar().showMessage(f"Ln {line}, Col {col}")

    # =========================
    # FILE FUNCTIONS
    # =========================
    def newFile(self):
        if self.current_path is None and self.textEdit.toPlainText().strip() != "":
            respuesta = QMessageBox.question(
                self,
                "Save File",
                "Do you want to save the changes to your 'Untitled' file before creating a new one?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if respuesta == QMessageBox.Cancel:
                return
            elif respuesta == QMessageBox.Yes:
                self.saveFileAs()
                if self.current_path is None:
                    return
        elif self.current_path is not None:
            self.opened_files_content[self.current_path] = self.textEdit.toPlainText()

        self.textEdit.clear()
        self.setWindowTitle("MaoIDE - Untitled")
        self.current_path = None
        self.limpiarPanelesAnalisis()

    def openFile(self):
        if self.current_path is None and self.textEdit.toPlainText().strip() != "":
            respuesta = QMessageBox.question(
                self,
                "Save File",
                "Do you want to save the changes to your 'Untitled' file before opening a new one?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if respuesta == QMessageBox.Cancel:
                return
            elif respuesta == QMessageBox.Yes:
                self.saveFileAs()
                if self.current_path is None:
                    return

        fileName, _ = QFileDialog.getOpenFileName(self, 'Open File', '', 'All files (*.*)')
        if fileName:
            if self.current_path:
                self.opened_files_content[self.current_path] = self.textEdit.toPlainText()
            with open(fileName, 'r', encoding='utf-8', errors='ignore') as f:
                fileText = f.read()
            self.opened_files_content[fileName] = fileText
            self.addFileToTree(fileName)
            self.textEdit.setPlainText(fileText)
            self.current_path = fileName
            self.setWindowTitle("MaoIDE - " + fileName)
            self.limpiarPanelesAnalisis()
            self._activar_panel(0, "EXPLORER")

    def saveFile(self):
        if self.current_path is not None:
            fileText = self.textEdit.toPlainText()
            with open(self.current_path, 'w', encoding='utf-8') as f:
                f.write(fileText)
        else:
            self.saveFileAs()

    def closeFile(self):
        if self.textEdit.toPlainText() != "":
            respuesta = QMessageBox.question(
                self, "Close File", "Save changes?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes
            )
            if respuesta == QMessageBox.Cancel:
                return
            elif respuesta == QMessageBox.Yes:
                self.saveFile()

        if self.current_path:
            if self.current_path in self.opened_files_content:
                del self.opened_files_content[self.current_path]
            folder_path = os.path.dirname(self.current_path)
            if folder_path in self.tree_groups:
                root = self.tree_groups[folder_path]
                for i in range(root.childCount()):
                    if root.child(i).data(0, Qt.UserRole) == self.current_path:
                        root.removeChild(root.child(i))
                        if root.childCount() == 0:
                            self.panelArchivos.takeTopLevelItem(self.panelArchivos.indexOfTopLevelItem(root))
                            del self.tree_groups[folder_path]
                        break

        self.current_path = None
        self.textEdit.clear()
        archivos_restantes = self.get_all_file_items()
        if archivos_restantes:
            self.switchToFile(archivos_restantes[-1])
        else:
            self.setWindowTitle("MaoIDE - Untitled")
            self.limpiarPanelesAnalisis()

    def closeEvent(self, event):
        if self.textEdit.toPlainText() != "":
            respuesta = QMessageBox.question(
                self,
                "Close MaoIDE",
                "Do you want to leave? Your changes will be lost if you don't save them.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if respuesta == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def saveFileAs(self):
        pathName, _ = QFileDialog.getSaveFileName(self, 'Save File', '', 'All files (*.*)')
        if pathName:
            fileText = self.textEdit.toPlainText()
            with open(pathName, 'w', encoding='utf-8') as f:
                f.write(fileText)
            self.current_path = pathName
            self.setWindowTitle("MaoIDE - " + pathName)
            self.opened_files_content[pathName] = fileText
            self.addFileToTree(pathName)
            self._activar_panel(0, "EXPLORER")

    def openFolder(self):
        folder_path = QFileDialog.getExistingDirectory(self, 'Open Folder', '')
        if folder_path:
            archivos = os.listdir(folder_path)
            for archivo in archivos:
                ruta_completa = os.path.join(folder_path, archivo).replace('\\', '/')
                if os.path.isfile(ruta_completa):
                    _, extension = os.path.splitext(ruta_completa)
                    if extension.lower() not in self.ignored_extensions:
                        self.addFileToTree(ruta_completa)
            self._activar_panel(0, "EXPLORER")

    def undo(self):
        self.textEdit.undo()

    def redo(self):
        self.textEdit.redo()

    def cut(self):
        self.textEdit.cut()

    def copy(self):
        self.textEdit.copy()

    def paste(self):
        self.textEdit.paste()

    # =========================
    # ESTILO UNIFICADO
    # =========================
    def setDarkTheme(self):
        self.is_dark_mode = True
        self.setStyleSheet('''
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
            QPlainTextEdit {
                background-color: #252526;
                color: #d4d4d4;
                border: none;
                outline: none;
                selection-background-color: #264f78;
            }
            QTextEdit {
                background-color: #252526;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 14px;
                border: none;
                outline: none;
                selection-background-color: #264f78;
            }
            QMenuBar {
                background-color: #1e1e1e;
                color: #cccccc;
                border-bottom: 1px solid #2d2d30;
                padding: 2px 4px;
            }
            QMenuBar::item {
                padding: 4px 10px;
                border-radius: 3px;
            }
            QMenuBar::item:selected {
                background-color: #2d2d30;
                color: #ffffff;
            }
            QMenu {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3c3c3c;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 24px 5px 12px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QDockWidget {
                color: #bbbbbb;
                font-family: "Segoe UI", sans-serif;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid #2d2d30;
            }
            QDockWidget::title {
                background-color: #252526;
                padding: 7px 10px;
                border-bottom: 1px solid #3c3c3c;
                text-align: left;
            }
            QTabWidget::pane {
                border: none;
                border-top: 1px solid #3c3c3c;
                background-color: #252526;
            }
            QTabBar {
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #969696;
                font-family: "Segoe UI", sans-serif;
                font-size: 12px;
                padding: 7px 14px;
                margin-right: 2px;
                border: none;
                border-top: 2px solid transparent;
            }
            QTabBar::tab:hover {
                background-color: #2a2d2e;
                color: #e0e0e0;
            }
            QTabBar::tab:selected {
                background-color: #252526;
                color: #ffffff;
                font-weight: bold;
                border-top: 2px solid #3794ff;
            }
            QStatusBar {
                background-color: #1e1e1e;
                color: #9cdcfe;
                border-top: 1px solid #2d2d30;
                font-family: Consolas, monospace;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: #252526;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #424242;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5a5a5a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background: #252526;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #424242;
                min-width: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #5a5a5a;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        ''')

        self.activityBar.setStyleSheet("""
            QToolBar {
                background-color: #181818;
                border: none;
                border-right: 1px solid #2d2d30;
                spacing: 4px;
                padding-top: 6px;
            }
            QToolButton {
                min-width: 68px;
                max-width: 68px;
                min-height: 50px;
                padding: 6px 2px;
                font-family: "Segoe UI", sans-serif;
                font-size: 10px;
                font-weight: 600;
                color: #858585;
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
            }
            QToolButton:hover {
                color: #e0e0e0;
                background-color: #252526;
            }
            QToolButton:checked {
                color: #ffffff;
                background-color: #252526;
                border-left: 3px solid #3794ff;
            }
            QToolButton:pressed {
                background-color: #2d2d30;
            }
        """)

        self.terminalOutput.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 16px;
                padding: 6px;
                border: none;
            }
        """)

        fuente_editor = QFont("Consolas", self.current_fontSize)
        self.textEdit.document().setDefaultFont(fuente_editor)
        self.textEdit.setFont(fuente_editor)
        self.textEdit.updateLineNumberAreaWidth(0)

    def showTerminal(self):
        if self.terminalPanel.isVisible():
            self.terminalPanel.hide()
        else:
            self.terminalPanel.show()

    def switchSidePanel(self, index, title):
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()
        elif self.stackedPanels.currentIndex() == index:
            self.sideBarDock.hide()
            self._sincronizar_activity_bar()
            return

        self.stackedPanels.setCurrentIndex(index)
        self.sideBarDock.setWindowTitle(title)
        self._sincronizar_activity_bar()

        if index == 4:
            if self.sideBarDock.width() < 450:
                self.resizeDocks([self.sideBarDock], [460], Qt.Horizontal)
        elif index == 5:
            if self.sideBarDock.width() < 480:
                self.resizeDocks([self.sideBarDock], [500], Qt.Horizontal)

    def limpiarPanelesAnalisis(self):
        self.panelLexico.setPlainText("")
        self.panelSintactico.clear()
        self.panelSemantico.clear()
        self.panelTabla.setRowCount(0)
        self.panelCodigoTM.clear()
        self.panelCodigoCI.clear()
        self.ultimo_archivo_tm = None
        self.ultimo_archivo_ci = None
        self.codigo_fuente_compilado = None
        self._ultimo_texto_analizado = None
        self.terminalOutput.clear()
        self.terminalPanel.hide()

    # =========================
    # FILE EXPLORER FUNCTIONS
    # =========================
    def addFileToTree(self, file_path):
        file_path = file_path.replace('\\', '/')
        folder_path = os.path.dirname(file_path)
        folder_name = os.path.basename(folder_path)

        if folder_path not in self.tree_groups:
            root_item = QTreeWidgetItem(self.panelArchivos, [folder_name.upper()])
            root_item.setData(0, Qt.UserRole, folder_path)
            root_item.setForeground(0, QColor("#9cdcfe"))
            font = root_item.font(0)
            font.setBold(True)
            root_item.setFont(0, font)
            root_item.setExpanded(True)
            self.tree_groups[folder_path] = root_item
        else:
            root_item = self.tree_groups[folder_path]

        for i in range(root_item.childCount()):
            if root_item.child(i).data(0, Qt.UserRole) == file_path:
                return

        file_item = QTreeWidgetItem(root_item, [os.path.basename(file_path)])
        file_item.setData(0, Qt.UserRole, file_path)
        file_item.setForeground(0, QColor("#d4d4d4"))

    def get_all_file_items(self):
        items = []
        for i in range(self.panelArchivos.topLevelItemCount()):
            root = self.panelArchivos.topLevelItem(i)
            for j in range(root.childCount()):
                items.append(root.child(j))
        return items

    def switchToFile(self, item, column=0):
        clicked_path = item.data(0, Qt.UserRole)
        if not os.path.isfile(clicked_path):
            return
        if clicked_path == self.current_path:
            return

        if self.current_path is None and self.textEdit.toPlainText().strip() != "":
            respuesta = QMessageBox.question(
                self, "Save File", "Do you want to save your 'Untitled' file?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes
            )
            if respuesta == QMessageBox.Cancel:
                return
            elif respuesta == QMessageBox.Yes:
                self.saveFileAs()
                if self.current_path is None:
                    return
        elif self.current_path is not None:
            self.opened_files_content[self.current_path] = self.textEdit.toPlainText()

        if clicked_path not in self.opened_files_content:
            try:
                with open(clicked_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.opened_files_content[clicked_path] = f.read()
            except Exception:
                return

        self.textEdit.setPlainText(self.opened_files_content.get(clicked_path, ""))
        self.current_path = clicked_path
        self.setWindowTitle("MaoIDE - " + clicked_path)
        self.limpiarPanelesAnalisis()

    def showFileContextMenu(self, pos):
        item = self.panelArchivos.itemAt(pos)
        if not item:
            return
        ruta_item = item.data(0, Qt.UserRole)
        menu = QMenu()
        if os.path.isfile(ruta_item):
            close_action = menu.addAction("Close File")
            action = menu.exec_(self.panelArchivos.mapToGlobal(pos))
            if action == close_action:
                self.closeFileFromExplorer(item)
        else:
            close_action = menu.addAction("Close Folder")
            action = menu.exec_(self.panelArchivos.mapToGlobal(pos))
            if action == close_action:
                self.closeFolderFromExplorer(item)

    def closeFolderFromExplorer(self, folder_item):
        nombre_carpeta = folder_item.text(0)
        respuesta = QMessageBox.question(
            self,
            "Close Folder",
            f"Do you want to close the folder '{nombre_carpeta}' and all its files?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if respuesta == QMessageBox.No:
            return
        for i in range(folder_item.childCount() - 1, -1, -1):
            child = folder_item.child(i)
            if self.closeFileFromExplorer(child) is False:
                return

    def closeFileFromExplorer(self, item):
        path_to_remove = item.data(0, Qt.UserRole)
        if not os.path.isfile(path_to_remove):
            return False

        necesita_comprobar = False
        if path_to_remove == self.current_path:
            fileText = self.textEdit.toPlainText()
            necesita_comprobar = True
        elif path_to_remove in self.opened_files_content:
            fileText = self.opened_files_content[path_to_remove]
            necesita_comprobar = True

        if necesita_comprobar:
            try:
                with open(path_to_remove, 'r', encoding='utf-8', errors='ignore') as f:
                    diskText = f.read()
            except Exception:
                diskText = ""

            if fileText != diskText:
                nombre_archivo = os.path.basename(path_to_remove)
                respuesta = QMessageBox.question(
                    self, "Close File", f"Save changes to '{nombre_archivo}'?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes
                )
                if respuesta == QMessageBox.Cancel:
                    return False
                elif respuesta == QMessageBox.Yes:
                    with open(path_to_remove, 'w', encoding='utf-8') as f:
                        f.write(fileText)

        parent_item = item.parent()
        if parent_item:
            parent_item.removeChild(item)
            if parent_item.childCount() == 0:
                folder_path = parent_item.data(0, Qt.UserRole)
                self.panelArchivos.takeTopLevelItem(self.panelArchivos.indexOfTopLevelItem(parent_item))
                del self.tree_groups[folder_path]

        if path_to_remove in self.opened_files_content:
            del self.opened_files_content[path_to_remove]

        if path_to_remove == self.current_path:
            self.current_path = None
            self.textEdit.clear()
            archivos_restantes = self.get_all_file_items()
            if archivos_restantes:
                self.switchToFile(archivos_restantes[-1])
            else:
                self.setWindowTitle("MaoIDE - Untitled")
                self.limpiarPanelesAnalisis()

        return True

    # =========================
    # ICONOS
    # =========================
    def _crear_icono_vectorial(self, tipo):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing, True)

        def lapiz(color_hex, grosor=1.8):
            pen = QPen(QColor(color_hex), grosor, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)

        if tipo == "explorer":
            lapiz("#9cdcfe", 1.7)
            p.drawPolyline(QPolygonF([
                QPointF(8, 6), QPointF(8, 3), QPointF(18, 3),
                QPointF(18, 16), QPointF(15, 16)
            ]))
            p.drawRect(5, 7, 10, 14)

        elif tipo == "new":
            lapiz("#cccccc")
            p.drawPolygon(QPolygonF([
                QPointF(6, 3), QPointF(14, 3), QPointF(18, 7),
                QPointF(18, 21), QPointF(6, 21)
            ]))
            p.drawPolyline(QPolygonF([QPointF(14, 3), QPointF(14, 7), QPointF(18, 7)]))

        elif tipo == "open":
            lapiz("#dcb67a")
            p.drawPolygon(QPolygonF([
                QPointF(3, 6), QPointF(9, 6), QPointF(11, 8),
                QPointF(21, 8), QPointF(21, 19), QPointF(3, 19)
            ]))

        elif tipo == "open_folder":
            lapiz("#dcb67a")
            p.drawPolyline(QPolygonF([
                QPointF(13, 19), QPointF(3, 19), QPointF(3, 6),
                QPointF(9, 6), QPointF(11, 8), QPointF(21, 8), QPointF(21, 13)
            ]))
            lapiz("#75beff", 2.0)
            p.drawLine(17, 14, 17, 20)
            p.drawLine(14, 17, 20, 17)

        elif tipo == "save":
            lapiz("#75beff")
            p.drawRoundedRect(4, 4, 16, 16, 2, 2)
            p.drawRect(7, 4, 8, 5)
            p.drawRect(7, 13, 10, 7)

        elif tipo == "save_as":
            lapiz("#75beff")
            p.drawPolyline(QPolygonF([
                QPointF(12, 20), QPointF(4, 20), QPointF(4, 4),
                QPointF(18, 4), QPointF(20, 6), QPointF(20, 11)
            ]))
            p.drawRect(7, 4, 8, 5)
            lapiz("#dcdcaa", 1.8)
            p.drawLine(14, 19, 20, 13)
            p.drawLine(13, 20, 15, 20)

        elif tipo == "close":
            lapiz("#f48771", 1.8)
            p.drawRoundedRect(4, 4, 16, 16, 3, 3)
            p.drawLine(9, 9, 15, 15)
            p.drawLine(15, 9, 9, 15)

        elif tipo == "exit":
            lapiz("#cccccc", 1.8)
            p.drawPolyline(QPolygonF([
                QPointF(11, 4), QPointF(5, 4), QPointF(5, 20), QPointF(11, 20)
            ]))
            lapiz("#f44747", 2.0)
            p.drawLine(10, 12, 20, 12)
            p.drawPolyline(QPolygonF([QPointF(16, 8), QPointF(20, 12), QPointF(16, 16)]))

        elif tipo == "undo":
            lapiz("#75beff", 2.0)
            p.drawPolyline(QPolygonF([QPointF(9, 5), QPointF(5, 9), QPointF(9, 13)]))
            p.drawArc(6, 9, 13, 10, 0, 180 * 16)

        elif tipo == "redo":
            lapiz("#75beff", 2.0)
            p.drawPolyline(QPolygonF([QPointF(15, 5), QPointF(19, 9), QPointF(15, 13)]))
            p.drawArc(5, 9, 13, 10, 0, 180 * 16)

        elif tipo == "cut":
            lapiz("#cccccc", 1.8)
            p.drawEllipse(5, 15, 5, 5)
            p.drawEllipse(14, 15, 5, 5)
            p.drawLine(9, 16, 17, 5)
            p.drawLine(15, 16, 7, 5)

        elif tipo == "copy":
            lapiz("#cccccc", 1.7)
            p.drawPolyline(QPolygonF([
                QPointF(9, 6), QPointF(9, 3), QPointF(19, 3),
                QPointF(19, 16), QPointF(16, 16)
            ]))
            p.drawRect(5, 7, 11, 14)

        elif tipo == "paste":
            lapiz("#cccccc", 1.7)
            p.drawRoundedRect(5, 5, 14, 16, 2, 2)
            p.drawRect(9, 3, 6, 3)
            p.drawLine(8, 11, 16, 11)
            p.drawLine(8, 15, 14, 15)

        elif tipo == "terminal":
            lapiz("#cccccc", 1.8)
            p.drawRoundedRect(3, 4, 18, 16, 2, 2)
            lapiz("#4ec9b0", 1.8)
            p.drawPolyline(QPolygonF([QPointF(7, 9), QPointF(10, 12), QPointF(7, 15)]))
            p.drawLine(12, 15, 17, 15)

        elif tipo == "lexico":
            lapiz("#c586c0", 2.0)
            p.drawPolyline(QPolygonF([QPointF(8, 4), QPointF(5, 4), QPointF(5, 20), QPointF(8, 20)]))
            p.drawPolyline(QPolygonF([QPointF(16, 4), QPointF(19, 4), QPointF(19, 20), QPointF(16, 20)]))
            p.setBrush(QColor("#c586c0"))
            p.drawEllipse(10, 10, 4, 4)

        elif tipo == "sintactico":
            lapiz("#4ec9b0", 1.8)
            p.drawLine(12, 7, 6, 16)
            p.drawLine(12, 7, 18, 16)
            p.setBrush(QColor("#4ec9b0"))
            p.drawEllipse(9, 3, 6, 6)
            p.drawEllipse(3, 15, 6, 6)
            p.drawEllipse(15, 15, 6, 6)

        elif tipo == "semantico":
            lapiz("#75beff", 1.8)
            p.drawRoundedRect(4, 4, 16, 16, 3, 3)
            lapiz("#89d185", 2.2)
            p.drawPolyline(QPolygonF([QPointF(8, 12), QPointF(11, 15), QPointF(17, 9)]))

        elif tipo == "tabla":
            lapiz("#ce9178", 1.7)
            p.drawRoundedRect(4, 4, 16, 16, 2, 2)
            p.drawLine(4, 9, 20, 9)
            p.drawLine(4, 14, 20, 14)
            p.drawLine(10, 9, 10, 20)

        elif tipo == "codigo_int":
            p.setPen(QColor("#dcdcaa"))
            p.setFont(QFont("Consolas", 10, QFont.Bold))
            p.drawText(QRect(0, 0, 24, 24), Qt.AlignCenter, "</>")

        elif tipo == "ejecutar":
            p.setPen(QPen(QColor("#73c991"), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(QColor("#73c991"))
            p.drawPolygon(QPolygonF([
                QPointF(7, 5), QPointF(19, 12), QPointF(7, 19)
            ]))

        p.end()
        return QIcon(pixmap)

    def setup_icons(self):
        self.actionNew.setIcon(self._crear_icono_vectorial("new"))
        self.actionOpen.setIcon(self._crear_icono_vectorial("open"))
        self.actionOpen_Folder.setIcon(self._crear_icono_vectorial("open_folder"))
        self.actionSave.setIcon(self._crear_icono_vectorial("save"))
        self.actionSave_As.setIcon(self._crear_icono_vectorial("save_as"))
        self.actionClose.setIcon(self._crear_icono_vectorial("close"))
        self.actionExit.setIcon(self._crear_icono_vectorial("exit"))

        self.actionUndo.setIcon(self._crear_icono_vectorial("undo"))
        self.actionRedo.setIcon(self._crear_icono_vectorial("redo"))
        self.actionCut.setIcon(self._crear_icono_vectorial("cut"))
        self.actionCopy.setIcon(self._crear_icono_vectorial("copy"))
        self.actionPaste.setIcon(self._crear_icono_vectorial("paste"))

        self.actionTerminal.setIcon(self._crear_icono_vectorial("terminal"))

        self.actionL_xico.setIcon(self._crear_icono_vectorial("lexico"))
        self.actionSint_ctico.setIcon(self._crear_icono_vectorial("sintactico"))
        self.actionSem_ntico.setIcon(self._crear_icono_vectorial("semantico"))
        self.actionGenerar_c_digo_intermedio.setIcon(self._crear_icono_vectorial("codigo_int"))
        self.actionEjecutar.setIcon(self._crear_icono_vectorial("ejecutar"))

        # Íconos de la barra lateral (Activity Bar)
        self.actArchivos.setIcon(self._crear_icono_vectorial("explorer"))
        self.actLexico.setIcon(self._crear_icono_vectorial("lexico"))
        self.actSintactico.setIcon(self._crear_icono_vectorial("sintactico"))
        self.actSemantico.setIcon(self._crear_icono_vectorial("semantico"))
        self.actTabla.setIcon(self._crear_icono_vectorial("tabla"))
        self.actCodigo.setIcon(self._crear_icono_vectorial("codigo_int"))

        quickBar = QToolBar("Quick Access", self.menuBar())
        quickBar.setMovable(False)
        quickBar.setFloatable(False)
        quickBar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        quickBar.setStyleSheet("""
            QToolBar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #2d2d30;
                spacing: 3px;
                padding: 2px 6px;
            }
            QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #2d2d30;
                border: 1px solid #3c3c3c;
            }
            QToolButton:pressed {
                background-color: #094771;
            }
        """)

        quickBar.addAction(self.actionNew)
        quickBar.addAction(self.actionOpen)
        quickBar.addAction(self.actionOpen_Folder)
        quickBar.addAction(self.actionSave)
        quickBar.addAction(self.actionSave_As)
        quickBar.addAction(self.actionClose)
        quickBar.addAction(self.actionExit)
        quickBar.addSeparator()

        quickBar.addAction(self.actionUndo)
        quickBar.addAction(self.actionRedo)
        quickBar.addSeparator()
        quickBar.addAction(self.actionCut)
        quickBar.addAction(self.actionCopy)
        quickBar.addAction(self.actionPaste)
        quickBar.addSeparator()

        quickBar.addAction(self.actionTerminal)
        quickBar.addSeparator()

        quickBar.addAction(self.actionL_xico)
        quickBar.addAction(self.actionSint_ctico)
        quickBar.addAction(self.actionSem_ntico)
        quickBar.addSeparator()
        quickBar.addAction(self.actionGenerar_c_digo_intermedio)
        quickBar.addSeparator()
        quickBar.addAction(self.actionEjecutar)

        quickBar.setIconSize(QSize(22, 22))
        self.addToolBar(Qt.TopToolBarArea, quickBar)

    def generar_txt_ast(self, nodo_raiz):
        if not nodo_raiz:
            return
        lineas_texto = []

        def recorrer(nodo, nivel):
            sangria = "    " * nivel
            texto = f"{sangria}- {nodo.etiqueta}"
            if nodo.lexema:
                texto += f" : '{nodo.lexema}'"
            lineas_texto.append(texto)
            for hijo in nodo.hijos:
                recorrer(hijo, nivel + 1)

        recorrer(nodo_raiz, 0)
        with open("arbol_sintactico_resultado.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(lineas_texto))


# =========================
# START APPLICATION
# =========================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = Main()
    ui.showMaximized()
    app.exec_()