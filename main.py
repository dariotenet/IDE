from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog, QMessageBox, QFrame, QDockWidget, QTextEdit, QToolBar, QStackedWidget, QVBoxLayout, QWidget, QAction, QMenu, QTreeWidget, QTreeWidgetItem, QHeaderView
from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QColor
import sys
import os

from code_editor import LexicalHighlighter
from lexico import AnalizadorLexico
from sintactico import AnalizadorSintactico

# clase que hereda las propiedas de qmainwindow
class Main(QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        loadUi("main.ui", self) # carga main.ui en la clase
        
        # =========================
        # VARIABLES
        # =========================
        self.current_path = None # para saber si es un archivo existente o nuevo
        self.current_fontSize = 10 # tam de la fuente
        self.is_dark_mode = True # saber en que tema está

        # EXTENSIONES PROHIBIDAS
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

        self.highlighter = LexicalHighlighter(self.textEdit.document()) # colores de sintaxis   

        self.textEdit.updateLineNumberAreaWidth(0) # soluciona overlap del editor y barra de numeros

        self.setWindowTitle("IDE - Untitled")

        # cursor
        self.textEdit.cursorPositionChanged.connect(self.update_cursor_position)
        self.update_cursor_position()

        #iconos
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
        # self.actionLight_Theme.triggered.connect(self.setLightTheme)
        self.actionIncrease_font_size.triggered.connect(self.increaseFont)
        self.actionDecrease_Font_Size.triggered.connect(self.decreaseFont)
        self.actionTerminal.triggered.connect(self.showTerminal)

        # =========================
        # COMPILAR ACTIONS
        # =========================
        self.actionL_xico.triggered.connect(self.ejecutarAnalisisLexico)
        self.actionSint_ctico.triggered.connect(self.ejecutarAnalisisSintactico)

        # ==========================================
        # TERMINAL
        # ==========================================
        self.terminalPanel = QDockWidget("Terminal", self)
        self.terminalPanel.setAllowedAreas(Qt.BottomDockWidgetArea) # anclada en la parte de abajo
        
        self.terminalOutput = QTextEdit()
        self.terminalOutput.setReadOnly(True) # lectura pq solo muestra mensajes
        
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
        self.opened_files_content = {} # diccionario para guardar el texto: {ruta: texto}
        
        # contenedor apilado
        self.stackedPanels = QStackedWidget()
        
        # explorador archivos
        self.panelArchivos = QTreeWidget()
        self.panelArchivos.setHeaderHidden(True) # ocultar la cabecera superior
        self.panelArchivos.setFrameShape(QFrame.NoFrame)
        self.panelArchivos.itemClicked.connect(self.switchToFile) # click cambiar archivo
        
        # cerrar archivo click derecho
        self.panelArchivos.setContextMenuPolicy(Qt.CustomContextMenu)
        self.panelArchivos.customContextMenuRequested.connect(self.showFileContextMenu)
        
        # diccionario para agrupar las carpetas
        self.tree_groups = {}
        
        # área de texto para cada opción
        self.panelLexico = QTextEdit()
        self.panelLexico.setReadOnly(True)
        self.panelLexico.setFrameShape(QFrame.NoFrame)
        self.panelLexico.setPlainText("")
        
        self.panelSintactico = QTreeWidget()
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
        # forzar que la columna siempre se ajuste al contenido automáticamente
        self.panelSintactico.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.panelSintactico.header().setStretchLastSection(False)

        self.panelSemantico = QTextEdit()
        self.panelSemantico.setReadOnly(True)
        self.panelSemantico.setFrameShape(QFrame.NoFrame)
        self.panelSemantico.setPlainText("")

        self.panelTabla = QTextEdit()
        self.panelTabla.setReadOnly(True)
        self.panelTabla.setFrameShape(QFrame.NoFrame)
        self.panelTabla.setPlainText("")

        self.panelCodigo = QTextEdit()
        self.panelCodigo.setReadOnly(True)
        self.panelCodigo.setFrameShape(QFrame.NoFrame)
        self.panelCodigo.setPlainText("")

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

        # barra de botones vertical
        self.activityBar = QToolBar("Barra de Actividades")
        self.activityBar.setMovable(False) 
        self.addToolBar(Qt.LeftToolBarArea, self.activityBar)

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
        
        self.addToolBar(Qt.LeftToolBarArea, self.activityBar)

        # acciones de botones
        self.actArchivos = QAction("Explorer", self)
        self.actLexico = QAction("Léxico", self)
        self.actSintactico = QAction("Sintáctico", self)
        self.actSemantico = QAction("Semántico", self)
        self.actTabla = QAction("Tabla Símb.", self)
        self.actCodigo = QAction("Código Int.", self)

        # agregar botones a la barra
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

    def ejecutarAnalisisLexico(self):
        # forzar la visibilidad del panel sin alternar 
        self.stackedPanels.setCurrentIndex(1)
        self.sideBarDock.setWindowTitle("Análisis Léxico")
        
        # si el panel estaba cerrado, lo abrimos, si ya estaba abierto no pasa nada
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()

        # extraer el texto y analizarlo
        texto = self.textEdit.toPlainText()
        analizador = AnalizadorLexico()
        tokens, errores = analizador.analizar(texto)
        
        # COLORES DEL MODO OSCURO 
        c_titulo = "#9cdcfe"
        c_res = "#c586c0"
        c_num = "#b5cea8"
        c_id = "#9cdcfe"
        c_rel = "#4ec9b0"
        c_com = "#6a9955"
        c_cad = "#ce9178"
        c_sim = "#ffd700"
        c_def = "#dcdcaa"
        
        c_texto = "#ffffff"
        c_sub = "gray"
        c_err = "#ff0000"
        c_ok = "#50fa7b"

        # imprimir los tokens
        html_tokens = f""
        for t in tokens:
            if t.tipo == "COMENTARIO":
                continue
            
            if t.tipo == "RESERVADA": color = c_res
            elif t.tipo in ["NUM_ENTERO", "NUM_REAL"]: color = c_num
            elif t.tipo == "ID": color = c_id
            elif t.tipo in ["RELACIONAL", "LOGICO"]: color = c_rel
            elif t.tipo in ["CADENA", "CARACTER"]: color = c_cad
            elif t.tipo == "SIMBOLO": color = c_sim
            else: color = c_def 

            lexema_mostrar = t.lexema
            if t.tipo in ["RELACIONAL", "LOGICO", "ARITMETICO", "ASIGNACION"]:
                # quitar espacios, saltos de línea y tabulaciones para que se vea "==" o "&&"
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
        
        # gestionar errores en la terminal
        if errores:
            self.terminalPanel.show() 
            html_errores = f"<span style='color: {c_err}; margin-top: 0;'>Errores léxicos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores:
                html_errores += f"<li style='color: {c_err}; margin-bottom: 5px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
        else:
            self.terminalPanel.show()
            exito_msg = f"""
                <span style='color: {c_texto}; margin-top: 0;'>Análisis léxico finalizado con éxito.</span>
                <span style='color: {c_texto};'>0 errores léxicos encontrados en el código.</span>
            """
            self.terminalOutput.setHtml(exito_msg)

    def ejecutarAnalisisSintactico(self):
        # forzar la visibilidad del panel sin alternar
        self.stackedPanels.setCurrentIndex(2)
        self.sideBarDock.setWindowTitle("Análisis Sintáctico")
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()

        # limpiar árbol anterior
        self.panelSintactico.clear()

        # extraer texto y ejecutar léxico para obtener los tokens
        texto = self.textEdit.toPlainText()
        analizador_lex = AnalizadorLexico()
        tokens, errores_lex = analizador_lex.analizar(texto)

        if not tokens:
            self.terminalPanel.show()
            self.terminalOutput.setHtml("<h4 style='color: #ff5555; margin-top: 0;'>No hay tokens para analizar.</h4>")
            return

        # ejecutar sintáctico con los tokens obtenidos
        tokens_limpios = [t for t in tokens if t.tipo != "COMENTARIO"]
        analizador_sint = AnalizadorSintactico(tokens_limpios)
        ast_raiz, errores_sint = analizador_sint.analizar()

        # dibujar AST en el panel sintáctico
        self.dibujarAST(ast_raiz, self.panelSintactico)
        self.panelSintactico.expandAll() # expandir carpetas para mostrar todo el árbol

        # errores en la terminal
        self.terminalPanel.show()
        c_err = "#ff0000"
        c_texto = "#ffffff"
        c_ok = "#50fa7b"

        if errores_sint:
            html_errores = f"<span style='color: {c_err}; margin-top: 0;'>Errores sintácticos encontrados:</span><ul style='list-style: none; padding-left: 0; margin-top: 5px;'>"
            for e in errores_sint:
                html_errores += f"<li style='color: {c_err};  margin-bottom: 5px;'>{e}</li>"
            html_errores += "</ul>"
            self.terminalOutput.setHtml(html_errores)
        else:
            exito_msg = f"""
                <span style='color: {c_texto}; margin-top: 0;'>Análisis sintáctico finalizado con éxito.</span>
                <span style='color: {c_texto};'>0 errores sintácticos encontrados en el código.</span>
            """
            self.terminalOutput.setHtml(exito_msg)

            self.generar_txt_ast(ast_raiz)

    def dibujarAST(self, nodo_ast, parent_widget):
        if not nodo_ast: return
        
        # armar texto del nodo
        texto_item = nodo_ast.etiqueta
        if nodo_ast.lexema:
            texto_item += f" : '{nodo_ast.lexema}'"
            
        # crear carpeta o archivo visual
        item = QTreeWidgetItem(parent_widget, [texto_item])
        
        # celeste para estructuras generales (ramas), naranja para los valores finales (hojas)
        if len(nodo_ast.hijos) == 0:
            item.setForeground(0, QColor("#ce9178")) # naranja (no tiene hijos)
        else:
            item.setForeground(0, QColor("#9cdcfe")) # celeste (si tiene hijos)
            
        # llamada recursiva para dibujar a los hijos
        for hijo in nodo_ast.hijos:
            self.dibujarAST(hijo, item)

    # =========================
    # STATUS BAR FUNCTION
    # =========================
    def update_cursor_position(self):
        cursor = self.textEdit.textCursor() # obtener cursor actual
        line = cursor.blockNumber() + 1 # linea actual
        col = cursor.columnNumber() + 1 # columna

        self.statusBar().showMessage(f"Ln {line}, Col {col}") # mostrar

    # =========================
    # FILE FUNCTIONS
    # =========================
    def newFile(self):
        # untitled con texto sin guardar
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
                    
        # si estamoss viendo un archivo que si existe, guardar progreso temporal en memoria
        elif self.current_path is not None:
            self.opened_files_content[self.current_path] = self.textEdit.toPlainText()

        # limpiar para el nuevo archivo
        self.textEdit.clear()
        self.setWindowTitle("IDE - Untitled")
        self.current_path = None
        self.limpiarPanelesAnalisis()
    
    def openFile(self):
        # verificar si esta en untitled y con texto
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
            
            # guardar como
            elif respuesta == QMessageBox.Yes:
                self.saveFileAs()
                if self.current_path is None:
                    return

        fileName, _ = QFileDialog.getOpenFileName(self, 'Open File', '', 'All files (*.*)')
        
        if fileName:
            if self.current_path:
                self.opened_files_content[self.current_path] = self.textEdit.toPlainText()

            with open(fileName, 'r') as f:
                fileText = f.read()
    
            self.opened_files_content[fileName] = fileText
            
            self.addFileToTree(fileName)
            
            self.textEdit.setPlainText(fileText)
            self.current_path = fileName
            self.setWindowTitle("IDE - " + fileName)

            self.limpiarPanelesAnalisis()
            
            # actualizar panel
            self.switchSidePanel(0, "Archivos Abiertos")

    def saveFile(self):
        if self.current_path is not None:
            fileText = self.textEdit.toPlainText() 
            with open(self.current_path, 'w') as f:
                f.write(fileText) # escribir en el archivo
        else:
            self.saveFileAs() # guardar como si es un archivo nuevo

    def closeFile(self):
        if self.textEdit.toPlainText() != "":
            respuesta = QMessageBox.question(self, "Close File", "Save changes?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if respuesta == QMessageBox.Cancel: return
            elif respuesta == QMessageBox.Yes: self.saveFile()

        if self.current_path:
            if self.current_path in self.opened_files_content: del self.opened_files_content[self.current_path]
            
            # quitar del árbol
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
        if archivos_restantes: self.switchToFile(archivos_restantes[-1])
        else: 
            self.setWindowTitle("IDE - Untitled")
            self.limpiarPanelesAnalisis()

    # función para exit o cuando se presiona la X de la ventana, dialogo de seguridad para el usuario
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
            with open(pathName, 'w') as f:
                f.write(fileText)
                
            self.current_path = pathName
            self.setWindowTitle("IDE - " + pathName)

            self.opened_files_content[pathName] = fileText
            
            self.addFileToTree(pathName)
                
            self.switchSidePanel(0, "Explorer")
    
    def openFolder(self):
        folder_path = QFileDialog.getExistingDirectory(self, 'Open Folder', '')
        
        if folder_path:
            # lista de los elementos de la carpeta
            archivos = os.listdir(folder_path)
            
            for archivo in archivos:
                ruta_completa = os.path.join(folder_path, archivo)
                ruta_completa = ruta_completa.replace('\\', '/')

                if os.path.isfile(ruta_completa):
                    _, extension = os.path.splitext(ruta_completa) # extrae extensión
                    
                    # agregar si no está en la lista negra
                    if extension.lower() not in self.ignored_extensions:
                        self.addFileToTree(ruta_completa)
            
            # mostrar
            self.switchSidePanel(0, "Explorer")

    # edit
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
        # mostrar panel si está oculto
        if not self.sideBarDock.isVisible():
            self.sideBarDock.show()
        
        # ocultar panel si se hace click en el botón del q se está mostrando
        elif self.stackedPanels.currentIndex() == index:
            self.sideBarDock.hide()
            return

        # cambiar panel y título al seleccionado
        self.stackedPanels.setCurrentIndex(index)
        self.sideBarDock.setWindowTitle(title)
    
    def limpiarPanelesAnalisis(self):
        self.panelLexico.setPlainText("")
        self.panelSintactico.clear()
        # limpiar y ocultar terminal
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
            root_item.setExpanded(True) # abierto por defecto
            
            self.tree_groups[folder_path] = root_item
        else:
            root_item = self.tree_groups[folder_path]

        # no duplicar archivo
        for i in range(root_item.childCount()):
            if root_item.child(i).data(0, Qt.UserRole) == file_path:
                return 

        # archivo como hijo de la carpeta
        file_item = QTreeWidgetItem(root_item, [os.path.basename(file_path)])
        file_item.setData(0, Qt.UserRole, file_path)

    def get_all_file_items(self):
        # ver los archivos abiertos del árbol
        items = []
        for i in range(self.panelArchivos.topLevelItemCount()):
            root = self.panelArchivos.topLevelItem(i)
            for j in range(root.childCount()):
                items.append(root.child(j))
        return items

    def switchToFile(self, item, column=0):
        # ruta
        clicked_path = item.data(0, Qt.UserRole) 
        
        # si es carpeta solo se expande/cierra sola
        if not os.path.isfile(clicked_path): return
        
        if clicked_path == self.current_path: return
        
        if self.current_path is None and self.textEdit.toPlainText().strip() != "":
            respuesta = QMessageBox.question(self, "Save File", "Do you want to save your 'Untitled' file?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if respuesta == QMessageBox.Cancel: return 
            elif respuesta == QMessageBox.Yes:
                self.saveFileAs()
                if self.current_path is None: return
                    
        elif self.current_path is not None:
            self.opened_files_content[self.current_path] = self.textEdit.toPlainText()
            
        if clicked_path not in self.opened_files_content:
            try:
                with open(clicked_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.opened_files_content[clicked_path] = f.read()
            except Exception as e:
                return
                
        self.textEdit.setPlainText(self.opened_files_content.get(clicked_path, ""))
        self.current_path = clicked_path
        self.setWindowTitle("IDE - " + clicked_path)

        self.limpiarPanelesAnalisis()

    def showFileContextMenu(self, pos):
        # menú click derecho
        item = self.panelArchivos.itemAt(pos)
        if not item: return
        
        ruta_item = item.data(0, Qt.UserRole)
        menu = QMenu()
        
        # si la ruta es de un archivo entonces "Close File"
        if os.path.isfile(ruta_item):
            close_action = menu.addAction("Close File")
            action = menu.exec_(self.panelArchivos.mapToGlobal(pos))
            if action == close_action:
                self.closeFileFromExplorer(item)
                
        # si no entonces "Close Folder"
        else:
            close_action = menu.addAction("Close Folder")
            action = menu.exec_(self.panelArchivos.mapToGlobal(pos))
            if action == close_action:
                self.closeFolderFromExplorer(item)
    
    # preguntar si se quiere cerrar la carpeta
    def closeFolderFromExplorer(self, folder_item):
        nombre_carpeta = folder_item.text(0)
        
        respuesta = QMessageBox.question(
            self, 
            "Close Folder", 
            f"Do you want to close the folder '{nombre_carpeta}' and all its files?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes
        )
        
        if respuesta == QMessageBox.No: return

        for i in range(folder_item.childCount() - 1, -1, -1):
            child = folder_item.child(i)
            exito = self.closeFileFromExplorer(child)
            
            if exito == False:
                return

    def closeFileFromExplorer(self, item):
        path_to_remove = item.data(0, Qt.UserRole)
        if not os.path.isfile(path_to_remove): return False # evita cerrar el separador de golpe
        
        # --- NUEVA LÓGICA INTELIGENTE ---
        necesita_comprobar = False
        
        if path_to_remove == self.current_path:
            fileText = self.textEdit.toPlainText()
            necesita_comprobar = True
        elif path_to_remove in self.opened_files_content:
            fileText = self.opened_files_content[path_to_remove]
            necesita_comprobar = True
            
        # Solo leemos el disco duro si el archivo realmente fue abierto en el IDE
        if necesita_comprobar:
            try:
                with open(path_to_remove, 'r', encoding='utf-8', errors='ignore') as f:
                    diskText = f.read()
            except Exception:
                diskText = "" 
                
            # solo pregunta si se hicieron cambios
            if fileText != diskText:
                nombre_archivo = os.path.basename(path_to_remove)
                respuesta = QMessageBox.question(self, "Close File", f"Save changes to '{nombre_archivo}'?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
                
                if respuesta == QMessageBox.Cancel: return False
                elif respuesta == QMessageBox.Yes:
                    with open(path_to_remove, 'w', encoding='utf-8') as f: f.write(fileText)
        # --------------------------------

        # quitar de la ui
        parent_item = item.parent()
        if parent_item:
            parent_item.removeChild(item)
            if parent_item.childCount() == 0:
                folder_path = parent_item.data(0, Qt.UserRole)
                self.panelArchivos.takeTopLevelItem(self.panelArchivos.indexOfTopLevelItem(parent_item))
                del self.tree_groups[folder_path]
        
        # limpiar memoria
        if path_to_remove in self.opened_files_content: del self.opened_files_content[path_to_remove]
            
        if path_to_remove == self.current_path:            
            self.current_path = None 
            self.textEdit.clear()
            archivos_restantes = self.get_all_file_items()
            if archivos_restantes: self.switchToFile(archivos_restantes[-1])
            else: 
                self.setWindowTitle("IDE - Untitled")
                self.limpiarPanelesAnalisis()
            
        return True

    # =========================
    # ICONOS
    # =========================
    def setup_icons(self):
        style = self.style()

        # iconos en FILE
        self.actionNew.setIcon(style.standardIcon(style.SP_FileIcon))
        self.actionOpen.setIcon(style.standardIcon(style.SP_DirIcon))
        self.actionOpen_Folder.setIcon(style.standardIcon(style.SP_DirLinkIcon))
        self.actionSave.setIcon(style.standardIcon(style.SP_DialogSaveButton))
        self.actionSave_As.setIcon(style.standardIcon(style.SP_DriveFDIcon))
        self.actionClose.setIcon(style.standardIcon(style.SP_DialogCloseButton))
        self.actionExit.setIcon(style.standardIcon(style.SP_TitleBarCloseButton))

        # Iconos en Menu
        self.actionUndo.setIcon(style.standardIcon(style.SP_ArrowBack))
        self.actionRedo.setIcon(style.standardIcon(style.SP_ArrowForward))
        self.actionCut.setIcon(style.standardIcon(style.SP_DialogResetButton))
        self.actionCopy.setIcon(style.standardIcon(style.SP_FileDialogContentsView))
        self.actionPaste.setIcon(style.standardIcon(style.SP_FileDialogDetailedView))

        # Iconos en Vista
        self.actionDark_Theme.setIcon(style.standardIcon(style.SP_DesktopIcon))
        self.actionLight_Theme.setIcon(style.standardIcon(style.SP_DesktopIcon))
        self.actionIncrease_font_size.setIcon(style.standardIcon(style.SP_ArrowUp))
        self.actionDecrease_Font_Size.setIcon(style.standardIcon(style.SP_ArrowDown))
        self.actionTerminal.setIcon(style.standardIcon(style.SP_ComputerIcon))

        #Iconos en Compilar
        self.actionL_xico.setIcon(style.standardIcon(style.SP_FileDialogContentsView))
        self.actionSint_ctico.setIcon(style.standardIcon(style.SP_FileDialogListView))
        self.actionSem_ntico.setIcon(style.standardIcon(style.SP_FileDialogDetailedView))
        self.actionGenerar_c_digo_intermedio.setIcon(style.standardIcon(style.SP_FileDialogNewFolder))
        self.actionEjecutar.setIcon(style.standardIcon(style.SP_MediaPlay))

        #Iconos apareciendo en el ToolBar
        quickBar = QToolBar("Quick Access", self.menuBar())
        quickBar.setMovable(False)
        quickBar.setFloatable(False)
        quickBar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        # FILE section
        quickBar.addAction(self.actionNew)
        quickBar.addAction(self.actionOpen)
        quickBar.addAction(self.actionOpen_Folder)
        quickBar.addAction(self.actionSave)
        quickBar.addAction(self.actionSave_As)
        quickBar.addAction(self.actionClose)
        quickBar.addAction(self.actionExit)
        quickBar.addSeparator()  # |

        # EDIT section
        quickBar.addAction(self.actionUndo)
        quickBar.addAction(self.actionRedo)
        quickBar.addSeparator()  # |
        quickBar.addAction(self.actionCut)
        quickBar.addAction(self.actionCopy)
        quickBar.addAction(self.actionPaste)
        quickBar.addSeparator()  # |

        # VIEW section
        # quickBar.addAction(self.actionDark_Theme)
        # quickBar.addAction(self.actionLight_Theme)
        quickBar.addSeparator()  # |
        quickBar.addAction(self.actionIncrease_font_size)
        quickBar.addAction(self.actionDecrease_Font_Size)
        quickBar.addSeparator()  # |
        quickBar.addAction(self.actionTerminal)
        quickBar.addSeparator()  # |

        # COMPILAR section
        quickBar.addAction(self.actionL_xico)
        quickBar.addAction(self.actionSint_ctico)
        quickBar.addAction(self.actionSem_ntico)
        quickBar.addSeparator()  # |
        quickBar.addAction(self.actionGenerar_c_digo_intermedio)
        quickBar.addSeparator()  # |
        quickBar.addAction(self.actionEjecutar)

        # tamaño de los iconos
        quickBar.setIconSize(QSize(23, 23))
        self.addToolBar(Qt.TopToolBarArea, quickBar)
    
    def generar_txt_ast(self, nodo_raiz):
        if not nodo_raiz: return

        lineas_texto = []

        def recorrer(nodo, nivel):
            # 4 espacios para cada nivel de profundidad
            sangria = "    " * nivel
            
            # armar el texto del nodo
            texto = f"{sangria}- {nodo.etiqueta}"
            if nodo.lexema:
                texto += f" : '{nodo.lexema}'"
                
            lineas_texto.append(texto)
            
            # llamada recursiva para los hijos
            for hijo in nodo.hijos:
                recorrer(hijo, nivel + 1)

        # iniciar recorrido
        recorrer(nodo_raiz, 0)

        # guardar en el mismo directorio del proyecto
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