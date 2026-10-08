class NodoAST:
    def __init__(self, etiqueta, lexema="", linea=0):
        self.etiqueta = etiqueta
        self.lexema = lexema
        self.linea = linea
        self.hijos = []

    def agregar_hijo(self, nodo):
        if nodo:
            self.hijos.append(nodo)

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
        nodo = NodoAST("Programa")
        if self.coincidir("RESERVADA", "main"):
            if self.coincidir("SIMBOLO", "{"):
                nodo.agregar_hijo(self.lista_declaracion())
                nodo.agregar_hijo(self.lista_sentencias()) # agregado como hermano
                self.coincidir("SIMBOLO", "}")
        return nodo

    # lista_declaraciones → declaracion_variable lista_declaraciones | ε
    def lista_declaracion(self):
        nodo = NodoAST("Lista Declaraciones")
        
        # Solo iteramos si el token es un tipo de dato
        while self.token_actual and self.token_actual.lexema in ["int", "float", "bool"]:
            hijo = self.declaracion_variable()
            if hijo:
                nodo.agregar_hijo(hijo)
                
        return nodo

    # declaracion_variable → tipo identificador ;
    def declaracion_variable(self):
        nodo = NodoAST("Declaracion Variable")
        nodo.agregar_hijo(self.tipo())
        nodo.agregar_hijo(self.identificador())
        self.coincidir("SIMBOLO", ";")
        return nodo

    # identificador → id { , id }
    def identificador(self):
        nodo = NodoAST("Identificadores")
        if self.token_actual and self.token_actual.tipo == "ID":
            nodo.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea))
            self.avanzar()
            while self.token_actual and self.token_actual.lexema == ",":
                self.avanzar() # consumir ','
                if self.token_actual and self.token_actual.tipo == "ID":
                    nodo.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea))
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
            nodo = NodoAST("Tipo", self.token_actual.lexema, self.token_actual.linea)
            self.avanzar()
            return nodo
        self.registrar_error("Se esperaba tipo (int, float, bool)")
        return None

    # lista_sentencias → { sentencia }
    # lista_sentencias → { sentencia }
    def lista_sentencias(self):
        nodo = NodoAST("Lista Sentencias")
        primeros_sentencia = ["if", "while", "do", "cin", "cout", "++", "--"]
        
        # obligar al bucle a seguir tragando tokens hasta topar con '}'
        while self.token_actual and self.token_actual.lexema != "}":
            
            # si el token es un inicio válido de sentencia...
            if self.token_actual.lexema in primeros_sentencia or self.token_actual.tipo == "ID":
                pos_inicial = self.pos # barrera anti-crash
                
                hijo = self.sentencia()
                if hijo:
                    nodo.agregar_hijo(hijo)
                    
                if self.pos == pos_inicial:
                    self.registrar_error(f"Sentencia no reconocida cerca de '{self.token_actual.lexema}'")
                    self.avanzar()
            else:
                # si hay basura léxica reportar y consumir
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
        # Si es un ID o empieza con un incremento (++ / --), vamos a asignacion
        elif self.token_actual.tipo == "ID" or lexema in ["++", "--"]: return self.asignacion()
        return None

    # asignacion → id = expresion ; | id ++ ; | id -- ; | ++ id ; | -- id ;
    def asignacion(self):
        nodo = NodoAST("Instruccion / Asignacion")

        # caso pre-incremento standalone (ej. ++x;)
        if self.token_actual.lexema in ["++", "--"]:
            nodo_inc = NodoAST(f"Pre-Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea)
            self.avanzar()
            if self.token_actual and self.token_actual.tipo == "ID":
                nodo_inc.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea))
                self.avanzar()
                self.coincidir("SIMBOLO", ";")
                return nodo_inc

        # caso ID normal
        elif self.token_actual.tipo == "ID":
            nodo_id = NodoAST("ID", self.token_actual.lexema, self.token_actual.linea)
            self.avanzar()

            # caso post-incremento standalone (ej. x++;)
            if self.token_actual and self.token_actual.lexema in ["++", "--"]:
                nodo_inc = NodoAST(f"Post-Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea)
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
        nodo = NodoAST("Sentencia Expresion")
        # ya no hay caso vacio 'id = ;', obligar a que haya una expresion
        nodo.agregar_hijo(self.expresion())
        self.coincidir("SIMBOLO", ";")
        return nodo

    # seleccion → if ( expresion ) { lista_sentencias } [ else { lista_sentencias } ]
    def seleccion(self):
        nodo = NodoAST("Seleccion (if)")
        self.coincidir("RESERVADA", "if")
        
        # expresión entre paréntesis
        self.coincidir("SIMBOLO", "(")
        nodo.agregar_hijo(self.expresion())
        self.coincidir("SIMBOLO", ")")
        
        # bloque if entre llaves
        self.coincidir("SIMBOLO", "{")
        nodo.agregar_hijo(self.lista_sentencias())
        self.coincidir("SIMBOLO", "}")
        
        # bloque else opcional
        if self.token_actual and self.token_actual.lexema == "else":
            nodo_else = NodoAST("Else")
            self.avanzar()
            self.coincidir("SIMBOLO", "{")
            nodo_else.agregar_hijo(self.lista_sentencias())
            self.coincidir("SIMBOLO", "}")
            nodo.agregar_hijo(nodo_else)
            
        return nodo

    # iteracion → while ( expresion ) { lista_sentencias }
    def iteracion(self):
        nodo = NodoAST("Iteracion (while)")
        self.coincidir("RESERVADA", "while")
        
        # expresión entre paréntesis
        self.coincidir("SIMBOLO", "(")
        nodo.agregar_hijo(self.expresion())
        self.coincidir("SIMBOLO", ")")
        
        # bloque while entre llaves
        self.coincidir("SIMBOLO", "{")
        nodo.agregar_hijo(self.lista_sentencias())
        self.coincidir("SIMBOLO", "}")
        
        return nodo

    # repeticion → do { lista_sentencias } while ( expresion ) ;
    def repeticion(self):
        nodo = NodoAST("Repeticion (do-while)")
        self.coincidir("RESERVADA", "do")
        
        # bloque do entre llaves
        self.coincidir("SIMBOLO", "{")
        nodo.agregar_hijo(self.lista_sentencias())
        self.coincidir("SIMBOLO", "}")
        
        # condición while al final
        self.coincidir("RESERVADA", "while")
        self.coincidir("SIMBOLO", "(")
        nodo.agregar_hijo(self.expresion())
        self.coincidir("SIMBOLO", ")")
        self.coincidir("SIMBOLO", ";") # obligar punto y coma final
        
        return nodo

    # sent_in → cin >> id ;
    def sent_in(self):
        nodo = NodoAST("Entrada (cin)")
        self.coincidir("RESERVADA", "cin")
        if self.coincidir("RELACIONAL", ">") and self.coincidir("RELACIONAL", ">"):
            if self.token_actual and self.token_actual.tipo == "ID":
                nodo.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea))
                self.avanzar()
                self.coincidir("SIMBOLO", ";")
        return nodo

    # sent_out → cout << salida ;
    def sent_out(self):
        nodo = NodoAST("Salida (cout)")
        self.coincidir("RESERVADA", "cout")
        if self.coincidir("RELACIONAL", "<") and self.coincidir("RELACIONAL", "<"):
            nodo.agregar_hijo(self.salida())
            
            self.coincidir("SIMBOLO", ";")
                
        return nodo

    # salida → item_salida { << item_salida }   (donde item_salida es cadena | expresion)
    def salida(self):
        nodo = NodoAST("Salida")

        def parsear_item():
            if self.token_actual and self.token_actual.tipo == "CADENA":
                nodo.agregar_hijo(NodoAST("CADENA", self.token_actual.lexema, self.token_actual.linea))
                self.avanzar()
            else:
                nodo.agregar_hijo(self.expresion())

        parsear_item() # analizamos primer elemento

        # permitir encadenar elementos infinitamente
        while self.token_actual and self.token_actual.lexema == "<":
            self.avanzar()
            self.coincidir("RELACIONAL", "<")
            parsear_item()

        return nodo

    # expresion → expr_or
    def expresion(self):
        return self.expresion_or()

    # expr_or → expr_and { || expr_and }
    # nivel 1: lógico OR (||)
    def expresion_or(self):
        nodo = self.expresion_and()
        
        while self.token_actual and self.token_actual.lexema == "||":
            nodo_op = NodoAST("Operador OR", self.token_actual.lexema, self.token_actual.linea)
            nodo_op.agregar_hijo(nodo) # el árbol acumulado pasa a ser el hijo izquierdo
            self.avanzar()
            nodo_op.agregar_hijo(self.expresion_and()) # el nuevo valor es el hijo derecho
            nodo = nodo_op # el operador se convierte en la nueva raíz
            
        return nodo
    
    # expr_and → expr_relacional { && expr_relacional }
    # nivel 2: lógico AND (&&) - mayor precedencia que OR
    def expresion_and(self):
        nodo = self.expresion_relacional()
        
        while self.token_actual and self.token_actual.lexema == "&&":
            nodo_op = NodoAST("Operador AND", self.token_actual.lexema, self.token_actual.linea)
            nodo_op.agregar_hijo(nodo)
            self.avanzar()
            nodo_op.agregar_hijo(self.expresion_relacional())
            nodo = nodo_op
            
        return nodo

    # expr_relacional → expr_simple [ rel_op expr_simple ]
    # nivel 3: relacionales (<, >, ==)
    def expresion_relacional(self):
        nodo = self.expresion_simple()
        
        if self.token_actual:
            lex = self.token_actual.lexema
            
            # lookahead
            if lex in ["<", ">"]:
                if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].lexema == lex:
                    return nodo # operador doble
                    
            operadores_rel = ["<", "<=", ">", ">=", "==", "!="]
            if lex in operadores_rel:
                nodo_rel = NodoAST("Operador Relacional", lex, self.token_actual.linea)
                nodo_rel.agregar_hijo(nodo)
                self.avanzar()
                nodo_rel.agregar_hijo(self.expresion_simple())
                return nodo_rel
                
        return nodo

    # expr_simple → termino { (+ | -) termino }
    # nivel 4: suma y resta (+, -) - asociativo a la izquierda
    def expresion_simple(self):
        nodo = self.termino()
        
        while self.token_actual and self.token_actual.lexema in ["+", "-"]:
            nodo_op = NodoAST(f"Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea)
            nodo_op.agregar_hijo(nodo)
            self.avanzar()
            nodo_op.agregar_hijo(self.termino())
            nodo = nodo_op
            
        return nodo

    # termino → factor { (* | / | %) factor }
    # nivel 5: multiplicación y división (*, /, %)
    def termino(self):
        nodo = self.factor_unario() # <--- CAMBIO AQUÍ
        
        while self.token_actual and self.token_actual.lexema in ["*", "/", "%"]:
            nodo_op = NodoAST(f"Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea)
            nodo_op.agregar_hijo(nodo)
            self.avanzar()
            nodo_op.agregar_hijo(self.factor_unario()) # <--- CAMBIO AQUÍ
            nodo = nodo_op
            
        return nodo
    
    # factor_unario → - factor_unario | factor
    def factor_unario(self):
        if self.token_actual and self.token_actual.lexema == "-":
            nodo_unario = NodoAST("Menos Unario", "-", self.token_actual.linea)
            self.avanzar()
            nodo_unario.agregar_hijo(self.factor_unario())
            return nodo_unario
            
        return self.factor()

    # factor → componente [ ^ factor ]
    def factor(self):
        hijo_izq = self.componente()
        
        if self.token_actual and self.token_actual.lexema == "^":
            nodo_op = NodoAST("Operador Potencia", self.token_actual.lexema, self.token_actual.linea)
            nodo_op.agregar_hijo(hijo_izq)
            self.avanzar()
            
            nodo_op.agregar_hijo(self.factor()) 
            return nodo_op
            
        return hijo_izq

    # componente → ( expresion ) | número | true | false | id | ++ id | -- id | id ++ | id -- | ! componente
    def componente(self):
        nodo = NodoAST("Componente")
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
            nodo.agregar_hijo(NodoAST("Numero", lexema, self.token_actual.linea))
            self.avanzar()
            
        elif lexema in ["true", "false"]:
            nodo.agregar_hijo(NodoAST("Booleano", lexema, self.token_actual.linea))
            self.avanzar()
            
        elif lexema in ["++", "--"]: # pre-incremento (ej. ++x)
            nodo_inc = NodoAST(f"Pre-Operador '{lexema}'", lexema, self.token_actual.linea)
            self.avanzar()
            if self.token_actual and self.token_actual.tipo == "ID":
                nodo_inc.agregar_hijo(NodoAST("ID", self.token_actual.lexema, self.token_actual.linea))
                self.avanzar()
            else:
                self.registrar_error(f"Se esperaba variable despues de {lexema}")
            nodo.agregar_hijo(nodo_inc)
            
        elif tipo == "ID": 
            nodo_id = NodoAST("ID", lexema, self.token_actual.linea)
            self.avanzar()
            if self.token_actual and self.token_actual.lexema in ["++", "--"]: # post-incremento (ej. x++)
                nodo_inc = NodoAST(f"Post-Operador '{self.token_actual.lexema}'", self.token_actual.lexema, self.token_actual.linea)
                nodo_inc.agregar_hijo(nodo_id)
                self.avanzar()
                nodo.agregar_hijo(nodo_inc)
            else:
                nodo.agregar_hijo(nodo_id)
                
        elif lexema == "!": 
            nodo_not = NodoAST("Operador NOT", lexema, self.token_actual.linea)
            self.avanzar()
            nodo_not.agregar_hijo(self.componente())
            nodo.agregar_hijo(nodo_not)
            
        else:
            self.registrar_error(f"Se esperaba un componente pero se encontró '{lexema}'")
            self.avanzar()
            
        return nodo