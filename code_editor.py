from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt5.QtGui import QPainter, QColor, QTextFormat, QSyntaxHighlighter, QTextCharFormat
from PyQt5.QtCore import QRect, Qt
from lexico import AnalizadorLexico

class LexicalHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.analizador = AnalizadorLexico()
        self.tokens = []
        self.text_cache = ""
        
        # COLORES 
        self.formats = {
            "NUM_ENTERO": self.crear_formato("#b5cea8", False),
            "NUM_REAL": self.crear_formato("#b5cea8", False),   
            "ID": self.crear_formato("#9cdcfe", False),         
            "COMENTARIO": self.crear_formato("#6a9955", False), 
            "RESERVADA": self.crear_formato("#c586c0", True),   
            "ARITMETICO": self.crear_formato("#dcdcaa", False), 
            "RELACIONAL": self.crear_formato("#4ec9b0", False), 
            "LOGICO": self.crear_formato("#4ec9b0", False),      
            "SIMBOLO": self.crear_formato("#ffd700", False),    
            "ASIGNACION": self.crear_formato("#d4d4d4", False),  
            "CADENA": self.crear_formato("#ce9178", False),     
            "CARACTER": self.crear_formato("#ce9178", False)    
        }

    def crear_formato(self, color, es_negrita):
        formato = QTextCharFormat()
        formato.setForeground(QColor(color))
        if es_negrita:
            from PyQt5.QtGui import QFont
            formato.setFontWeight(QFont.Bold)
        return formato

    def highlightBlock(self, text):
        doc_text = self.document().toPlainText()
        
        if doc_text != self.text_cache:
            self.tokens, _ = self.analizador.analizar(doc_text)
            self.text_cache = doc_text

        block_num = self.currentBlock().blockNumber() + 1
        estado_bloque = 0 
        
        for t in self.tokens:
            # eliminar posibles retornos de carro de Windows por seguridad
            lineas_token = t.lexema.replace('\r', '').split('\n')
            linea_fin = t.linea + len(lineas_token) - 1
            
            if t.linea <= block_num <= linea_fin:
                if t.tipo in self.formats:
                    formato = self.formats[t.tipo]
                    
                    if t.linea == linea_fin:
                        self.setFormat(t.columna - 1, len(t.lexema), formato)
                    else:
                        idx_linea = block_num - t.linea
                        sub_lexema = lineas_token[idx_linea]
                        
                        if block_num == t.linea:
                            self.setFormat(t.columna - 1, len(text) - (t.columna - 1), formato)
                            # solo los comentarios pueden heredar el color hacia abajo
                            if t.tipo == "COMENTARIO": estado_bloque = 1 
                        elif block_num < linea_fin:
                            self.setFormat(0, len(text), formato)
                            if t.tipo == "COMENTARIO": estado_bloque = 1 
                        else:
                            self.setFormat(0, len(sub_lexema), formato)

        self.setCurrentBlockState(estado_bloque)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return self.codeEditor.lineNumberAreaSizeHint()

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        # activar scroll lateral
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        # espacio de los numeros de linea
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth(0)
        # para resaltar la linea actual

        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.highlightCurrentLine()

    # numero de linea
    def lineNumberAreaWidth(self):
        digits = 4
        space = 15 + self.fontMetrics().width('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#2b2b2b")) # color de fondo del margen

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#FFFFFF")) # color del número
                painter.drawText(0, int(top), self.lineNumberArea.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    # resaltado de linea actual
    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor(0, 120, 215, 40) 
            
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            
            extraSelections.append(selection)

        self.setExtraSelections(extraSelections)