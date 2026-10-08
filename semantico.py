class Simbolo:
    def __init__(self, nombre, tipo, desplazamiento, linea_declaracion):
        self.nombre = nombre
        self.tipo = tipo
        self.desplazamiento = desplazamiento
        self.linea_declaracion = linea_declaracion
        self.lineas = [linea_declaracion]
        self.valor = None

    def agregar_linea(self, linea):
        if linea not in self.lineas:
            self.lineas.append(linea)

    def __str__(self):
        lineas_str = ", ".join(map(str, sorted(self.lineas)))
        return f"<Simbolo '{self.nombre}': tipo={self.tipo}, offset={self.desplazamiento}, val={self.valor}, lineas=[{lineas_str}]>"


class TablaSimbolos:
    TAMANIOS = {
        'int': 4,
        'float': 8,
        'bool': 1
    }

    def __init__(self):
        self.simbolos = {}
        self.offset_actual = 0
        self.errores = []

    def insertar(self, nombre, tipo, linea, columna=0):
        if nombre in self.simbolos:
            sim_existente = self.simbolos[nombre]
            error = f"Error Semántico en L:{linea} C:{columna} -> Redeclaración del identificador '{nombre}'. Ya fue declarado previamente en la línea {sim_existente.linea_declaracion}."
            if error not in self.errores:
                self.errores.append(error)
            return False, error

        tamanio = self.TAMANIOS.get(tipo, 4)
        simbolo = Simbolo(nombre, tipo, self.offset_actual, linea)
        self.simbolos[nombre] = simbolo
        self.offset_actual += tamanio
        return True, None

    def buscar(self, nombre):
        return self.simbolos.get(nombre, None)

    def registrar_uso(self, nombre, linea):
        simbolo = self.buscar(nombre)
        if simbolo:
            simbolo.agregar_linea(linea)

    def esta_declarado(self, nombre):
        return nombre in self.simbolos

    def obtener_simbolos(self):
        return sorted(self.simbolos.values(), key=lambda s: s.desplazamiento)

    def limpiar(self):
        self.simbolos.clear()
        self.offset_actual = 0
        self.errores.clear()


class TypeSystem:
    TIPOS_NUMERICOS = {'int', 'float'}

    @classmethod
    def operacion_aritmetica(cls, tipo_izq, tipo_der, operador):
        if tipo_izq == 'ERROR' or tipo_der == 'ERROR':
            return 'ERROR', None, None

        if tipo_izq not in cls.TIPOS_NUMERICOS or tipo_der not in cls.TIPOS_NUMERICOS:
            error = f"Operador aritmético '{operador}' no aplicable a tipos '{tipo_izq}' y '{tipo_der}'."
            return 'ERROR', None, error

        if tipo_izq == 'int' and tipo_der == 'int':
            return 'int', None, None

        if tipo_izq == 'float' and tipo_der == 'float':
            return 'float', None, None

        if tipo_izq == 'int' and tipo_der == 'float':
            return 'float', 'izq_int_a_float', None

        if tipo_izq == 'float' and tipo_der == 'int':
            return 'float', 'der_int_a_float', None

        return 'ERROR', None, f"Tipos incompatibles en operación '{operador}': '{tipo_izq}' y '{tipo_der}'."

    @classmethod
    def operacion_relacional(cls, tipo_izq, tipo_der, operador):
        if tipo_izq == 'ERROR' or tipo_der == 'ERROR':
            return 'ERROR', None

        if operador in ['<', '<=', '>', '>=']:
            if tipo_izq in cls.TIPOS_NUMERICOS and tipo_der in cls.TIPOS_NUMERICOS:
                return 'bool', None
            return 'ERROR', f"Operador relacional '{operador}' solo es aplicable a tipos numéricos, no a '{tipo_izq}' y '{tipo_der}'."

        if operador in ['==', '!=']:
            if (tipo_izq in cls.TIPOS_NUMERICOS and tipo_der in cls.TIPOS_NUMERICOS) or (tipo_izq == tipo_der):
                return 'bool', None
            return 'ERROR', f"Operador de igualdad '{operador}' no aplicable entre '{tipo_izq}' y '{tipo_der}'."

        return 'ERROR', f"Operador relacional desconocido '{operador}'."

    @classmethod
    def operacion_logica(cls, tipo_izq, tipo_der, operador):
        if tipo_izq == 'ERROR' or tipo_der == 'ERROR':
            return 'ERROR', None

        if tipo_izq == 'bool' and tipo_der == 'bool':
            return 'bool', None

        return 'ERROR', f"Operador lógico '{operador}' requiere operandos booleanos, pero se obtuvo '{tipo_izq}' y '{tipo_der}'."

    @classmethod
    def asignacion_compatible(cls, tipo_destino, tipo_origen):
        if tipo_destino == 'ERROR' or tipo_origen == 'ERROR':
            return True, None, None

        if tipo_destino == tipo_origen:
            return True, None, None

        if tipo_destino == 'float' and tipo_origen == 'int':
            return True, 'coercion_int_a_float', None

        if tipo_destino == 'int' and tipo_origen == 'float':
            error = "Incompatibilidad de tipos: no se puede asignar un valor de tipo 'float' a una variable de tipo 'int' (pérdida de precisión)."
            return False, None, error

        error = f"Incompatibilidad de tipos: no se puede asignar una expresión de tipo '{tipo_origen}' a una variable de tipo '{tipo_destino}'."
        return False, None, error


