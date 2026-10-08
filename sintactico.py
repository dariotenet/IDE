class NodoAST:
    def __init__(self, etiqueta, lexema="", linea=0, columna=0):
        self.etiqueta = etiqueta
        self.lexema = lexema
        self.linea = linea
        self.columna = columna
        self.hijos = []
        # Atributos para análisis semántico (Fase 3)
        self.dtype = None          # Tipo de dato ('int', 'float', 'bool', etc.)
        self.val = None            # Valor constante calculado (si aplica)
        self.coercion = None       # Coerción realizada (ej. 'int_a_float')
        self.desplazamiento = None # Desplazamiento de memoria / offset

    def agregar_hijo(self, nodo):
        if nodo:
            self.hijos.append(nodo)

    def copiar(self):
        """Copia profunda para separar AST original del AST anotado."""
        nuevo = NodoAST(self.etiqueta, self.lexema, self.linea, self.columna)
        nuevo.dtype = self.dtype
        nuevo.val = self.val
        nuevo.coercion = self.coercion
        nuevo.desplazamiento = self.desplazamiento
        for h in self.hijos:
            nuevo.agregar_hijo(h.copiar() if hasattr(h, 'copiar') else h)
        return nuevo


class AnalizadorSintactico:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.token_actual = self.tokens[0] if tokens else None
        self.errores = []

    def avanzar(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.token_actual = self.tokens[self.pos]
        else:
            self.token_actual = None

    def coincidir(self, tipo_esperado, lexema_esperado=None):
        if self.token_actual and self.token_actual.tipo == tipo_esperado:
            if lexema_esperado and self.token_actual.lexema != lexema_esperado:
                self.registrar_error(f"Se esperaba '{lexema_esperado}' pero se encontró '{self.token_actual.lexema}'")
                return False
            self.avanzar()
            return True
        else:
            encontrado = self.token_actual.lexema if self.token_actual else "EOF"
            esperado = lexema_esperado if lexema_esperado else tipo_esperado
            self.registrar_error(f"Se esperaba '{esperado}' pero se encontró '{encontrado}'")
            return False

    def registrar_error(self, mensaje):
        mensaje = mensaje.replace('<', '&lt;').replace('>', '&gt;')
        linea = self.token_actual.linea if self.token_actual else "EOF"
        columna = self.token_actual.columna if self.token_actual else "EOF"
        error = f"Error Sintáctico en L:{linea} C:{columna} -> {mensaje}"
        if error not in self.errores:
            self.errores.append(error)

    # ==========================================
    # REGLAS DE LA GRAMÁTICA
    # ==========================================
    def analizar(self):
        raiz = self.programa()
        return raiz, self.errores

    # programa → main { lista_declaraciones lista_sentencias }
    def programa(self):
        linea = self.token_actual.linea if self.token_actual else 1
        col = self.token_actual.columna if self.token_actual else 1
        nodo = NodoAST("Programa", "", linea, col)
        if self.coincidir("RESERVADA", "main"):
            if self.coincidir("SIMBOLO", "{"):
                nodo.agregar_hijo(self.lista_declaracion())
                nodo.agregar_hijo(self.lista_sentencias(delimitadores=["}"]))
                self.coincidir("SIMBOLO", "}")
        return nodo

    # lista_declaraciones → declaracion_variable lista_declaraciones | ε
    def lista_declaracion(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Lista Declaraciones", "", linea, col)
        
        while self.token_actual and self.token_actual.lexema in ["int", "float", "bool"]:
            hijo = self.declaracion_variable()
            if hijo:
                nodo.agregar_hijo(hijo)
                
        return nodo

    # declaracion_variable → tipo identificador ;
    def declaracion_variable(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Declaracion Variable", "", linea, col)
        nodo.agregar_hijo(self.tipo())
        nodo.agregar_hijo(self.identificador())
        self.coincidir("SIMBOLO", ";")
        return nodo

    # identificador → id { , id }
    def identificador(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Identificadores", "", linea, col)
        if self.token_actual and self.token_actual.tipo == "ID":
            nodo.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna))
            self.avanzar()
            while self.token_actual and self.token_actual.lexema == ",":
                self.avanzar()
                if self.token_actual and self.token_actual.tipo == "ID":
                    nodo.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna))
                    self.avanzar()
                else:
                    self.registrar_error("Se esperaba un ID después de la coma")
                    break
        else:
            self.registrar_error("Se esperaba un identificador")
        return nodo

    # tipo → int | float | bool
    def tipo(self):
        if self.token_actual and self.token_actual.lexema in ["int", "float", "bool"]:
            nodo = NodoAST("Tipo", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            self.avanzar()
            return nodo
        self.registrar_error("Se esperaba tipo (int, float, bool)")
        return None

    # lista_sentencias → { sentencia }
    def lista_sentencias(self, delimitadores=None):
        if delimitadores is None:
            delimitadores = ["}"]
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Lista Sentencias", "", linea, col)
        primeros_sentencia = ["if", "while", "do", "cin", "cout", "++", "--"]
        
        while self.token_actual and self.token_actual.lexema not in delimitadores:
            if self.token_actual.lexema in primeros_sentencia or self.token_actual.tipo == "ID":
                pos_inicial = self.pos
                hijo = self.sentencia()
                if hijo:
                    nodo.agregar_hijo(hijo)
                    
                if self.pos == pos_inicial:
                    self.registrar_error(f"Sentencia no reconocida cerca de '{self.token_actual.lexema}'")
                    self.avanzar()
            else:
                self.registrar_error(f"Sintaxis inválida cerca de '{self.token_actual.lexema}'")
                self.avanzar()
                
        return nodo

    # sentencia → seleccion | iteracion | repeticion | sent_in | sent_out | asignacion
    def sentencia(self):
        lexema = self.token_actual.lexema
        if lexema == "if": return self.seleccion()
        elif lexema == "while": return self.iteracion()
        elif lexema == "do": return self.repeticion()
        elif lexema == "cin": return self.sent_in()
        elif lexema == "cout": return self.sent_out()
        elif self.token_actual.tipo == "ID" or lexema in ["++", "--"]: return self.asignacion()
        return None

    # asignacion → id = expresion ; | id ++ ; | id -- ; | ++ id ; | -- id ;
    def asignacion(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Instruccion / Asignacion", "", linea, col)

        # caso pre-incremento standalone (ej. ++x;)
        if self.token_actual.lexema in ["++", "--"]:
            nodo_inc = NodoAST(f"Pre-Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            self.avanzar()
            if self.token_actual and self.token_actual.tipo == "ID":
                nodo_inc.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna))
                self.avanzar()
                self.coincidir("SIMBOLO", ";")
                return nodo_inc

        # caso ID normal
        elif self.token_actual.tipo == "ID":
            nodo_id = NodoAST("ID", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            self.avanzar()

            # caso post-incremento standalone (ej. x++;)
            if self.token_actual and self.token_actual.lexema in ["++", "--"]:
                nodo_inc = NodoAST(f"Post-Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
                nodo_inc.agregar_hijo(nodo_id)
                self.avanzar()
                self.coincidir("SIMBOLO", ";")
                return nodo_inc
                
            # caso asignacion normal (ej. x = 5;)
            elif self.coincidir("ASIGNACION", "="):
                nodo.agregar_hijo(nodo_id)
                nodo.agregar_hijo(self.sent_expresion())
                return nodo
        return nodo

    # sent_expresion → expresion ;
    def sent_expresion(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Sentencia Expresion", "", linea, col)
        nodo.agregar_hijo(self.expresion())
        self.coincidir("SIMBOLO", ";")
        return nodo

    # seleccion → if ( expresion ) { lista_sentencias } [ else { lista_sentencias } ]
    #           | if expresion then lista_sentencias [ else lista_sentencias ] end
    def seleccion(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Seleccion (if)", "", linea, col)
        self.coincidir("RESERVADA", "if")
        
        tiene_parentesis = False
        if self.token_actual and self.token_actual.lexema == "(":
            tiene_parentesis = True
            self.avanzar()
            
        nodo.agregar_hijo(self.expresion())
        
        if tiene_parentesis:
            self.coincidir("SIMBOLO", ")")

        # Bloque then ... else ... end
        if self.token_actual and self.token_actual.lexema == "then":
            self.avanzar()
            nodo.agregar_hijo(self.lista_sentencias(delimitadores=["else", "end", "}"]))
            
            if self.token_actual and self.token_actual.lexema == "else":
                nodo_else = NodoAST("Else", "", self.token_actual.linea, self.token_actual.columna)
                self.avanzar()
                nodo_else.agregar_hijo(self.lista_sentencias(delimitadores=["end", "}"]))
                nodo.agregar_hijo(nodo_else)
                
            self.coincidir("RESERVADA", "end")
            if self.token_actual and self.token_actual.lexema == ";":
                self.avanzar()

        # Bloque { ... }
        elif self.token_actual and self.token_actual.lexema == "{":
            self.avanzar()
            nodo.agregar_hijo(self.lista_sentencias(delimitadores=["}"]))
            self.coincidir("SIMBOLO", "}")
            
            if self.token_actual and self.token_actual.lexema == "else":
                nodo_else = NodoAST("Else", "", self.token_actual.linea, self.token_actual.columna)
                self.avanzar()
                self.coincidir("SIMBOLO", "{")
                nodo_else.agregar_hijo(self.lista_sentencias(delimitadores=["}"]))
                self.coincidir("SIMBOLO", "}")
                nodo.agregar_hijo(nodo_else)
        else:
            self.registrar_error("Se esperaba 'then' o '{' después de la condición del if")
            
        return nodo

    # iteracion → while ( expresion ) { lista_sentencias }
    #           | while expresion lista_sentencias end
    def iteracion(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Iteracion (while)", "", linea, col)
        self.coincidir("RESERVADA", "while")
        
        tiene_parentesis = False
        if self.token_actual and self.token_actual.lexema == "(":
            tiene_parentesis = True
            self.avanzar()
            
        nodo.agregar_hijo(self.expresion())
        
        if tiene_parentesis:
            self.coincidir("SIMBOLO", ")")
            
        if self.token_actual and self.token_actual.lexema == "{":
            self.avanzar()
            nodo.agregar_hijo(self.lista_sentencias(delimitadores=["}"]))
            self.coincidir("SIMBOLO", "}")
        else:
            nodo.agregar_hijo(self.lista_sentencias(delimitadores=["end", "}"]))
            self.coincidir("RESERVADA", "end")
            if self.token_actual and self.token_actual.lexema == ";":
                self.avanzar()
                
        return nodo

    # repeticion → do { lista_sentencias } while ( expresion ) ;
    #            | do lista_sentencias until expresion
    def repeticion(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Repeticion (do)", "", linea, col)
        self.coincidir("RESERVADA", "do")
        
        if self.token_actual and self.token_actual.lexema == "{":
            self.avanzar()
            nodo.agregar_hijo(self.lista_sentencias(delimitadores=["}"]))
            self.coincidir("SIMBOLO", "}")
            
            if self.token_actual and self.token_actual.lexema == "until":
                self.avanzar()
                tiene_par = False
                if self.token_actual and self.token_actual.lexema == "(":
                    tiene_par = True
                    self.avanzar()
                nodo.agregar_hijo(self.expresion())
                if tiene_par:
                    self.coincidir("SIMBOLO", ")")
                if self.token_actual and self.token_actual.lexema == ";":
                    self.avanzar()
            else:
                self.coincidir("RESERVADA", "while")
                self.coincidir("SIMBOLO", "(")
                nodo.agregar_hijo(self.expresion())
                self.coincidir("SIMBOLO", ")")
                self.coincidir("SIMBOLO", ";")
        else:
            nodo.agregar_hijo(self.lista_sentencias(delimitadores=["until", "}"]))
            if self.token_actual and self.token_actual.lexema == "until":
                self.avanzar()
                tiene_par = False
                if self.token_actual and self.token_actual.lexema == "(":
                    tiene_par = True
                    self.avanzar()
                nodo.agregar_hijo(self.expresion())
                if tiene_par:
                    self.coincidir("SIMBOLO", ")")
                if self.token_actual and self.token_actual.lexema == ";":
                    self.avanzar()
            elif self.token_actual and self.token_actual.lexema == "while":
                self.avanzar()
                tiene_par = False
                if self.token_actual and self.token_actual.lexema == "(":
                    tiene_par = True
                    self.avanzar()
                nodo.agregar_hijo(self.expresion())
                if tiene_par:
                    self.coincidir("SIMBOLO", ")")
                if self.token_actual and self.token_actual.lexema == ";":
                    self.avanzar()
            else:
                self.registrar_error("Se esperaba 'until' o 'while' al final del bloque do")
                
        return nodo

    # sent_in → cin >> id ;
    def sent_in(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Entrada (cin)", "", linea, col)
        self.coincidir("RESERVADA", "cin")
        
        if self.token_actual and self.token_actual.lexema == ">>":
            self.avanzar()
        elif self.token_actual and self.token_actual.lexema == ">":
            self.avanzar()
            if self.token_actual and self.token_actual.lexema == ">":
                self.avanzar()
            else:
                self.registrar_error("Se esperaba '>>' después de 'cin'")
        else:
            self.registrar_error("Se esperaba '>>' después de 'cin'")
            
        if self.token_actual and self.token_actual.tipo == "ID":
            nodo.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna))
            self.avanzar()
            self.coincidir("SIMBOLO", ";")
        else:
            self.registrar_error("Se esperaba un ID después de 'cin >>'")
        return nodo

    # sent_out → cout << salida ;
    def sent_out(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Salida (cout)", "", linea, col)
        self.coincidir("RESERVADA", "cout")
        
        if self.token_actual and self.token_actual.lexema == "<<":
            self.avanzar()
        elif self.token_actual and self.token_actual.lexema == "<":
            self.avanzar()
            if self.token_actual and self.token_actual.lexema == "<":
                self.avanzar()
            else:
                self.registrar_error("Se esperaba '<<' después de 'cout'")
        else:
            self.registrar_error("Se esperaba '<<' después de 'cout'")
            
        nodo.agregar_hijo(self.salida())
        self.coincidir("SIMBOLO", ";")
        return nodo

    # salida → item_salida { << item_salida }
    def salida(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Salida", "", linea, col)

        def parsear_item():
            if self.token_actual and self.token_actual.tipo == "CADENA":
                nodo.agregar_hijo(NodoAST("CADENA", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna))
                self.avanzar()
            else:
                nodo.agregar_hijo(self.expresion())

        parsear_item()

        while self.token_actual and (self.token_actual.lexema in ["<<", "<"]):
            if self.token_actual.lexema == "<<":
                self.avanzar()
            else:
                self.avanzar()
                self.coincidir("RELACIONAL", "<")
            parsear_item()

        return nodo

    # expresion → expr_or
    def expresion(self):
        return self.expresion_or()

    # expr_or → expr_and { || expr_and }
    def expresion_or(self):
        nodo = self.expresion_and()
        
        while self.token_actual and self.token_actual.lexema == "||":
            nodo_op = NodoAST("Operador OR", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            nodo_op.agregar_hijo(nodo)
            self.avanzar()
            nodo_op.agregar_hijo(self.expresion_and())
            nodo = nodo_op
            
        return nodo
    
    # expr_and → expr_relacional { && expr_relacional }
    def expresion_and(self):
        nodo = self.expr_relacional()
        
        while self.token_actual and self.token_actual.lexema == "&&":
            nodo_op = NodoAST("Operador AND", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            nodo_op.agregar_hijo(nodo)
            self.avanzar()
            nodo_op.agregar_hijo(self.expr_relacional())
            nodo = nodo_op
            
        return nodo

    # expr_relacional → expr_simple [ rel_op expr_simple ]
    def expr_relacional(self):
        nodo = self.expresion_simple()
        
        if self.token_actual and self.token_actual.lexema in ["<", "<=", ">", ">=", "==", "!="]:
            nodo_rel = NodoAST("Operador Relacional", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            nodo_rel.agregar_hijo(nodo)
            self.avanzar()
            nodo_rel.agregar_hijo(self.expresion_simple())
            return nodo_rel
            
        return nodo

    # expr_simple → termino { (+ | -) termino }
    def expresion_simple(self):
        nodo = self.termino()
        
        while self.token_actual and self.token_actual.lexema in ["+", "-"]:
            nodo_op = NodoAST(f"Operador Aritmetico '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            nodo_op.agregar_hijo(nodo)
            self.avanzar()
            nodo_op.agregar_hijo(self.termino())
            nodo = nodo_op
            
        return nodo

    # termino → factor_unario { (* | / | %) factor_unario }
    def termino(self):
        nodo = self.factor_unario()
        
        while self.token_actual and self.token_actual.lexema in ["*", "/", "%"]:
            nodo_op = NodoAST(f"Operador Aritmetico '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            nodo_op.agregar_hijo(nodo)
            self.avanzar()
            nodo_op.agregar_hijo(self.factor_unario())
            nodo = nodo_op
            
        return nodo
    
    # factor_unario → - factor_unario | factor
    def factor_unario(self):
        if self.token_actual and self.token_actual.lexema == "-":
            nodo_unario = NodoAST("Menos Unario", "-", self.token_actual.linea, self.token_actual.columna)
            self.avanzar()
            nodo_unario.agregar_hijo(self.factor_unario())
            return nodo_unario
            
        return self.factor()

    # factor → componente [ ^ factor ]
    def factor(self):
        hijo_izq = self.componente()
        
        if self.token_actual and self.token_actual.lexema == "^":
            nodo_op = NodoAST("Operador Potencia", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
            nodo_op.agregar_hijo(hijo_izq)
            self.avanzar()
            nodo_op.agregar_hijo(self.factor()) 
            return nodo_op
            
        return hijo_izq

    # componente → ( expresion ) | número | true | false | id | ++ id | -- id | id ++ | id -- | ! componente
    def componente(self):
        linea = self.token_actual.linea if self.token_actual else 0
        col = self.token_actual.columna if self.token_actual else 0
        nodo = NodoAST("Componente", "", linea, col)
        if not self.token_actual:
            self.registrar_error("Componente inesperado o faltante")
            return nodo

        lexema = self.token_actual.lexema
        tipo = self.token_actual.tipo

        if lexema == "(":
            self.avanzar()
            nodo.agregar_hijo(self.expresion())
            self.coincidir("SIMBOLO", ")")
            
        elif tipo in ["NUM_ENTERO", "NUM_REAL"]:
            nodo.agregar_hijo(NodoAST("Numero", lexema, self.token_actual.linea, self.token_actual.columna))
            self.avanzar()
            
        elif lexema in ["true", "false"]:
            nodo.agregar_hijo(NodoAST("Booleano", lexema, self.token_actual.linea, self.token_actual.columna))
            self.avanzar()
            
        elif lexema in ["++", "--"]:
            nodo_inc = NodoAST(f"Pre-Operador '{lexema}'", lexema, self.token_actual.linea, self.token_actual.columna)
            self.avanzar()
            if self.token_actual and self.token_actual.tipo == "ID":
                nodo_inc.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna))
                self.avanzar()
            else:
                self.registrar_error(f"Se esperaba variable despues de {lexema}")
            nodo.agregar_hijo(nodo_inc)
            
        elif tipo == "ID": 
            nodo_id = NodoAST("ID", lexema, self.token_actual.linea, self.token_actual.columna)
            self.avanzar()
            if self.token_actual and self.token_actual.lexema in ["++", "--"]:
                nodo_inc = NodoAST(f"Post-Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea, self.token_actual.columna)
                nodo_inc.agregar_hijo(nodo_id)
                self.avanzar()
                nodo.agregar_hijo(nodo_inc)
            else:
                nodo.agregar_hijo(nodo_id)
                
        elif lexema == "!": 
            nodo_not = NodoAST("Operador NOT", lexema, self.token_actual.linea, self.token_actual.columna)
            self.avanzar()
            nodo_not.agregar_hijo(self.componente())
            nodo.agregar_hijo(nodo_not)
            
        else:
            self.registrar_error(f"Se esperaba un componente pero se encontró '{lexema}'")
            self.avanzar()
            
        return nodo