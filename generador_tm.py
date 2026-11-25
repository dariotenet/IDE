class EmisorTM:
    """Emisor de instrucciones para la Tiny Machine (code.h / code.c)"""

    # Convenciones de registros de Louden (code.h)
    ac = 0    # Acumulador principal
    ac1 = 1   # Segundo acumulador
    gp = 5    # Global pointer (base de variables en dMem)
    mp = 6    # Memory pointer (tope de memoria para temporales)
    pc = 7    # Program counter

    MAX_LINEA_TM = 115  # tm.c define LINESIZE = 121

    def __init__(self, trace_code=True):
        self.trace_code = trace_code
        self.emit_loc = 0
        self.high_emit_loc = 0
        self.lineas = []

    def _limpiar_comentario(self, comentario):
        if not comentario:
            return ""
        return str(comentario).replace("\n", " ").replace("\r", " ")

    def _agregar_linea(self, texto):
        if len(texto) > self.MAX_LINEA_TM:
            texto = texto[:self.MAX_LINEA_TM - 3] + "..."
        self.lineas.append(texto)

    def emit_comment(self, comentario):
        if self.trace_code:
            limpio = self._limpiar_comentario(comentario)
            self._agregar_linea(f"* {limpio}")

    def emit_ro(self, op, r, s, t, comentario=""):
        linea = f"{self.emit_loc:3d}:  {op:>5s}  {r},{s},{t} "
        if self.trace_code and comentario:
            linea += f"\t{self._limpiar_comentario(comentario)}"
        self._agregar_linea(linea)
        self.emit_loc += 1
        if self.high_emit_loc < self.emit_loc:
            self.high_emit_loc = self.emit_loc

    def emit_rm(self, op, r, d, s, comentario=""):
        linea = f"{self.emit_loc:3d}:  {op:>5s}  {r},{d}({s}) "
        if self.trace_code and comentario:
            linea += f"\t{self._limpiar_comentario(comentario)}"
        self._agregar_linea(linea)
        self.emit_loc += 1
        if self.high_emit_loc < self.emit_loc:
            self.high_emit_loc = self.emit_loc

    def emit_skip(self, how_many):
        i = self.emit_loc
        self.emit_loc += how_many
        if self.high_emit_loc < self.emit_loc:
            self.high_emit_loc = self.emit_loc
        return i

    def emit_backup(self, loc):
        if loc > self.high_emit_loc:
            self.emit_comment("BUG in emitBackup")
        self.emit_loc = loc

    def emit_restore(self):
        self.emit_loc = self.high_emit_loc

    def emit_rm_abs(self, op, r, a, comentario=""):
        desplazamiento_rel = a - (self.emit_loc + 1)
        linea = f"{self.emit_loc:3d}:  {op:>5s}  {r},{desplazamiento_rel}({self.pc}) "
        if self.trace_code and comentario:
            linea += f"\t{self._limpiar_comentario(comentario)}"
        self._agregar_linea(linea)
        self.emit_loc += 1
        if self.high_emit_loc < self.emit_loc:
            self.high_emit_loc = self.emit_loc

    def obtener_codigo(self):
        return "\n".join(self.lineas) + "\n"


