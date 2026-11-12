"""
Módulo de Generación de Código Intermedio.
Fase 4 del Compilador.

Implementa la representación interna basada en cuádruplos y la generación
de Código de Tres Direcciones (TAC) y Tabla de Cuádruplos a partir del AST anotado.
Apego estricto a las especificaciones de GEMINI.md y arquitectura del compilador.
"""

class Cuadruplo:
    """
    Representa una instrucción cuádrupla de código intermedio:
    (operador, argumento1, argumento2, resultado)
    """
    def __init__(self, op, arg1=None, arg2=None, resultado=None):
        self.op = str(op)
        self.arg1 = str(arg1) if arg1 is not None else "-"
        self.arg2 = str(arg2) if arg2 is not None else "-"
        self.resultado = str(resultado) if resultado is not None else "-"

    def a_tupla(self):
        return (self.op, self.arg1, self.arg2, self.resultado)

    def __repr__(self):
        return f"({self.op}, {self.arg1}, {self.arg2}, {self.resultado})"


class GeneradorCodigoIntermedio:
    """
    Genera cuádruplos y código intermedio de tres direcciones a partir del AST
    y la Tabla de Símbolos decorados en la fase semántica.
    """
    def __init__(self, tabla_simbolos=None):
        self.tabla_simbolos = tabla_simbolos
        self.cuadruplos = []
        self.temp_count = 0
        self.label_count = 0

    def nuevo_temp(self) -> str:
        """Genera un identificador único para una variable temporal (t0, t1, ...)."""
        t = f"t{self.temp_count}"
        self.temp_count += 1
        return t

    def nuevo_temporal(self) -> str:
        """Alias para nuevo_temp()."""
        return self.nuevo_temp()

    def nueva_etiqueta(self) -> str:
        """Genera una etiqueta de salto simbólica única (L0, L1, ...)."""
        lbl = f"L{self.label_count}"
        self.label_count += 1
        return lbl

    def emitir(self, op, arg1=None, arg2=None, resultado=None) -> Cuadruplo:
        """Crea, registra en la lista interna y retorna un nuevo cuádruplo."""
        c = Cuadruplo(op, arg1, arg2, resultado)
        self.cuadruplos.append(c)
        return c

    # =========================================================================
    # RECORRIDO DEL AST Y GENERACIÓN
    # =========================================================================

    def generar(self, ast_raiz) -> list:
        """
        Punto de entrada principal para generar código intermedio desde la raíz del AST.
        Retorna la lista de cuádruplos generados.
        """
        self.cuadruplos.clear()
        self.temp_count = 0
        self.label_count = 0

        if not ast_raiz:
            return self.cuadruplos

        if ast_raiz.etiqueta == "Programa":
            # hijos[0]: Lista Declaraciones, hijos[1]: Lista Sentencias
            if len(ast_raiz.hijos) > 0:
                self.generar_declaraciones(ast_raiz.hijos[0])
            if len(ast_raiz.hijos) > 1:
                self.generar_sentencias(ast_raiz.hijos[1])
        elif ast_raiz.etiqueta == "Lista Sentencias":
            self.generar_sentencias(ast_raiz)
        else:
            self.generar_sentencias(ast_raiz)

        return self.cuadruplos

    def generar_declaraciones(self, nodo):
        """
        Procesa declaraciones de variables.
        En TAC estándar las declaraciones estáticas no generan cuádruplos ejecutables,
        pues el espacio y tipo ya han sido determinados por la Tabla de Símbolos.
        """
        pass

    def generar_sentencias(self, nodo):
        """
        Recorre secuencialmente una lista de sentencias o despacha una sentencia individual.
        """
        if not nodo:
            return

        if nodo.etiqueta == "Lista Sentencias":
            for sent in nodo.hijos:
                self.generar_sentencia(sent)
        else:
            self.generar_sentencia(nodo)

    def generar_sentencia(self, nodo):
        """
        Despacha la generación de código para una sentencia específica según su etiqueta.
        """
        if not nodo:
            return

        etiqueta = nodo.etiqueta

        if etiqueta == "Instruccion / Asignacion":
            self.generar_asignacion(nodo)
        elif "Pre-Operador" in etiqueta or "Post-Operador" in etiqueta:
            self.generar_unario_standalone(nodo)
        elif etiqueta == "Entrada (cin)":
            self.generar_cin(nodo)
        elif etiqueta == "Salida (cout)":
            self.generar_cout(nodo)
        elif etiqueta == "Sentencia Expresion":
            if nodo.hijos:
                self.generar_expresion(nodo.hijos[0])
        elif etiqueta == "Seleccion (if)":
            self.generar_seleccion(nodo)
        elif etiqueta == "Iteracion (while)":
            self.generar_while(nodo)
        elif etiqueta == "Repeticion (do)":
            self.generar_do(nodo)
        else:
            for hijo in nodo.hijos:
                self.generar_sentencia(hijo)

    # =========================================================================
    # ASIGNACIÓN, E/S E INCREMENTOS AUTÓNOMOS
    # =========================================================================

    def generar_asignacion(self, nodo):
        """
        Traduce una asignación: id = expresion;
        AST: Instruccion / Asignacion -> [ID, Sentencia Expresion -> [expresion]]
        Emite: destino = origen
        """
        if len(nodo.hijos) < 2:
            return

        nodo_id = nodo.hijos[0]
        nodo_expr_stmt = nodo.hijos[1]
        var_name = nodo_id.lexema

        if nodo_expr_stmt.hijos:
            res_expr = self.generar_expresion(nodo_expr_stmt.hijos[0])
        else:
            res_expr = self.generar_expresion(nodo_expr_stmt)

        self.emitir('=', arg1=res_expr, resultado=var_name)

    def generar_unario_standalone(self, nodo):
        """
        Traduce un operador de incremento o decremento autónomo (x++; o ++x;).
        AST: Pre-Operador '++' / '--' o Post-Operador '++' / '--' -> [ID]
        Emite:
            t_inc = var + 1
            var = t_inc
        """
        if not nodo.hijos:
            return

        var_name = nodo.hijos[0].lexema
        op_arit = '+' if '++' in (nodo.lexema or nodo.etiqueta) else '-'
        t_inc = self.nuevo_temp()
        self.emitir(op_arit, arg1=var_name, arg2='1', resultado=t_inc)
        self.emitir('=', arg1=t_inc, resultado=var_name)

    def generar_cin(self, nodo):
        """
        Traduce una sentencia de entrada: cin >> id;
        AST: Entrada (cin) -> [ID]
        Emite: read id
        """
        if nodo.hijos:
            var_name = nodo.hijos[0].lexema
            self.emitir('read', resultado=var_name)

    def generar_cout(self, nodo):
        """
        Traduce una sentencia de salida: cout << salida;
        AST: Salida (cout) -> [Salida -> [item_1, item_2, ...]]
        Donde cada item es una "CADENA" o una expresión.
        Emite: write expr / write "texto"
        """
        if not nodo.hijos:
            return

        items = nodo.hijos[0].hijos if (nodo.hijos[0].etiqueta == "Salida") else nodo.hijos
        for item in items:
            if item.etiqueta == "CADENA":
                self.emitir('write', resultado=item.lexema)
            else:
                res = self.generar_expresion(item)
                self.emitir('write', resultado=res)

    # =========================================================================
    # ESTRUCTURAS SELECTIVAS Y REPETITIVAS (ETAPA 2)
    # =========================================================================

    def generar_seleccion(self, nodo):
        """
        Traduce una estructura selectiva (if o if-else).
        Soporta bloques con llaves {} y formato then ... else ... end.
        AST: Seleccion (if) -> [condicion, Lista Sentencias (then), (opcional) Else -> [Lista Sentencias]]

        Plantilla TAC:
            [ Evaluar expresion condicional -> tmp_cond ]
            if_false tmp_cond goto L_else  (o L_fin si no hay Else)
            [ Bloque then ]
            goto L_fin                     (solo si hay Else)
        label L_else                       (solo si hay Else)
            [ Bloque else ]
        label L_fin
        """
        if len(nodo.hijos) < 2:
            return

        t_cond = self.generar_expresion(nodo.hijos[0])
        l_else = self.nueva_etiqueta()
        l_fin = self.nueva_etiqueta()
        tiene_else = len(nodo.hijos) > 2 and nodo.hijos[2].etiqueta == "Else"

        self.emitir('if_false', arg1=t_cond, resultado=l_else if tiene_else else l_fin)
        self.generar_sentencias(nodo.hijos[1])

        if tiene_else:
            self.emitir('goto', resultado=l_fin)
            self.emitir('label', arg1=l_else)
            for hijo_else in nodo.hijos[2].hijos:
                self.generar_sentencias(hijo_else)
            self.emitir('label', arg1=l_fin)
        else:
            self.emitir('label', arg1=l_fin)

    def generar_while(self, nodo):
        """
        Traduce una estructura iterativa (while).
        Soporta sintaxis con llaves {} y sintaxis while cond sentencias end.
        AST: Iteracion (while) -> [condicion, Lista Sentencias]

        Plantilla TAC:
        label L_inicio
            [ Evaluar expresion condicional -> tmp_cond ]
            if_false tmp_cond goto L_fin
            [ Bloque cuerpo ]
            goto L_inicio
        label L_fin
        """
        if len(nodo.hijos) < 2:
            return

        l_inicio = self.nueva_etiqueta()
        l_fin = self.nueva_etiqueta()

        self.emitir('label', arg1=l_inicio)
        t_cond = self.generar_expresion(nodo.hijos[0])
        self.emitir('if_false', arg1=t_cond, resultado=l_fin)
        self.generar_sentencias(nodo.hijos[1])
        self.emitir('goto', resultado=l_inicio)
        self.emitir('label', arg1=l_fin)

    def generar_do(self, nodo):
        """
        Traduce una estructura de repetición (do-while o do-until).
        AST: Repeticion (do) -> [Lista Sentencias, condicion]

        Plantilla TAC:
        label L_inicio
            [ Bloque cuerpo ]
            [ Evaluar expresion condicional -> tmp_cond ]
            if_true tmp_cond goto L_inicio    (do-while tradicional)
            (o if_false si fuera until)
        """
        if len(nodo.hijos) < 2:
            return

        l_inicio = self.nueva_etiqueta()
        self.emitir('label', arg1=l_inicio)
        self.generar_sentencias(nodo.hijos[0])
        t_cond = self.generar_expresion(nodo.hijos[1])

        op_salto = 'if_false' if getattr(nodo, 'lexema', '') == 'until' else 'if_true'
        self.emitir(op_salto, arg1=t_cond, resultado=l_inicio)

    # =========================================================================
    # EVALUACIÓN DE EXPRESIONES (POSTORDEN RECURSIVO)
    # =========================================================================

    def generar_expresion(self, nodo) -> str:
        """
        Recorre en postorden recursivo el subárbol de una expresión.
        Emite los cuádruplos de cálculo intermedio y retorna el identificador
        o literal que almacena el resultado.
        """
        if not nodo:
            return ""

        etiqueta = nodo.etiqueta
        lexema = nodo.lexema

        # --- Terminales / Hojas ---
        if etiqueta == "Numero":
            return lexema

        if etiqueta == "Booleano":
            return "1" if lexema == "true" else "0"

        if etiqueta == "ID":
            return lexema

        if etiqueta == "CADENA":
            return lexema

        # --- Contenedor Componente ---
        if etiqueta == "Componente":
            if nodo.hijos:
                return self.generar_expresion(nodo.hijos[0])
            return ""

        # --- Menos Unario (- factor) ---
        if etiqueta == "Menos Unario":
            val = self.generar_expresion(nodo.hijos[0])
            t = self.nuevo_temp()
            self.emitir('uminus', arg1=val, resultado=t)
            return t

        # --- Negación Lógica (! componente) ---
        if etiqueta == "Operador NOT":
            val = self.generar_expresion(nodo.hijos[0])
            t = self.nuevo_temp()
            self.emitir('!', arg1=val, resultado=t)
            return t

        # --- Incremento / Decremento dentro de expresión ---
        if "Pre-Operador" in etiqueta:
            var_name = nodo.hijos[0].lexema
            op_arit = '+' if '++' in (lexema or etiqueta) else '-'
            t_inc = self.nuevo_temp()
            self.emitir(op_arit, arg1=var_name, arg2='1', resultado=t_inc)
            self.emitir('=', arg1=t_inc, resultado=var_name)
            return var_name

        if "Post-Operador" in etiqueta:
            var_name = nodo.hijos[0].lexema
            op_arit = '+' if '++' in (lexema or etiqueta) else '-'
            t_old = self.nuevo_temp()
            self.emitir('=', arg1=var_name, resultado=t_old)
            t_inc = self.nuevo_temp()
            self.emitir(op_arit, arg1=var_name, arg2='1', resultado=t_inc)
            self.emitir('=', arg1=t_inc, resultado=var_name)
            return t_old

        # --- Operaciones Binarias con 2 hijos ---
        if len(nodo.hijos) >= 2:
            izq = self.generar_expresion(nodo.hijos[0])
            der = self.generar_expresion(nodo.hijos[1])

            # Operador Potencia
            if etiqueta == "Operador Potencia" or lexema == "^":
                t = self.nuevo_temp()
                self.emitir('^', arg1=izq, arg2=der, resultado=t)
                return t

            # Operadores Aritméticos (+, -, *, /, %)
            if etiqueta.startswith("Operador Aritmetico") or lexema in ('+', '-', '*', '/', '%'):
                t = self.nuevo_temp()
                self.emitir(lexema, arg1=izq, arg2=der, resultado=t)
                return t

            # Operadores Relacionales (<, <=, >, >=, ==, !=)
            if etiqueta == "Operador Relacional" or lexema in ('<', '<=', '>', '>=', '==', '!='):
                t = self.nuevo_temp()
                self.emitir(lexema, arg1=izq, arg2=der, resultado=t)
                return t

            # Operadores Lógicos (&&, ||)
            if etiqueta in ("Operador AND", "Operador OR") or lexema in ('&&', '||'):
                t = self.nuevo_temp()
                self.emitir(lexema, arg1=izq, arg2=der, resultado=t)
                return t

        # Caso base recursivo de un solo hijo no previsto
        if len(nodo.hijos) == 1:
            return self.generar_expresion(nodo.hijos[0])

        return lexema or ""

    # =========================================================================
    # RENDERIZADO VISUAL (TAC Y TABLA DE CUÁDRUPLOS)
    # =========================================================================

    def a_tres_direcciones(self) -> str:
        """
        Convierte la lista interna de cuádruplos a sintaxis estándar
        de Código de Tres Direcciones (TAC).
        """
        lineas = []
        for c in self.cuadruplos:
            if c.op in ('+', '-', '*', '/', '%', '^', '<', '<=', '>', '>=', '==', '!='):
                lineas.append(f"{c.resultado} = {c.arg1} {c.op} {c.arg2}")
            elif c.op in ('&&', '||'):
                lineas.append(f"{c.resultado} = {c.arg1} {c.op} {c.arg2}")
            elif c.op == '=':
                lineas.append(f"{c.resultado} = {c.arg1}")
            elif c.op == 'uminus':
                lineas.append(f"{c.resultado} = -{c.arg1}")
            elif c.op == '!':
                lineas.append(f"{c.resultado} = !{c.arg1}")
            elif c.op == 'if_false':
                lineas.append(f"if_false {c.arg1} goto {c.resultado}")
            elif c.op == 'if_true':
                lineas.append(f"if_true {c.arg1} goto {c.resultado}")
            elif c.op == 'goto':
                lineas.append(f"goto {c.resultado}")
            elif c.op == 'label':
                lineas.append(f"label {c.arg1}")
            elif c.op == 'read':
                lineas.append(f"read {c.resultado}")
            elif c.op == 'write':
                lineas.append(f"write {c.resultado}")
            else:
                lineas.append(f"{c.op} {c.arg1} {c.arg2} {c.resultado}")
        return "\n".join(lineas)

    def a_tabla_cuadruplos(self) -> str:
        """
        Formatea los cuádruplos como tabla con columnas alineadas
        (Índice, Op, Arg1, Arg2, Resultado).
        """
        encabezado = f"{'#':<4} | {'OP':<12} | {'ARG1':<15} | {'ARG2':<15} | {'RESULTADO':<15}"
        separador = "-" * len(encabezado)
        lineas = [encabezado, separador]
        for idx, c in enumerate(self.cuadruplos):
            lineas.append(f"{idx:<4} | {c.op:<12} | {c.arg1:<15} | {c.arg2:<15} | {c.resultado:<15}")
        return "\n".join(lineas)
