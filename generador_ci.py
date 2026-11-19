class GeneradorCodigoIntermedio:
    """Genera código intermedio de tres direcciones (.ci) en recorrido postorden (intermedio.h / intermedio.c)"""

    def __init__(self):
        self.temporal = 0
        self.etiqueta = 0
        self.lineas = []

    def _nuevo_temporal(self):
        self.temporal += 1
        return f"t{self.temporal}"

    def _nueva_etiqueta(self):
        self.etiqueta += 1
        return f"L{self.etiqueta}"

    def generar(self, ast_raiz):
        self.temporal = 0
        self.etiqueta = 0
        self.lineas = [
            "# CODIGO INTERMEDIO DE TRES DIRECCIONES",
            "# Salida didactica generada en paralelo desde el AST validado.",
            "# Los temporales t1, t2... y etiquetas L1, L2... son simbolicos.",
            ""
        ]

        if not ast_raiz:
            return ""

        self._generar_sentencias(ast_raiz)
        self.lineas.append("halt")
        return "\n".join(self.lineas) + "\n"

    def _generar_sentencias(self, nodo):
        if not nodo:
            return

        etiqueta = nodo.etiqueta

        if etiqueta in ["Programa", "Lista Sentencias"]:
            for hijo in nodo.hijos:
                self._generar_sentencias(hijo)
            return

        if etiqueta == "Lista Declaraciones":
            return

        if etiqueta == "Entrada (cin)":
            for h in nodo.hijos:
                if h.etiqueta == "ID":
                    self.lineas.append(f"read {h.lexema}")
            return

        if etiqueta == "Salida (cout)":
            for h in nodo.hijos:
                if h.etiqueta == "Salida":
                    for item in h.hijos:
                        if item.etiqueta == "CADENA":
                            self.lineas.append(f"write {item.lexema}")
                        else:
                            res = self._generar_expresion(item)
                            if res:
                                self.lineas.append(f"write {res}")
            return

        if etiqueta == "Instruccion / Asignacion":
            nodo_id = None
            nodo_expr = None
            for h in nodo.hijos:
                if h.etiqueta == "ID":
                    nodo_id = h
                elif h.etiqueta == "Sentencia Expresion":
                    nodo_expr = h
            if nodo_id and nodo_expr and nodo_expr.hijos:
                res = self._generar_expresion(nodo_expr.hijos[0])
                if res:
                    self.lineas.append(f"{nodo_id.lexema} = {res}")
            return

        if "Pre-Operador" in etiqueta or "Post-Operador" in etiqueta:
            nodo_id = next((h for h in nodo.hijos if h.etiqueta == "ID"), None)
            if nodo_id:
                op = "+" if "++" in nodo.lexema else "-"
                tmp = self._nuevo_temporal()
                self.lineas.append(f"{tmp} = {nodo_id.lexema} {op} 1")
                self.lineas.append(f"{nodo_id.lexema} = {tmp}")
            return

        if etiqueta == "Seleccion (if)":
            if len(nodo.hijos) < 2:
                return
            cond = self._generar_expresion(nodo.hijos[0])
            et1 = self._nueva_etiqueta()
            self.lineas.append(f"if_false {cond} goto {et1}")
            self._generar_sentencias(nodo.hijos[1])

            tiene_else = len(nodo.hijos) > 2
            et2 = None
            if tiene_else:
                et2 = self._nueva_etiqueta()
                self.lineas.append(f"goto {et2}")

            self.lineas.append(f"label {et1}")
            if tiene_else:
                for h in nodo.hijos[2].hijos:
                    self._generar_sentencias(h)
                self.lineas.append(f"label {et2}")
            return

        if etiqueta == "Iteracion (while)":
            if len(nodo.hijos) < 2:
                return
            et_inicio = self._nueva_etiqueta()
            et_fin = self._nueva_etiqueta()
            self.lineas.append(f"label {et_inicio}")
            cond = self._generar_expresion(nodo.hijos[0])
            self.lineas.append(f"if_false {cond} goto {et_fin}")
            self._generar_sentencias(nodo.hijos[1])
            self.lineas.append(f"goto {et_inicio}")
            self.lineas.append(f"label {et_fin}")
            return

        if etiqueta == "Repeticion (do)":
            if len(nodo.hijos) < 2:
                return
            tipo_cierre = nodo.lexema if nodo.lexema in ["until", "while"] else "while"
            et_inicio = self._nueva_etiqueta()
            self.lineas.append(f"label {et_inicio}")
            self._generar_sentencias(nodo.hijos[0])
            cond = self._generar_expresion(nodo.hijos[1])
            if tipo_cierre == "until":
                self.lineas.append(f"if_false {cond} goto {et_inicio}")
            else:
                self.lineas.append(f"if_true {cond} goto {et_inicio}")
            return

    def _generar_expresion(self, nodo):
        if not nodo:
            return None

        etiqueta = nodo.etiqueta

        if etiqueta == "Componente":
            return self._generar_expresion(nodo.hijos[0]) if nodo.hijos else None

        if etiqueta in ["Numero", "Booleano", "ID"]:
            return nodo.lexema

        if "Post-Operador" in etiqueta:
            nodo_id = next((h for h in nodo.hijos if h.etiqueta == "ID"), None)
            if nodo_id:
                op = "+" if "++" in nodo.lexema else "-"
                viejo = self._nuevo_temporal()
                nuevo = self._nuevo_temporal()
                self.lineas.append(f"{viejo} = {nodo_id.lexema}")
                self.lineas.append(f"{nuevo} = {viejo} {op} 1")
                self.lineas.append(f"{nodo_id.lexema} = {nuevo}")
                return viejo
            return None

        if "Pre-Operador" in etiqueta:
            nodo_id = next((h for h in nodo.hijos if h.etiqueta == "ID"), None)
            if nodo_id:
                op = "+" if "++" in nodo.lexema else "-"
                tmp = self._nuevo_temporal()
                self.lineas.append(f"{tmp} = {nodo_id.lexema} {op} 1")
                self.lineas.append(f"{nodo_id.lexema} = {tmp}")
                return nodo_id.lexema
            return None

        if etiqueta == "Menos Unario" and nodo.hijos:
            hijo = self._generar_expresion(nodo.hijos[0])
            tmp = self._nuevo_temporal()
            self.lineas.append(f"{tmp} = -{hijo}")
            return tmp

        if etiqueta == "Operador NOT" and nodo.hijos:
            hijo = self._generar_expresion(nodo.hijos[0])
            tmp = self._nuevo_temporal()
            self.lineas.append(f"{tmp} = !{hijo}")
            return tmp

        if len(nodo.hijos) >= 2 and (
            "Operador Aritmetico" in etiqueta
            or etiqueta in ["Operador Potencia", "Operador Relacional", "Operador AND", "Operador OR"]
        ):
            izq = self._generar_expresion(nodo.hijos[0])
            der = self._generar_expresion(nodo.hijos[1])
            tmp = self._nuevo_temporal()
            self.lineas.append(f"{tmp} = {izq} {nodo.lexema} {der}")
            return tmp

        if nodo.hijos:
            return self._generar_expresion(nodo.hijos[0])
        return None