class GeneradorTM:
    """Generador de código objeto TM a partir del AST validado (cgen.c)"""

    def __init__(self, trace_code=True):
        self.trace_code = trace_code
        self.emisor = None
        self.tabla_simbolos = None
        self.tmp_offset = 0
        self.advertencias = []

    def generar(self, ast_raiz, tabla_simbolos, nombre_archivo="salida.tm"):
        self.emisor = EmisorTM(trace_code=self.trace_code)
        self.tabla_simbolos = tabla_simbolos
        self.tmp_offset = 0
        self.advertencias = []

        if not ast_raiz:
            return "", ["No hay AST válido para generar código TM."]

        self.emisor.emit_comment("TINY Compilation to TM Code")
        self.emisor.emit_comment(f"File: {nombre_archivo}")

        # Prólogo estándar de la máquina TM
        self.emisor.emit_comment("Standard prelude:")
        self.emisor.emit_rm("LD", self.emisor.mp, 0, self.emisor.ac, "load maxaddress from location 0")
        self.emisor.emit_rm("ST", self.emisor.ac, 0, self.emisor.ac, "clear location 0")
        self.emisor.emit_comment("End of standard prelude.")

        # Recorrido del AST
        self._cgen(ast_raiz)

        # Finalización
        self.emisor.emit_comment("End of execution.")
        self.emisor.emit_ro("HALT", 0, 0, 0, "")

        return self.emisor.obtener_codigo(), self.advertencias

    def _obtener_offset(self, nombre_var):
        if not self.tabla_simbolos:
            return 0
        simbolo = self.tabla_simbolos.buscar(nombre_var)
        if simbolo is not None:
            return simbolo.desplazamiento
        return 0

    def _cgen(self, nodo):
        if not nodo:
            return

        etiqueta = nodo.etiqueta

        if etiqueta == "Programa":
            for hijo in nodo.hijos:
                self._cgen(hijo)
        elif etiqueta == "Lista Declaraciones":
            # Las declaraciones ya reservaron su offset en TablaSimbolos; inicializamos en 0 por seguridad
            for decl in nodo.hijos:
                self._gen_declaracion(decl)
        elif etiqueta == "Lista Sentencias":
            for stmt in nodo.hijos:
                self._gen_stmt(stmt)
        else:
            self._gen_stmt(nodo)

    def _gen_declaracion(self, nodo_decl):
        nodo_ids = None
        for h in nodo_decl.hijos:
            if h.etiqueta == "Identificadores":
                nodo_ids = h
        if not nodo_ids:
            return
        for nodo_id in nodo_ids.hijos:
            if nodo_id.etiqueta == "ID":
                loc = self._obtener_offset(nodo_id.lexema)
                self.emisor.emit_comment(f"decl {nodo_id.lexema} at gp+{loc}")

    def _gen_stmt(self, nodo):
        if not nodo:
            return

        etiqueta = nodo.etiqueta

        if etiqueta == "Instruccion / Asignacion":
            self._gen_assign(nodo)
        elif "Pre-Operador" in etiqueta or "Post-Operador" in etiqueta:
            self._gen_unario_inc_dec(nodo, retornar_previo=False)
        elif etiqueta == "Seleccion (if)":
            self._gen_if(nodo)
        elif etiqueta == "Iteracion (while)":
            self._gen_while(nodo)
        elif etiqueta == "Repeticion (do)":
            self._gen_do(nodo)
        elif etiqueta == "Entrada (cin)":
            self._gen_cin(nodo)
        elif etiqueta == "Salida (cout)":
            self._gen_cout(nodo)
        elif etiqueta == "Lista Sentencias":
            for hijo in nodo.hijos:
                self._gen_stmt(hijo)

    def _gen_assign(self, nodo):
        nodo_id = None
        nodo_expr = None
        for h in nodo.hijos:
            if h.etiqueta == "ID":
                nodo_id = h
            elif h.etiqueta == "Sentencia Expresion":
                nodo_expr = h

        if not nodo_id:
            return

        self.emisor.emit_comment(f"-> assign {nodo_id.lexema}")
        if nodo_expr and nodo_expr.hijos:
            self._gen_exp(nodo_expr.hijos[0])
        loc = self._obtener_offset(nodo_id.lexema)
        self.emisor.emit_rm("ST", self.emisor.ac, loc, self.emisor.gp, f"assign: store {nodo_id.lexema}")
        self.emisor.emit_comment(f"<- assign {nodo_id.lexema}")

    def _gen_unario_inc_dec(self, nodo, retornar_previo=False):
        nodo_id = None
        for h in nodo.hijos:
            if h.etiqueta == "ID":
                nodo_id = h
                break
        if not nodo_id:
            return

        loc = self._obtener_offset(nodo_id.lexema)
        es_incremento = "++" in nodo.lexema
        op_tm = "ADD" if es_incremento else "SUB"

        self.emisor.emit_comment(f"-> unary {nodo.lexema}{nodo_id.lexema}")
        self.emisor.emit_rm("LD", self.emisor.ac, loc, self.emisor.gp, f"load {nodo_id.lexema}")

        if retornar_previo:
            # Post-incremento en expresión: guardar valor anterior en pila temporal
            tmp_prev = self.tmp_offset
            self.tmp_offset -= 1
            self.emisor.emit_rm("ST", self.emisor.ac, tmp_prev, self.emisor.mp, "post-op: save old value")

        self.emisor.emit_rm("LDC", self.emisor.ac1, 1, 0, "load 1")
        self.emisor.emit_ro(op_tm, self.emisor.ac, self.emisor.ac, self.emisor.ac1, f"{nodo_id.lexema} {nodo.lexema}")
        self.emisor.emit_rm("ST", self.emisor.ac, loc, self.emisor.gp, f"store updated {nodo_id.lexema}")

        if retornar_previo:
            self.tmp_offset += 1
            self.emisor.emit_rm("LD", self.emisor.ac, self.tmp_offset, self.emisor.mp, "post-op: restore old value")

        self.emisor.emit_comment(f"<- unary {nodo.lexema}{nodo_id.lexema}")

    def _gen_if(self, nodo):
        if len(nodo.hijos) < 2:
            return

        self.emisor.emit_comment("-> if")
        cond = nodo.hijos[0]
        then_branch = nodo.hijos[1]
        else_branch = nodo.hijos[2] if len(nodo.hijos) > 2 else None

        # Evaluar condición
        self._gen_exp(cond)
        saved_loc1 = self.emisor.emit_skip(1)
        self.emisor.emit_comment("if: jump to else belongs here")

        # Bloque THEN
        self._cgen(then_branch)
        saved_loc2 = self.emisor.emit_skip(1)
        self.emisor.emit_comment("if: jump to end belongs here")

        # Rellenar salto falso hacia ELSE (o fin si no hay else)
        current_loc = self.emisor.emit_skip(0)
        self.emisor.emit_backup(saved_loc1)
        self.emisor.emit_rm_abs("JEQ", self.emisor.ac, current_loc, "if: jmp to else")
        self.emisor.emit_restore()

        # Bloque ELSE (si existe)
        if else_branch:
            for hijo in else_branch.hijos:
                self._cgen(hijo)

        # Rellenar salto incondicional al final del IF
        current_loc = self.emisor.emit_skip(0)
        self.emisor.emit_backup(saved_loc2)
        self.emisor.emit_rm_abs("LDA", self.emisor.pc, current_loc, "jmp to end")
        self.emisor.emit_restore()
        self.emisor.emit_comment("<- if")

    def _gen_while(self, nodo):
        if len(nodo.hijos) < 2:
            return

        self.emisor.emit_comment("-> while")
        cond = nodo.hijos[0]
        body = nodo.hijos[1]

        start_loc = self.emisor.emit_skip(0)
        self.emisor.emit_comment("while: condition check")
        self._gen_exp(cond)

        saved_exit_jmp = self.emisor.emit_skip(1)
        self.emisor.emit_comment("while: jump to end belongs here")

        # Cuerpo del ciclo
        self._cgen(body)
        self.emisor.emit_rm_abs("LDA", self.emisor.pc, start_loc, "while: jmp back to cond")

        # Rellenar salida cuando condición == 0 (falsa)
        end_loc = self.emisor.emit_skip(0)
        self.emisor.emit_backup(saved_exit_jmp)
        self.emisor.emit_rm_abs("JEQ", self.emisor.ac, end_loc, "while: exit if false")
        self.emisor.emit_restore()
        self.emisor.emit_comment("<- while")

    def _gen_do(self, nodo):
        if len(nodo.hijos) < 2:
            return

        tipo_cierre = nodo.lexema if nodo.lexema in ["until", "while"] else "while"
        self.emisor.emit_comment(f"-> do-{tipo_cierre}")

        body = nodo.hijos[0]
        cond = nodo.hijos[1]

        start_loc = self.emisor.emit_skip(0)
        self.emisor.emit_comment("do: body start")

        # Cuerpo del ciclo
        self._cgen(body)

        # Evaluar condición de cierre
        self._gen_exp(cond)
        if tipo_cierre == "until":
            # Repeat-until: repite mientras condición sea FALSA (ac == 0)
            self.emisor.emit_rm_abs("JEQ", self.emisor.ac, start_loc, "do-until: jmp back if false")
        else:
            # Do-while: repite mientras condición sea VERDADERA (ac != 0)
            self.emisor.emit_rm_abs("JNE", self.emisor.ac, start_loc, "do-while: jmp back if true")

        self.emisor.emit_comment(f"<- do-{tipo_cierre}")

    def _gen_cin(self, nodo):
        for h in nodo.hijos:
            if h.etiqueta == "ID":
                loc = self._obtener_offset(h.lexema)
                simbolo = self.tabla_simbolos.buscar(h.lexema) if self.tabla_simbolos else None
                tipo_var = getattr(h, "dtype", None) or (simbolo.tipo if simbolo else None)
                if tipo_var == "float":
                    self.emisor.emit_ro("INF", self.emisor.ac, 0, 0, f"read float into {h.lexema}")
                else:
                    self.emisor.emit_ro("IN", self.emisor.ac, 0, 0, f"read integer into {h.lexema}")
                self.emisor.emit_rm("ST", self.emisor.ac, loc, self.emisor.gp, f"read: store {h.lexema}")

    def _gen_cout(self, nodo):
        for h in nodo.hijos:
            if h.etiqueta == "Salida":
                for item in h.hijos:
                    if item.etiqueta == "CADENA":
                        self.emisor.emit_comment(f"cout string (TM solo imprime enteros): {item.lexema}")
                        self.advertencias.append(
                            f"Nota TM (L:{item.linea}): las cadenas ({item.lexema}) no se imprimen en TM (solo enteros)."
                        )
                    else:
                        self._gen_exp(item)
                        self.emisor.emit_ro("OUT", self.emisor.ac, 0, 0, "write ac")

    def _gen_exp(self, nodo):
        if not nodo:
            return

        etiqueta = nodo.etiqueta

        if etiqueta == "Componente":
            if nodo.hijos:
                self._gen_exp(nodo.hijos[0])
            return

        if etiqueta == "Numero":
            self.emisor.emit_comment("-> Const")
            if "." in nodo.lexema:
                val_float = float(nodo.lexema)
                self.emisor.emit_rm("LDCF", self.emisor.ac, val_float, 0, f"load float const {val_float}")
            else:
                val_int = int(nodo.lexema)
                self.emisor.emit_rm("LDC", self.emisor.ac, val_int, 0, f"load const {val_int}")
            self.emisor.emit_comment("<- Const")
            return

        if etiqueta == "Booleano":
            self.emisor.emit_comment("-> Bool")
            val_bool = 1 if nodo.lexema == "true" else 0
            self.emisor.emit_rm("LDC", self.emisor.ac, val_bool, 0, f"load bool {nodo.lexema}")
            self.emisor.emit_comment("<- Bool")
            return

        if etiqueta == "ID":
            self.emisor.emit_comment("-> Id")
            loc = self._obtener_offset(nodo.lexema)
            self.emisor.emit_rm("LD", self.emisor.ac, loc, self.emisor.gp, f"load id {nodo.lexema}")
            self.emisor.emit_comment("<- Id")
            return

        if "Pre-Operador" in etiqueta:
            self._gen_unario_inc_dec(nodo, retornar_previo=False)
            return

        if "Post-Operador" in etiqueta:
            self._gen_unario_inc_dec(nodo, retornar_previo=True)
            return

        if etiqueta == "Menos Unario":
            if nodo.hijos:
                self.emisor.emit_comment("-> Unary Minus")
                self._gen_exp(nodo.hijos[0])
                self.emisor.emit_rm("ST", self.emisor.ac, self.tmp_offset, self.emisor.mp, "neg: push operand")
                self.tmp_offset -= 1
                self.emisor.emit_rm("LDC", self.emisor.ac, 0, 0, "load 0")
                self.tmp_offset += 1
                self.emisor.emit_rm("LD", self.emisor.ac1, self.tmp_offset, self.emisor.mp, "neg: load operand")
                self.emisor.emit_ro("SUB", self.emisor.ac, self.emisor.ac, self.emisor.ac1, "0 - operand")
                self.emisor.emit_comment("<- Unary Minus")
            return

        if etiqueta == "Operador NOT":
            if nodo.hijos:
                self.emisor.emit_comment("-> NOT")
                self._gen_exp(nodo.hijos[0])
                self.emisor.emit_rm_abs("JEQ", self.emisor.ac, self.emisor.emit_loc + 3, "if 0 -> true")
                self.emisor.emit_rm("LDC", self.emisor.ac, 0, 0, "false case")
                self.emisor.emit_rm_abs("LDA", self.emisor.pc, self.emisor.emit_loc + 2, "unconditional jmp")
                self.emisor.emit_rm("LDC", self.emisor.ac, 1, 0, "true case")
                self.emisor.emit_comment("<- NOT")
            return

        if etiqueta == "Operador Potencia" and len(nodo.hijos) >= 2:
            self._gen_potencia(nodo.hijos[0], nodo.hijos[1])
            return

        if "Operador Aritmetico" in etiqueta and len(nodo.hijos) >= 2:
            self._gen_aritmetico(nodo.lexema, nodo.hijos[0], nodo.hijos[1])
            return

        if etiqueta == "Operador Relacional" and len(nodo.hijos) >= 2:
            self._gen_relacional(nodo.lexema, nodo.hijos[0], nodo.hijos[1])
            return

        if etiqueta in ["Operador AND", "Operador OR"] and len(nodo.hijos) >= 2:
            self._gen_logico(nodo.lexema, nodo.hijos[0], nodo.hijos[1])
            return

        for h in nodo.hijos:
            self._gen_exp(h)

    def _gen_aritmetico(self, op, izq, der):
        self.emisor.emit_comment(f"-> Op {op}")
        if op == "%":
            # Módulo entero: a % b = a - (a / b) * b
            self._gen_exp(izq)
            tmp_a = self.tmp_offset
            self.tmp_offset -= 1
            self.emisor.emit_rm("ST", self.emisor.ac, tmp_a, self.emisor.mp, "mod: push left (a)")

            self._gen_exp(der)
            tmp_b = self.tmp_offset
            self.tmp_offset -= 1
            self.emisor.emit_rm("ST", self.emisor.ac, tmp_b, self.emisor.mp, "mod: push right (b)")

            self.emisor.emit_rm("LD", self.emisor.ac1, tmp_a, self.emisor.mp, "mod: load a")
            self.emisor.emit_ro("DIV", self.emisor.ac, self.emisor.ac1, self.emisor.ac, "a / b")
            self.emisor.emit_rm("LD", self.emisor.ac1, tmp_b, self.emisor.mp, "mod: load b")
            self.emisor.emit_ro("MUL", self.emisor.ac, self.emisor.ac1, self.emisor.ac, "b * (a / b)")
            self.emisor.emit_rm("LD", self.emisor.ac1, tmp_a, self.emisor.mp, "mod: reload a")
            self.emisor.emit_ro("SUB", self.emisor.ac, self.emisor.ac1, self.emisor.ac, "a - (a / b) * b")

            self.tmp_offset += 2
            self.emisor.emit_comment("<- Op %")
            return

        self._gen_exp(izq)
        self.emisor.emit_rm("ST", self.emisor.ac, self.tmp_offset, self.emisor.mp, "op: push left")
        self.tmp_offset -= 1

        self._gen_exp(der)
        self.tmp_offset += 1
        self.emisor.emit_rm("LD", self.emisor.ac1, self.tmp_offset, self.emisor.mp, "op: load left")

        mapa_ops = {
            "+": ("ADD", "op +"),
            "-": ("SUB", "op -"),
            "*": ("MUL", "op *"),
            "/": ("DIV", "op /"),
        }
        instruccion, desc = mapa_ops.get(op, ("ADD", "op ?"))
        self.emisor.emit_ro(instruccion, self.emisor.ac, self.emisor.ac1, self.emisor.ac, desc)
        self.emisor.emit_comment(f"<- Op {op}")

    def _gen_potencia(self, izq, der):
        self.emisor.emit_comment("-> Op ^ (power)")
        self._gen_exp(izq)
        tmp_base = self.tmp_offset
        self.tmp_offset -= 1
        self.emisor.emit_rm("ST", self.emisor.ac, tmp_base, self.emisor.mp, "pow: push base")

        self._gen_exp(der)
        tmp_exp = self.tmp_offset
        self.tmp_offset -= 1
        self.emisor.emit_rm("ST", self.emisor.ac, tmp_exp, self.emisor.mp, "pow: push exp")

        tmp_res = self.tmp_offset
        self.tmp_offset -= 1

        self.emisor.emit_rm("LDC", self.emisor.ac, 1, 0, "pow: init result = 1")
        loop_start = self.emisor.emit_skip(0)
        self.emisor.emit_rm("LD", self.emisor.ac1, tmp_exp, self.emisor.mp, "pow: load exp")
        saved_end = self.emisor.emit_skip(1)

        self.emisor.emit_rm("LD", self.emisor.ac1, tmp_base, self.emisor.mp, "pow: load base")
        self.emisor.emit_ro("MUL", self.emisor.ac, self.emisor.ac, self.emisor.ac1, "pow: result *= base")
        self.emisor.emit_rm("ST", self.emisor.ac, tmp_res, self.emisor.mp, "pow: save result")

        self.emisor.emit_rm("LD", self.emisor.ac, tmp_exp, self.emisor.mp, "pow: load exp")
        self.emisor.emit_rm("LDC", self.emisor.ac1, 1, 0, "load 1")
        self.emisor.emit_ro("SUB", self.emisor.ac, self.emisor.ac, self.emisor.ac1, "pow: exp--")
        self.emisor.emit_rm("ST", self.emisor.ac, tmp_exp, self.emisor.mp, "pow: save exp")

        self.emisor.emit_rm("LD", self.emisor.ac, tmp_res, self.emisor.mp, "pow: reload result")
        self.emisor.emit_rm_abs("LDA", self.emisor.pc, loop_start, "pow: loop back")

        end_loc = self.emisor.emit_skip(0)
        self.emisor.emit_backup(saved_end)
        self.emisor.emit_rm_abs("JLE", self.emisor.ac1, end_loc, "pow: exit if exp <= 0")
        self.emisor.emit_restore()

        self.tmp_offset += 3
        self.emisor.emit_comment("<- Op ^")

    def _gen_relacional(self, op, izq, der):
        self.emisor.emit_comment(f"-> Rel {op}")
        self._gen_exp(izq)
        self.emisor.emit_rm("ST", self.emisor.ac, self.tmp_offset, self.emisor.mp, "rel: push left")
        self.tmp_offset -= 1

        self._gen_exp(der)
        self.tmp_offset += 1
        self.emisor.emit_rm("LD", self.emisor.ac1, self.tmp_offset, self.emisor.mp, "rel: load left")

        self.emisor.emit_ro("SUB", self.emisor.ac, self.emisor.ac1, self.emisor.ac, f"op {op}")
        saltos = {
            "<": "JLT",
            "<=": "JLE",
            ">": "JGT",
            ">=": "JGE",
            "==": "JEQ",
            "!=": "JNE",
        }
        salto = saltos.get(op, "JEQ")
        self.emisor.emit_rm(salto, self.emisor.ac, 2, self.emisor.pc, "br if true")
        self.emisor.emit_rm("LDC", self.emisor.ac, 0, 0, "false case")
        self.emisor.emit_rm("LDA", self.emisor.pc, 1, self.emisor.pc, "unconditional jmp")
        self.emisor.emit_rm("LDC", self.emisor.ac, 1, 0, "true case")
        self.emisor.emit_comment(f"<- Rel {op}")

    def _gen_logico(self, op, izq, der):
        self.emisor.emit_comment(f"-> Logic {op}")
        if op == "&&":
            self._gen_exp(izq)
            jmp_false1 = self.emisor.emit_skip(1)
            self._gen_exp(der)
            jmp_false2 = self.emisor.emit_skip(1)

            self.emisor.emit_rm("LDC", self.emisor.ac, 1, 0, "and: true case")
            jmp_end = self.emisor.emit_skip(1)

            false_loc = self.emisor.emit_skip(0)
            self.emisor.emit_backup(jmp_false1)
            self.emisor.emit_rm_abs("JEQ", self.emisor.ac, false_loc, "and: short-circuit false")
            self.emisor.emit_backup(jmp_false2)
            self.emisor.emit_rm_abs("JEQ", self.emisor.ac, false_loc, "and: right false")
            self.emisor.emit_restore()

            self.emisor.emit_rm("LDC", self.emisor.ac, 0, 0, "and: false case")
            end_loc = self.emisor.emit_skip(0)
            self.emisor.emit_backup(jmp_end)
            self.emisor.emit_rm_abs("LDA", self.emisor.pc, end_loc, "and: jmp end")
            self.emisor.emit_restore()
        else:  # "||"
            self._gen_exp(izq)
            jmp_true1 = self.emisor.emit_skip(1)
            self._gen_exp(der)
            jmp_true2 = self.emisor.emit_skip(1)

            self.emisor.emit_rm("LDC", self.emisor.ac, 0, 0, "or: false case")
            jmp_end = self.emisor.emit_skip(1)

            true_loc = self.emisor.emit_skip(0)
            self.emisor.emit_backup(jmp_true1)
            self.emisor.emit_rm_abs("JNE", self.emisor.ac, true_loc, "or: short-circuit true")
            self.emisor.emit_backup(jmp_true2)
            self.emisor.emit_rm_abs("JNE", self.emisor.ac, true_loc, "or: right true")
            self.emisor.emit_restore()

            self.emisor.emit_rm("LDC", self.emisor.ac, 1, 0, "or: true case")
            end_loc = self.emisor.emit_skip(0)
            self.emisor.emit_backup(jmp_end)
            self.emisor.emit_rm_abs("LDA", self.emisor.pc, end_loc, "or: jmp end")
            self.emisor.emit_restore()
        self.emisor.emit_comment(f"<- Logic {op}")