class AnalizadorSemantico:
    def __init__(self):
        self.tabla_simbolos = TablaSimbolos()
        self.errores = []
        self.valores = {}  # Entorno dinámico de valores de variables {nombre: valor}

    def analizar(self, ast_raiz):
        self.tabla_simbolos.limpiar()
        self.errores.clear()
        self.valores.clear()

        if not ast_raiz:
            return None, self.tabla_simbolos, ["No se proporcionó un AST válido para análisis."]

        ast_anotado = ast_raiz.copiar()
        self.procesar_nodo(ast_anotado)

        for e in self.tabla_simbolos.errores:
            if e not in self.errores:
                self.errores.append(e)

        return ast_anotado, self.tabla_simbolos, self.errores

    def registrar_error(self, mensaje, linea=0, columna=0):
        texto = f"Error Semántico en L:{linea} C:{columna} -> {mensaje}"
        if texto not in self.errores:
            self.errores.append(texto)

    def procesar_nodo(self, nodo):
        if not nodo:
            return

        etiqueta = nodo.etiqueta

        if etiqueta == "Declaracion Variable":
            self.procesar_declaracion(nodo)
            return
        elif etiqueta == "Instruccion / Asignacion":
            self.procesar_asignacion(nodo)
            return
        elif "Pre-Operador" in etiqueta or "Post-Operador" in etiqueta:
            self.procesar_unario_standalone(nodo)
            return
        elif etiqueta == "Seleccion (if)":
            self.procesar_seleccion(nodo)
            return
        elif etiqueta == "Iteracion (while)":
            self.procesar_while(nodo)
            return
        elif etiqueta == "Repeticion (do)":
            self.procesar_do(nodo)
            return
        elif etiqueta == "Entrada (cin)":
            self.procesar_cin(nodo)
            return
        elif etiqueta == "Salida (cout)":
            self.procesar_cout(nodo)
            return

        for hijo in nodo.hijos:
            self.procesar_nodo(hijo)

    def procesar_declaracion(self, nodo):
        nodo_tipo = None
        nodo_ids = None

        for hijo in nodo.hijos:
            if hijo.etiqueta == "Tipo":
                nodo_tipo = hijo
            elif hijo.etiqueta == "Identificadores":
                nodo_ids = hijo

        if not nodo_tipo or not nodo_ids:
            return

        tipo_declarado = nodo_tipo.lexema
        nodo_tipo.dtype = tipo_declarado

        for hijo_id in nodo_ids.hijos:
            if hijo_id.etiqueta == "ID":
                nombre = hijo_id.lexema
                hijo_id.dtype = tipo_declarado
                exito, error = self.tabla_simbolos.insertar(nombre, tipo_declarado, hijo_id.linea, hijo_id.columna)
                if exito:
                    simbolo = self.tabla_simbolos.buscar(nombre)
                    if simbolo:
                        hijo_id.desplazamiento = simbolo.desplazamiento
                    self.valores[nombre] = None
                else:
                    hijo_id.dtype = 'ERROR'

    def procesar_asignacion(self, nodo):
        nodo_id = None
        nodo_expr = None

        for hijo in nodo.hijos:
            if hijo.etiqueta == "ID":
                nodo_id = hijo
            elif hijo.etiqueta == "Sentencia Expresion":
                nodo_expr = hijo

        if not nodo_id:
            return

        nombre = nodo_id.lexema
        simbolo = self.tabla_simbolos.buscar(nombre)

        if not simbolo:
            self.registrar_error(f"Variable '{nombre}' no ha sido declarada.", nodo_id.linea, nodo_id.columna)
            nodo_id.dtype = 'ERROR'
            tipo_destino = 'ERROR'
        else:
            self.tabla_simbolos.registrar_uso(nombre, nodo_id.linea)
            # Siempre mantiene su tipo declarado válido sin etiquetas erróneas de ERROR
            nodo_id.dtype = simbolo.tipo
            nodo_id.desplazamiento = simbolo.desplazamiento
            tipo_destino = simbolo.tipo

        tipo_origen = 'ERROR'
        val_origen = None
        if nodo_expr and nodo_expr.hijos:
            tipo_origen, val_origen = self.evaluar_expresion(nodo_expr.hijos[0])
            nodo_expr.dtype = tipo_origen
            nodo_expr.val = val_origen

        if tipo_destino != 'ERROR' and tipo_origen != 'ERROR':
            compatible, coercion, error = TypeSystem.asignacion_compatible(tipo_destino, tipo_origen)
            if not compatible:
                self.registrar_error(error, nodo_id.linea, nodo_id.columna)
                nodo.val = None
            else:
                if coercion:
                    nodo.coercion = coercion
                if val_origen is not None:
                    try:
                        if tipo_destino == 'int':
                            val_almacenar = int(val_origen)
                        elif tipo_destino == 'float':
                            val_almacenar = float(val_origen)
                        elif tipo_destino == 'bool':
                            val_almacenar = bool(val_origen)
                        else:
                            val_almacenar = val_origen
                    except Exception:
                        val_almacenar = val_origen

                    simbolo.valor = val_almacenar
                    self.valores[nombre] = val_almacenar
                    nodo.val = val_almacenar
                    nodo_id.val = val_almacenar
                else:
                    simbolo.valor = None
                    self.valores[nombre] = None
                    nodo.val = None
        elif tipo_destino != 'ERROR':
            if simbolo:
                simbolo.valor = None
            self.valores[nombre] = None
            nodo.val = None

    def procesar_unario_standalone(self, nodo):
        nodo_id = None
        for hijo in nodo.hijos:
            if hijo.etiqueta == "ID":
                nodo_id = hijo
                break

        if not nodo_id:
            return

        nombre = nodo_id.lexema
        simbolo = self.tabla_simbolos.buscar(nombre)

        if not simbolo:
            self.registrar_error(f"Variable '{nombre}' no ha sido declarada.", nodo_id.linea, nodo_id.columna)
            nodo_id.dtype = 'ERROR'
        else:
            self.tabla_simbolos.registrar_uso(nombre, nodo_id.linea)
            nodo_id.dtype = simbolo.tipo
            nodo_id.desplazamiento = simbolo.desplazamiento

            if simbolo.tipo not in TypeSystem.TIPOS_NUMERICOS:
                self.registrar_error(f"Operador unario '{nodo.lexema}' solo es aplicable a tipos numéricos, no a '{simbolo.tipo}'.", nodo_id.linea, nodo_id.columna)
            else:
                val_prev = self.valores.get(nombre, None)
                if val_prev is not None:
                    if "++" in nodo.lexema:
                        val_nuevo = val_prev + 1
                    else:
                        val_nuevo = val_prev - 1
                    simbolo.valor = val_nuevo
                    self.valores[nombre] = val_nuevo
                    nodo.val = val_nuevo
                    nodo_id.val = val_nuevo

    def procesar_seleccion(self, nodo):
        if not nodo.hijos:
            return

        nodo_cond = nodo.hijos[0]
        tipo_cond, val_cond = self.evaluar_expresion(nodo_cond)
        nodo_cond.dtype = tipo_cond
        nodo_cond.val = val_cond

        if tipo_cond != 'bool' and tipo_cond != 'ERROR':
            self.registrar_error(f"La condición del 'if' debe ser de tipo 'bool', pero se obtuvo '{tipo_cond}'.", nodo.linea, nodo.columna)

        for hijo in nodo.hijos[1:]:
            self.procesar_nodo(hijo)

    def procesar_while(self, nodo):
        if not nodo.hijos:
            return

        nodo_cond = nodo.hijos[0]
        tipo_cond, val_cond = self.evaluar_expresion(nodo_cond)
        nodo_cond.dtype = tipo_cond
        nodo_cond.val = val_cond

        if tipo_cond != 'bool' and tipo_cond != 'ERROR':
            self.registrar_error(f"La condición del ciclo 'while' debe ser de tipo 'bool', pero se obtuvo '{tipo_cond}'.", nodo.linea, nodo.columna)

        for hijo in nodo.hijos[1:]:
            self.procesar_nodo(hijo)

    def procesar_do(self, nodo):
        if not nodo.hijos:
            return

        nodo_sentencias = nodo.hijos[0]
        self.procesar_nodo(nodo_sentencias)

        if len(nodo.hijos) > 1:
            nodo_cond = nodo.hijos[-1]
            tipo_cond, val_cond = self.evaluar_expresion(nodo_cond)
            nodo_cond.dtype = tipo_cond
            nodo_cond.val = val_cond

            if tipo_cond != 'bool' and tipo_cond != 'ERROR':
                self.registrar_error(f"La condición de término del ciclo 'do' debe ser de tipo 'bool', pero se obtuvo '{tipo_cond}'.", nodo.linea, nodo.columna)

    def procesar_cin(self, nodo):
        for hijo in nodo.hijos:
            if hijo.etiqueta == "ID":
                nombre = hijo.lexema
                simbolo = self.tabla_simbolos.buscar(nombre)
                if not simbolo:
                    self.registrar_error(f"Variable '{nombre}' no ha sido declarada en sentencia 'cin'.", hijo.linea, hijo.columna)
                    hijo.dtype = 'ERROR'
                else:
                    self.tabla_simbolos.registrar_uso(nombre, hijo.linea)
                    hijo.dtype = simbolo.tipo
                    hijo.desplazamiento = simbolo.desplazamiento
                    # Entrada en tiempo de ejecución: valor indeterminado en compilación
                    simbolo.valor = None
                    self.valores[nombre] = None

    def procesar_cout(self, nodo):
        for hijo in nodo.hijos:
            if hijo.etiqueta == "Salida":
                for item in hijo.hijos:
                    if item.etiqueta == "CADENA":
                        item.dtype = "cadena"
                    else:
                        self.evaluar_expresion(item)

    def evaluar_expresion(self, nodo):
        if not nodo:
            return 'ERROR', None

        etiqueta = nodo.etiqueta

        if etiqueta == "Componente":
            if nodo.hijos:
                tipo, val = self.evaluar_expresion(nodo.hijos[0])
                if tipo != 'ERROR':
                    nodo.dtype = tipo
                nodo.val = val
                return tipo, val
            return 'ERROR', None

        if etiqueta == "Numero":
            if "." in nodo.lexema:
                nodo.dtype = 'float'
                try: nodo.val = float(nodo.lexema)
                except ValueError: nodo.val = None
            else:
                nodo.dtype = 'int'
                try: nodo.val = int(nodo.lexema)
                except ValueError: nodo.val = None
            return nodo.dtype, nodo.val

        if etiqueta == "Booleano":
            nodo.dtype = 'bool'
            nodo.val = (nodo.lexema == "true")
            return nodo.dtype, nodo.val

        if etiqueta == "ID":
            nombre = nodo.lexema
            simbolo = self.tabla_simbolos.buscar(nombre)
            if not simbolo:
                self.registrar_error(f"Variable '{nombre}' no ha sido declarada.", nodo.linea, nodo.columna)
                nodo.dtype = 'ERROR'
                nodo.val = None
                return 'ERROR', None
            else:
                self.tabla_simbolos.registrar_uso(nombre, nodo.linea)
                nodo.dtype = simbolo.tipo
                nodo.desplazamiento = simbolo.desplazamiento
                # Jalar valor actual propagado
                val = self.valores.get(nombre, None)
                nodo.val = val
                return simbolo.tipo, val

        if etiqueta == "Menos Unario":
            if nodo.hijos:
                tipo_hijo, val_hijo = self.evaluar_expresion(nodo.hijos[0])
                nodo.dtype = tipo_hijo
                if val_hijo is not None:
                    nodo.val = -val_hijo
                return nodo.dtype, nodo.val
            return 'ERROR', None

        if etiqueta == "Operador NOT":
            if nodo.hijos:
                tipo_hijo, val_hijo = self.evaluar_expresion(nodo.hijos[0])
                if tipo_hijo != 'bool' and tipo_hijo != 'ERROR':
                    self.registrar_error(f"Operador '!' requiere operando booleano, se obtuvo '{tipo_hijo}'.", nodo.linea, nodo.columna)
                    nodo.dtype = 'ERROR'
                else:
                    nodo.dtype = 'bool'
                    if val_hijo is not None:
                        nodo.val = not val_hijo
                return nodo.dtype, nodo.val
            return 'ERROR', None

        if "Operador Aritmetico" in etiqueta or etiqueta == "Operador Potencia":
            op = nodo.lexema
            if len(nodo.hijos) >= 2:
                tipo_izq, val_izq = self.evaluar_expresion(nodo.hijos[0])
                tipo_der, val_der = self.evaluar_expresion(nodo.hijos[1])

                tipo_res, coercion, error = TypeSystem.operacion_aritmetica(tipo_izq, tipo_der, op)
                nodo.dtype = tipo_res
                nodo.coercion = coercion

                if error:
                    self.registrar_error(error, nodo.linea, nodo.columna)

                if val_izq is not None and val_der is not None and tipo_res != 'ERROR':
                    try:
                        if op == "+": nodo.val = val_izq + val_der
                        elif op == "-": nodo.val = val_izq - val_der
                        elif op == "*": nodo.val = val_izq * val_der
                        elif op == "/":
                            if val_der == 0:
                                self.registrar_error("División entre cero detectada en tiempo de compilación.", nodo.linea, nodo.columna)
                                nodo.val = None
                            else:
                                if tipo_res == 'int':
                                    nodo.val = val_izq // val_der
                                else:
                                    nodo.val = val_izq / val_der
                        elif op == "%": nodo.val = val_izq % val_der
                        elif op == "^": nodo.val = val_izq ** val_der
                    except Exception:
                        nodo.val = None

                return nodo.dtype, nodo.val

        if etiqueta == "Operador Relacional":
            op = nodo.lexema
            if len(nodo.hijos) >= 2:
                tipo_izq, val_izq = self.evaluar_expresion(nodo.hijos[0])
                tipo_der, val_der = self.evaluar_expresion(nodo.hijos[1])

                tipo_res, error = TypeSystem.operacion_relacional(tipo_izq, tipo_der, op)
                nodo.dtype = tipo_res

                if error:
                    self.registrar_error(error, nodo.linea, nodo.columna)

                if val_izq is not None and val_der is not None and tipo_res != 'ERROR':
                    try:
                        if op == "<": nodo.val = val_izq < val_der
                        elif op == "<=": nodo.val = val_izq <= val_der
                        elif op == ">": nodo.val = val_izq > val_der
                        elif op == ">=": nodo.val = val_izq >= val_der
                        elif op == "==": nodo.val = val_izq == val_der
                        elif op == "!=": nodo.val = val_izq != val_der
                    except Exception:
                        nodo.val = None

                return nodo.dtype, nodo.val

        if etiqueta in ["Operador AND", "Operador OR"]:
            op = nodo.lexema
            if len(nodo.hijos) >= 2:
                tipo_izq, val_izq = self.evaluar_expresion(nodo.hijos[0])
                tipo_der, val_der = self.evaluar_expresion(nodo.hijos[1])

                tipo_res, error = TypeSystem.operacion_logica(tipo_izq, tipo_der, op)
                nodo.dtype = tipo_res

                if error:
                    self.registrar_error(error, nodo.linea, nodo.columna)

                if val_izq is not None and val_der is not None and tipo_res != 'ERROR':
                    try:
                        if op == "&&": nodo.val = bool(val_izq and val_der)
                        elif op == "||": nodo.val = bool(val_izq or val_der)
                    except Exception:
                        nodo.val = None

                return nodo.dtype, nodo.val

        tipo_ultimo = 'ERROR'
        val_ultimo = None
        for hijo in nodo.hijos:
            tipo_ultimo, val_ultimo = self.evaluar_expresion(hijo)

        nodo.dtype = tipo_ultimo
        nodo.val = val_ultimo
        return nodo.dtype, nodo.val
