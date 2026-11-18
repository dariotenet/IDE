from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QFileDialog, QMessageBox, QFrame, QDockWidget,
    QTextEdit, QToolBar, QStackedWidget, QTabWidget, QAction, QMenu,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QTableWidget, QTableWidgetItem,
    QProxyStyle, QStyle
)
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, QSize, QPointF
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QPolygonF
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
    """Dibuja las flechas de expansión/colapso del QTreeWidget con alto contraste."""
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorBranch:
            if option.state & QStyle.State_Children:
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing, True)
                color = QColor("#ffffff") if (option.state & QStyle.State_MouseOver) else QColor("#dcdcaa")
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

        # =========================
        # VARIABLES
        # =========================
        self.current_path = None
        self.current_fontSize = 10
        self.is_dark_mode = True
        self.ultimo_archivo_tm = None
        self.ultimo_archivo_ci = None
        self.codigo_fuente_compilado = None

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
        self.setWindowTitle("IDE - Untitled")

        self.textEdit.cursorPositionChanged.connect(self.update_cursor_position)
        self.update_cursor_position()

        self.setup_icons()

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
        self.actionIncrease_font_size.triggered.connect(self.increaseFont)
        self.actionDecrease_Font_Size.triggered.connect(self.decreaseFont)
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
        # TERMINAL
        # ==========================================
        self.terminalPanel = QDockWidget("Terminal", self)
        self.terminalPanel.setAllowedAreas(Qt.BottomDockWidgetArea)

        self.terminalOutput = QTextEdit()
        self.terminalOutput.setReadOnly(True)
        self.terminalOutput.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #000000;
                font-family: Consolas, monospace;
                font-size: 10pt;
                border: none;
            }
        """)

        self.terminalPanel.setWidget(self.terminalOutput)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.terminalPanel)
        self.resizeDocks([self.terminalPanel], [160], Qt.Vertical)
        self.terminalPanel.hide()

        # ==========================================
        # LATERAL BAR (ACTIVITY BAR)
        # ==========================================
        self.opened_files_content = {}
        self.stackedPanels = QStackedWidget()
        self._tree_branch_style = TreeBranchStyle()

        # Explorador de archivos
        self.panelArchivos = QTreeWidget()
        self.panelArchivos.setStyle(self._tree_branch_style)
        self.panelArchivos.setHeaderHidden(True)
        self.panelArchivos.setFrameShape(QFrame.NoFrame)
        self.panelArchivos.itemClicked.connect(self.switchToFile)
        self.panelArchivos.setContextMenuPolicy(Qt.CustomContextMenu)
        self.panelArchivos.customContextMenuRequested.connect(self.showFileContextMenu)
        self.tree_groups = {}

        # Léxico
        self.panelLexico = QTextEdit()
        self.panelLexico.setReadOnly(True)
        self.panelLexico.setFrameShape(QFrame.NoFrame)
        self.panelLexico.setPlainText("")

        # Sintáctico
        self.panelSintactico = QTreeWidget()
        self.panelSintactico.setStyle(self._tree_branch_style)
        self.panelSintactico.setHeaderHidden(True)
        self.panelSintactico.setFrameShape(QFrame.NoFrame)
        self.panelSintactico.setStyleSheet("""
            QTreeWidget {
                background-color: rgb(46,46,46);
                color: #dcdcaa;
                font-family: Consolas, monospace;
                font-size: 14px;
                border: none;
            }
            QTreeWidget::item:hover { background-color: rgb(60,60,60); }
            QTreeWidget::item:selected { background-color: #062f4a; }
        """)
        self.panelSintactico.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.panelSintactico.header().setStretchLastSection(False)

        # Semántico
        self.panelSemantico = QTreeWidget()
        self.panelSemantico.setStyle(self._tree_branch_style)
        self.panelSemantico.setHeaderHidden(True)
        self.panelSemantico.setFrameShape(QFrame.NoFrame)
        self.panelSemantico.setStyleSheet("""
            QTreeWidget {
                background-color: rgb(46,46,46);
                color: #dcdcaa;
                font-family: Consolas, monospace;
                font-size: 13px;
                border: none;
            }
            QTreeWidget::item:hover { background-color: rgb(60,60,60); }
            QTreeWidget::item:selected { background-color: #062f4a; }
        """)
        self.panelSemantico.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.panelSemantico.header().setStretchLastSection(False)

        # Tabla de Símbolos
        self.panelTabla = QTableWidget()
        self.panelTabla.setColumnCount(4)
        self.panelTabla.setHorizontalHeaderLabels(["Lexema", "Tipo", "Offset", "Líneas"])
        self.panelTabla.verticalHeader().setVisible(False)
        self.panelTabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.panelTabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.panelTabla.setWordWrap(True)
        self.panelTabla.setFrameShape(QFrame.NoFrame)
        header = self.panelTabla.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setMinimumSectionSize(65)
        self.panelTabla.setColumnWidth(0, 80)
        self.panelTabla.setColumnWidth(1, 75)
        self.panelTabla.setColumnWidth(2, 75)
        self.panelTabla.setStyleSheet("""
            QTableWidget {
                background-color: rgb(46,46,46);
                color: #ffffff;
                font-family: Consolas, monospace;
                font-size: 12px;
                border: none;
                gridline-color: #555555;
            }
            QTableWidget::item {
                padding: 4px 6px;
            }
            QHeaderView::section {
                background-color: rgb(33,33,33);
                color: #9cdcfe;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #555555;
            }
        """)

        # Panel de Código Intermedio (.tm y .ci diferenciados)
        self.panelCodigo = QTabWidget()
        self.panelCodigo.setDocumentMode(True)

        self.panelCodigoTM = QTextEdit()
        self.panelCodigoTM.setReadOnly(True)
        self.panelCodigoTM.setLineWrapMode(QTextEdit.NoWrap)
        self.panelCodigoTM.setFrameShape(QFrame.NoFrame)
        self.panelCodigoTM.setFont(QFont("Consolas", 10))

        self.panelCodigoCI = QTextEdit()
        self.panelCodigoCI.setReadOnly(True)
        self.panelCodigoCI.setLineWrapMode(QTextEdit.NoWrap)
        self.panelCodigoCI.setFrameShape(QFrame.NoFrame)
        self.panelCodigoCI.setFont(QFont("Consolas", 10))

        self.panelCodigo.addTab(self.panelCodigoTM, "Código Objeto TM (.tm)")
        self.panelCodigo.addTab(self.panelCodigoCI, "Código intermedio de tres direcciones (.ci)")

        self.stackedPanels.addWidget(self.panelArchivos)
        self.stackedPanels.addWidget(self.panelLexico)
        self.stackedPanels.addWidget(self.panelSintactico)
        self.stackedPanels.addWidget(self.panelSemantico)
        self.stackedPanels.addWidget(self.panelTabla)
        self.stackedPanels.addWidget(self.panelCodigo)

        self.sideBarDock = QDockWidget("Explorer", self)
        self.sideBarDock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.sideBarDock.setWidget(self.stackedPanels)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sideBarDock)
        self.resizeDocks([self.sideBarDock], [480], Qt.Horizontal)

        # Barra de botones vertical
        self.activityBar = QToolBar("Barra de Actividades")
        self.activityBar.setMovable(False)
        self.addToolBar(Qt.LeftToolBarArea, self.activityBar)

        self.actArchivos = QAction("Explorer", self)
        self.actLexico = QAction("Léxico", self)
        self.actSintactico = QAction("Sintáctico", self)
        self.actSemantico = QAction("Semántico", self)
        self.actTabla = QAction("Tabla Símb.", self)
        self.actCodigo = QAction("Código Int.", self)

        self.activityBar.addAction(self.actArchivos)
        self.activityBar.addAction(self.actLexico)
        self.activityBar.addAction(self.actSintactico)
        self.activityBar.addAction(self.actSemantico)
        self.activityBar.addAction(self.actTabla)
        self.activityBar.addAction(self.actCodigo)

        self.actArchivos.triggered.connect(lambda: self.switchSidePanel(0, 'Explorer'))
        self.actLexico.triggered.connect(lambda: self.switchSidePanel(1, "Análisis Léxico"))
        self.actSintactico.triggered.connect(lambda: self.switchSidePanel(2, "Análisis Sintáctico"))
        self.actSemantico.triggered.connect(lambda: self.switchSidePanel(3, "Análisis Semántico"))
        self.actTabla.triggered.connect(lambda: self.switchSidePanel(4, "Tabla de Símbolos"))
        self.actCodigo.triggered.connect(lambda: self.switchSidePanel(5, "Código Intermedio"))

        self.setDarkTheme()

    # =========================================================
    # FASES DE COMPILACIÓN
    # =========================================================
    def ejecutarAnalisisLexico(self):
        self.stackedPanels.setCurrentIndex(1)
        self.sideBarDock.setWindowTitle("Análisis Léxico")
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()

        texto = self.textEdit.toPlainText()
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
        c_err = "#ff0000"

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
                <div style='margin-bottom: 6px; font-family: Consolas, monospace;'>
                    <span style='color: {color}; font-weight: bold;'>[{t.tipo}]</span><br>
                    <span style='color: {c_texto};'>Lexema: <b>'{lexema_mostrar}'</b></span><br>
                    <span style='color: {c_sub}; font-size: 11px;'>Ubicación: Línea {t.linea}, Columna {t.columna}</span>
                    <hr style='border: 0.5px solid {c_sub}; margin-top: 4px;'>
                </div>
            """
        self.panelLexico.setHtml(html_tokens)

        self.terminalPanel.show()
        if errores:
            html_errores = f"<span style='color: {c_err}; margin-top: 0;'>Errores léxicos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores:
                html_errores += f"<li style='color: {c_err}; margin-bottom: 5px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
        else:
            exito_msg = f"""
                <span style='color: {c_texto}; margin-top: 0;'>Análisis léxico finalizado con éxito.</span><br>
                <span style='color: {c_texto};'>0 errores léxicos encontrados en el código.</span>
            """
            self.terminalOutput.setHtml(exito_msg)

    def ejecutarAnalisisSintactico(self):
        self.stackedPanels.setCurrentIndex(2)
        self.sideBarDock.setWindowTitle("Análisis Sintáctico")
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()

        self.panelSintactico.clear()

        texto = self.textEdit.toPlainText()
        analizador_lex = AnalizadorLexico()
        tokens, errores_lex = analizador_lex.analizar(texto)

        if not tokens:
            self.terminalPanel.show()
            self.terminalOutput.setHtml("<h4 style='color: #ff5555; margin-top: 0;'>No hay tokens para analizar.</h4>")
            return

        tokens_limpios = [t for t in tokens if t.tipo != "COMENTARIO"]
        analizador_sint = AnalizadorSintactico(tokens_limpios)
        ast_raiz, errores_sint = analizador_sint.analizar()

        self.dibujarAST(ast_raiz, self.panelSintactico)
        self.panelSintactico.expandAll()

        self.terminalPanel.show()
        c_err = "#ff0000"
        c_texto = "#ffffff"

        if errores_sint:
            html_errores = f"<span style='color: {c_err}; margin-top: 0;'>Errores sintácticos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_sint:
                html_errores += f"<li style='color: {c_err}; margin-bottom: 5px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
        else:
            exito_msg = f"""
                <span style='color: {c_texto}; margin-top: 0;'>Análisis sintáctico finalizado con éxito.</span><br>
                <span style='color: {c_texto};'>0 errores sintácticos encontrados en el código.</span>
            """
            self.terminalOutput.setHtml(exito_msg)
            self.generar_txt_ast(ast_raiz)

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

    def ejecutarAnalisisSemantico(self):
        self.stackedPanels.setCurrentIndex(3)
        self.sideBarDock.setWindowTitle("Análisis Semántico (AST Anotado)")
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()

        self.panelSemantico.clear()
        self.panelTabla.setRowCount(0)

        texto = self.textEdit.toPlainText()
        if not texto.strip():
            self.terminalPanel.show()
            self.terminalOutput.setHtml("<span style='color: #ff0000;'>No hay código para analizar.</span>")
            return None, None

        # 1. Análisis léxico
        analizador_lex = AnalizadorLexico()
        tokens, errores_lex = analizador_lex.analizar(texto)
        if errores_lex:
            self.terminalPanel.show()
            html_errores = "<span style='color: #ff0000; margin-top: 0;'>Errores léxicos impidieron el análisis semántico:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_lex:
                html_errores += f"<li style='color: #ff0000; margin-bottom: 5px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
            return None, None

        # 2. Análisis sintáctico
        tokens_limpios = [t for t in tokens if t.tipo != "COMENTARIO"]
        analizador_sint = AnalizadorSintactico(tokens_limpios)
        ast_original, errores_sint = analizador_sint.analizar()

        self.panelSintactico.clear()
        self.dibujarAST(ast_original, self.panelSintactico)
        self.panelSintactico.expandAll()

        if errores_sint:
            self.terminalPanel.show()
            html_errores = "<span style='color: #ff0000; margin-top: 0;'>Errores sintácticos impidieron el análisis semántico:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_sint:
                html_errores += f"<li style='color: #ff0000; margin-bottom: 5px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
            return None, None

        # 3. Análisis semántico
        analizador_sem = AnalizadorSemantico()
        ast_anotado, tabla_simbolos, errores_sem = analizador_sem.analizar(ast_original)

        self.dibujarASTAnotado(ast_anotado, self.panelSemantico)
        self.panelSemantico.expandAll()

        # Poblar Tabla de Símbolos
        simbolos = tabla_simbolos.obtener_simbolos()
        self.panelTabla.setRowCount(len(simbolos))
        for row, s in enumerate(simbolos):
            lineas_str = ", ".join(map(str, sorted(s.lineas)))
            item_nom = QTableWidgetItem(s.nombre)
            item_tipo = QTableWidgetItem(s.tipo)
            item_off = QTableWidgetItem(str(s.desplazamiento))
            item_lin = QTableWidgetItem(lineas_str)

            item_nom.setTextAlignment(Qt.AlignCenter)
            item_tipo.setTextAlignment(Qt.AlignCenter)
            item_off.setTextAlignment(Qt.AlignCenter)
            item_lin.setTextAlignment(Qt.AlignCenter)

            self.panelTabla.setItem(row, 0, item_nom)
            self.panelTabla.setItem(row, 1, item_tipo)
            self.panelTabla.setItem(row, 2, item_off)
            self.panelTabla.setItem(row, 3, item_lin)

        self.panelTabla.resizeRowsToContents()

        self.terminalPanel.show()
        c_err = "#ff0000"
        c_texto = "#ffffff"

        if errores_sem:
            html = f"<span style='color: {c_err}; margin-top: 0;'>Errores semánticos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_sem:
                html += f"<li style='color: {c_err}; margin-bottom: 5px;'>{e}</li>"
            html += "</ul>"
            self.terminalOutput.setHtml(html)
            return None, None
        else:
            exito_msg = f"""
                <span style='color: {c_texto}; margin-top: 0;'>Análisis semántico finalizado con éxito.</span><br>
                <span style='color: {c_texto};'>0 errores semánticos encontrados en el código.</span>
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
            item.setForeground(0, QColor("#ff5555"))
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
        # Limpiar salidas previas para garantizar correspondencia con el fuente actual
        self.panelCodigoTM.clear()
        self.panelCodigoCI.clear()
        self.ultimo_archivo_tm = None
        self.ultimo_archivo_ci = None
        self.codigo_fuente_compilado = None

        # Ejecutar validación completa (Léxico -> Sintáctico -> Semántico)
        ast_anotado, tabla_simbolos = self.ejecutarAnalisisSemantico()
        if not ast_anotado or not tabla_simbolos:
            return False

        # Cambiar vista lateral a Código Intermedio
        self.stackedPanels.setCurrentIndex(5)
        self.sideBarDock.setWindowTitle("Código Intermedio")
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()
        if self.sideBarDock.width() < 480:
            self.resizeDocks([self.sideBarDock], [500], Qt.Horizontal)

        # Determinar rutas de salida (.tm y .ci)
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

        # 1. Generar código intermedio de tres direcciones (.ci - salida didáctica)
        gen_ci = GeneradorCodigoIntermedio()
        codigo_ci = gen_ci.generar(ast_anotado)

        # 2. Generar código objeto para Tiny Machine (.tm - salida ejecutable)
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
                f"<span style='color: #ff0000;'>Error al escribir archivos de código generado: {e}</span>"
            )
            return False

        # Mostrar ambos códigos en pestañas separadas dentro de Código Intermedio
        self.panelCodigoTM.setPlainText(codigo_tm)
        self.panelCodigoCI.setPlainText(codigo_ci)
        self.panelCodigo.setCurrentIndex(0)

        # Si hay un archivo abierto en el explorador, agregar .tm y .ci al árbol
        if self.current_path:
            self.addFileToTree(ruta_tm)
            self.addFileToTree(ruta_ci)

        self.ultimo_archivo_tm = ruta_tm
        self.ultimo_archivo_ci = ruta_ci
        self.codigo_fuente_compilado = self.textEdit.toPlainText()

        # Informar en terminal
        self.terminalPanel.show()
        msg_html = f"""
            <span style='color: #ffffff;'>Generación de código finalizada con éxito.</span><br>
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
        # Regenerar siempre para garantizar que el .tm corresponda al código actual del editor
        if not self.generarCodigoIntermedioAction():
            return

        ruta_tm = self.ultimo_archivo_tm
        if not ruta_tm or not os.path.isfile(ruta_tm):
            self.terminalPanel.show()
            self.terminalOutput.setHtml(
                "<span style='color: #ff0000;'>No se encontró un archivo .tm válido para ejecutar.</span>"
            )
            return

        tm_bin, error_tm = self._obtener_ejecutable_tm()
        if error_tm:
            self.terminalPanel.show()
            self.terminalOutput.setHtml(f"<span style='color: #ff0000;'>{error_tm}</span>")
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
            self.terminalOutput.setHtml(f"""
                <span style='color: #ffffff;'>Simulador TM iniciado con: <b>{os.path.basename(ruta_tm)}</b></span><br>
                <span style='color: #dcdcaa;'>Comandos dentro de la consola TM: <b>g</b> (ejecutar programa), <b>v</b> (ver .ci), <b>r</b> (registros), <b>d 0 10</b> (memoria), <b>q</b> (salir).</span>
            """)
        except Exception as e:
            self.terminalPanel.show()
            self.terminalOutput.setHtml(
                f"<span style='color: #ff0000;'>Error al abrir el simulador TM: {e}</span>"
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
        self.setWindowTitle("IDE - Untitled")
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
            self.setWindowTitle("IDE - " + fileName)
            self.limpiarPanelesAnalisis()
            self.switchSidePanel(0, "Explorer")

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
            self.setWindowTitle("IDE - Untitled")
            self.limpiarPanelesAnalisis()

    def closeEvent(self, event):
        if self.textEdit.toPlainText() != "":
            respuesta = QMessageBox.question(
                self,
                "Close IDE",
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
            self.setWindowTitle("IDE - " + pathName)
            self.opened_files_content[pathName] = fileText
            self.addFileToTree(pathName)
            self.switchSidePanel(0, "Explorer")

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
            self.switchSidePanel(0, "Explorer")

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
    # VIEW FUNCTIONS
    # =========================
    def setDarkTheme(self):
        self.is_dark_mode = True
        self.setStyleSheet('''
            QWidget {
                background-color: rgb(33,33,33);
                color: #FFFFFF;
            }
            QPlainTextEdit, QTextEdit {
                background-color: rgb(46,46,46);
                border: none;
                outline: none;
            }
            QMenuBar {
                background-color: rgb(33,33,33);
            }
            QMenuBar::item:selected {
                background-color: rgb(60,60,60);
            }
            QMenu {
                background-color: rgb(46,46,46);
                border: 1px solid #555555;
            }
            QMenu::item:selected {
                background-color: rgb(60,60,60);
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: rgb(46,46,46);
            }
            QTabBar::tab {
                background-color: rgb(33,33,33);
                color: #cccccc;
                padding: 6px 10px;
                border: 1px solid #555555;
            }
            QTabBar::tab:selected {
                background-color: rgb(46,46,46);
                color: #9cdcfe;
                font-weight: bold;
            }
        ''')
        self.activityBar.setStyleSheet("""
            QToolBar {
                border: none;
                background: transparent;
            }
            QToolButton {
                min-width: 60px;
                max-width: 60px;
                padding: 6px;
                font-size: 11px;
                border: 1px solid #c0c0c0;
                background-color: rgb(33,33,33);
            }
            QToolButton:hover {
                background-color: rgb(60,60,60);
                border: 1px solid #a0a0a0;
            }
            QToolButton:pressed {
                background-color: #dae0e5;
            }
        """)
        self.terminalOutput.setStyleSheet("""
            QTextEdit {
                background-color: rgb(33,33,33);
                color: #ffffff;
                font-family: Consolas, monospace;
                font-size: 10pt;
                border: none;
            }
        """)

    def setLightTheme(self):
        self.is_dark_mode = False
        self.setStyleSheet('''
            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }
        ''')
        self.activityBar.setStyleSheet("""
            QToolBar {
                border: none;
                background: transparent;
            }
            QToolButton {
                min-width: 60px;
                max-width: 60px;
                padding: 6px;
                font-size: 11px;
                border: 1px solid #c0c0c0;
                background-color: #f8f9fa;
            }
            QToolButton:hover {
                background-color: #e2e6ea;
                border: 1px solid #a0a0a0;
            }
            QToolButton:pressed {
                background-color: #dae0e5;
            }
        """)
        self.terminalOutput.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #000000;
                font-family: Consolas, monospace;
                font-size: 10pt;
                border: none;
            }
        """)

    def increaseFont(self):
        self.current_fontSize += 1
        font = QFont("Consolas", self.current_fontSize)
        self.textEdit.document().setDefaultFont(font)
        self.textEdit.setFont(font)

    def decreaseFont(self):
        self.current_fontSize -= 1
        font = QFont("Consolas", self.current_fontSize)
        self.textEdit.document().setDefaultFont(font)
        self.textEdit.setFont(font)

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
            return

        self.stackedPanels.setCurrentIndex(index)
        self.sideBarDock.setWindowTitle(title)

        if index == 4:
            if self.sideBarDock.width() < 450:
                self.resizeDocks([self.sideBarDock], [460], Qt.Horizontal)
            self.panelTabla.resizeRowsToContents()
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
        self.setWindowTitle("IDE - " + clicked_path)
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
                self.setWindowTitle("IDE - Untitled")
                self.limpiarPanelesAnalisis()

        return True

    # =========================
    # ICONOS
    # =========================
    def setup_icons(self):
        style = self.style()
        self.actionNew.setIcon(style.standardIcon(style.SP_FileIcon))
        self.actionOpen.setIcon(style.standardIcon(style.SP_DirIcon))
        self.actionOpen_Folder.setIcon(style.standardIcon(style.SP_DirLinkIcon))
        self.actionSave.setIcon(style.standardIcon(style.SP_DialogSaveButton))
        self.actionSave_As.setIcon(style.standardIcon(style.SP_DriveFDIcon))
        self.actionClose.setIcon(style.standardIcon(style.SP_DialogCloseButton))
        self.actionExit.setIcon(style.standardIcon(style.SP_TitleBarCloseButton))

        self.actionUndo.setIcon(style.standardIcon(style.SP_ArrowBack))
        self.actionRedo.setIcon(style.standardIcon(style.SP_ArrowForward))
        self.actionCut.setIcon(style.standardIcon(style.SP_DialogResetButton))
        self.actionCopy.setIcon(style.standardIcon(style.SP_FileDialogContentsView))
        self.actionPaste.setIcon(style.standardIcon(style.SP_FileDialogDetailedView))

        self.actionDark_Theme.setIcon(style.standardIcon(style.SP_DesktopIcon))
        self.actionLight_Theme.setIcon(style.standardIcon(style.SP_DesktopIcon))
        self.actionIncrease_font_size.setIcon(style.standardIcon(style.SP_ArrowUp))
        self.actionDecrease_Font_Size.setIcon(style.standardIcon(style.SP_ArrowDown))
        self.actionTerminal.setIcon(style.standardIcon(style.SP_ComputerIcon))

        self.actionL_xico.setIcon(style.standardIcon(style.SP_FileDialogContentsView))
        self.actionSint_ctico.setIcon(style.standardIcon(style.SP_FileDialogListView))
        self.actionSem_ntico.setIcon(style.standardIcon(style.SP_FileDialogDetailedView))
        self.actionGenerar_c_digo_intermedio.setIcon(style.standardIcon(style.SP_FileDialogNewFolder))
        self.actionEjecutar.setIcon(style.standardIcon(style.SP_MediaPlay))

        quickBar = QToolBar("Quick Access", self.menuBar())
        quickBar.setMovable(False)
        quickBar.setFloatable(False)
        quickBar.setToolButtonStyle(Qt.ToolButtonIconOnly)

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

        quickBar.addSeparator()
        quickBar.addAction(self.actionIncrease_font_size)
        quickBar.addAction(self.actionDecrease_Font_Size)
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

        quickBar.setIconSize(QSize(23, 23))
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