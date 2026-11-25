import os
import re


class SimuladorTM:
    """Simulador interactivo de la Tiny Machine (TM) con soporte para enteros y flotantes.

    Implementado como máquina de estados no bloqueante para integrarse
    directamente en la terminal del IDE.
    """

    IADDR_SIZE = 1024
    DADDR_SIZE = 1024
    NO_REGS = 8
    PC_REG = 7

    OP_RR = {"HALT", "IN", "INF", "OUT", "ADD", "SUB", "MUL", "DIV"}
    OP_RM = {"LD", "ST"}
    OP_RA = {"LDA", "LDC", "LDCF", "JLT", "JLE", "JGT", "JGE", "JEQ", "JNE"}

    STEP_RESULTS = {
        "srOKAY": "Correcto",
        "srHALT": "Ejecucion finalizada (HALT)",
        "srIMEM_ERR": "Error: memoria de instrucciones",
        "srDMEM_ERR": "Error: memoria de datos",
        "srZERODIVIDE": "Error: division entre cero",
    }

    def __init__(self):
        self.iMem = {}
        self.dMem = [0] * self.DADDR_SIZE
        self.reg = [0] * self.NO_REGS
        self.iloc = 0
        self.dloc = 0
        self.traceflag = False
        self.icountflag = False
        self.pgm_path = ""
        self.estado = "IDLE"  # IDLE, WAITING_COMMAND, WAITING_INPUT, FINISHED

        # Estado de ejecución en curso (para pausar en IN/INF y reanudar)
        self._running_cmd = None
        self._stepcnt = 0
        self._executed_steps = 0
        self._pending_in_reg = 0
        self._pending_in_is_float = False

    def cargar_programa(self, ruta_tm):
        """Carga y valida un archivo .tm. Retorna (exito, mensajes_salida)."""
        self.pgm_path = ruta_tm
        self.iMem.clear()
        self.reiniciar_memoria()
        self.traceflag = False
        self.icountflag = False
        self.estado = "IDLE"

        if not os.path.isfile(ruta_tm):
            return False, [f"Archivo no encontrado: '{ruta_tm}'"]

        try:
            with open(ruta_tm, "r", encoding="utf-8", errors="replace") as f:
                lineas = f.readlines()
        except Exception as e:
            return False, [f"Error al abrir '{ruta_tm}': {e}"]

        # Regex para instrucciones RR: loc: OP r,s,t
        rx_rr = re.compile(r"^\s*(\d+)\s*:\s*([A-Za-z]+)\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
        # Regex para instrucciones RM/RA: loc: OP r,d(s)  (d puede ser entero o flotante con signo)
        rx_rm = re.compile(r"^\s*(\d+)\s*:\s*([A-Za-z]+)\s+(\d+)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*[\(,]\s*(\d+)\s*\)?")

        for num_linea, raw in enumerate(lineas, start=1):
            sin_tab = raw.split("\t")[0].strip()
            if not sin_tab or sin_tab.startswith("*"):
                continue

            m_rr = rx_rr.match(sin_tab)
            m_rm = rx_rm.match(sin_tab)

            if m_rr:
                loc = int(m_rr.group(1))
                op = m_rr.group(2).upper()
                if op not in self.OP_RR:
                    return False, [f"Línea {num_linea}: Opcode RR ilegal '{op}'"]
                a1, a2, a3 = int(m_rr.group(3)), int(m_rr.group(4)), int(m_rr.group(5))
            elif m_rm:
                loc = int(m_rm.group(1))
                op = m_rm.group(2).upper()
                if op not in self.OP_RM and op not in self.OP_RA:
                    return False, [f"Línea {num_linea}: Opcode RM/RA ilegal '{op}'"]
                a1 = int(m_rm.group(3))
                val_str = m_rm.group(4)
                if op == "LDCF" or "." in val_str:
                    a2 = float(val_str)
                else:
                    a2 = int(val_str)
                a3 = int(m_rm.group(5))
            else:
                return False, [f"Línea {num_linea}: Formato de instrucción inválido -> {sin_tab}"]

            if not (0 <= loc < self.IADDR_SIZE):
                return False, [f"Línea {num_linea}: Dirección de instrucción fuera de rango ({loc})"]
            if not (0 <= a1 < self.NO_REGS) or not (0 <= a3 < self.NO_REGS):
                return False, [f"Línea {num_linea}: Registro inválido en instrucción {loc}"]
            if op in self.OP_RR and not (0 <= a2 < self.NO_REGS):
                return False, [f"Línea {num_linea}: Segundo registro inválido en instrucción {loc}"]

            self.iMem[loc] = (op, a1, a2, a3)

        self.estado = "WAITING_COMMAND"
        return True, ["Simulador TM listo (soporta enteros y flotantes). Escriba 'h' para ver la ayuda."]

    def reiniciar_memoria(self):
        self.iloc = 0
        self.dloc = 0
        self.reg = [0] * self.NO_REGS
        self.dMem = [0] * self.DADDR_SIZE
        self.dMem[0] = self.DADDR_SIZE - 1

    def _formatear_valor(self, val):
        if isinstance(val, float):
            if val.is_integer():
                return f"{val:.1f}"
            return f"{val:.6g}"
        return str(val)

    def _formatear_instruccion(self, loc):
        inst = self.iMem.get(loc, ("HALT", 0, 0, 0))
        op, a1, a2, a3 = inst
        if op in self.OP_RR:
            return f"{loc:5d}: {op:>6s} {a1:2d},{a2},{a3}"
        return f"{loc:5d}: {op:>6s} {a1:2d},{a2}({a3})"

    def _step_tm(self):
        pc = int(self.reg[self.PC_REG])
        if pc < 0 or pc >= self.IADDR_SIZE:
            return "srIMEM_ERR", []

        self.reg[self.PC_REG] = pc + 1
        op, a1, a2, a3 = self.iMem.get(pc, ("HALT", 0, 0, 0))
        salidas = []

        if op in self.OP_RR:
            r, s, t = a1, a2, a3
            if op == "HALT":
                salidas.append(f"HALT: {r},{s},{t}")
                return "srHALT", salidas
            elif op in ("IN", "INF"):
                self._pending_in_reg = r
                self._pending_in_is_float = (op == "INF")
                self.estado = "WAITING_INPUT"
                etiqueta = "numero (IN/float)" if op == "INF" else "numero (IN)"
                salidas.append(f"Ingrese un {etiqueta}: ")
                return "srWAIT_INPUT", salidas
            elif op == "OUT":
                salidas.append(f"Resultado del programa (OUT): {self._formatear_valor(self.reg[r])}")
            elif op == "ADD":
                self.reg[r] = self.reg[s] + self.reg[t]
            elif op == "SUB":
                self.reg[r] = self.reg[s] - self.reg[t]
            elif op == "MUL":
                self.reg[r] = self.reg[s] * self.reg[t]
            elif op == "DIV":
                if self.reg[t] == 0:
                    return "srZERODIVIDE", salidas
                if isinstance(self.reg[s], float) or isinstance(self.reg[t], float):
                    self.reg[r] = self.reg[s] / self.reg[t]
                else:
                    # División entera truncando hacia cero (como en C)
                    self.reg[r] = int(self.reg[s] / self.reg[t])

        elif op in self.OP_RM:
            r = a1
            m = int(a2 + self.reg[a3])
            if m < 0 or m >= self.DADDR_SIZE:
                return "srDMEM_ERR", salidas
            if op == "LD":
                self.reg[r] = self.dMem[m]
            elif op == "ST":
                self.dMem[m] = self.reg[r]

        elif op in self.OP_RA:
            r = a1
            if op == "LDC":
                self.reg[r] = int(a2) if not isinstance(a2, float) else a2
            elif op == "LDCF":
                self.reg[r] = float(a2)
            else:
                m = int(a2 + self.reg[a3])
                if op == "LDA":
                    self.reg[r] = m
                elif op == "JLT" and self.reg[r] < 0:
                    self.reg[self.PC_REG] = m
                elif op == "JLE" and self.reg[r] <= 0:
                    self.reg[self.PC_REG] = m
                elif op == "JGT" and self.reg[r] > 0:
                    self.reg[self.PC_REG] = m
                elif op == "JGE" and self.reg[r] >= 0:
                    self.reg[self.PC_REG] = m
                elif op == "JEQ" and self.reg[r] == 0:
                    self.reg[self.PC_REG] = m
                elif op == "JNE" and self.reg[r] != 0:
                    self.reg[self.PC_REG] = m

        return "srOKAY", salidas

    def _continuar_ejecucion(self):
        salidas = []
        step_result = "srOKAY"

        while self._running_cmd == "g" or self._stepcnt > 0:
            iloc = int(self.reg[self.PC_REG])
            if self.traceflag:
                salidas.append(self._formatear_instruccion(iloc))

            step_result, step_out = self._step_tm()
            salidas.extend(step_out)

            if step_result == "srWAIT_INPUT":
                return salidas

            self._executed_steps += 1
            if self._running_cmd != "g":
                self._stepcnt -= 1

            if step_result != "srOKAY":
                break

        if self._running_cmd == "g" and self.icountflag:
            salidas.append(f"Number of instructions executed = {self._executed_steps}")

        salidas.append(self.STEP_RESULTS.get(step_result, step_result))
        self._running_cmd = None
        self.estado = "WAITING_COMMAND"
        return salidas

    def _mostrar_ci(self):
        base, _ = os.path.splitext(self.pgm_path)
        ruta_ci = base + ".ci"
        if not os.path.isfile(ruta_ci):
            return [f"No se encontró el código intermedio: {ruta_ci}"]
        salidas = [f"======= CODIGO INTERMEDIO: {os.path.basename(ruta_ci)} ======="]
        try:
            with open(ruta_ci, "r", encoding="utf-8", errors="replace") as f:
                for l in f:
                    salidas.append(l.rstrip("\r\n"))
        except Exception as e:
            salidas.append(f"Error al leer .ci: {e}")
        salidas.append("======= FIN DEL CODIGO INTERMEDIO =======")
        return salidas

    def procesar_entrada(self, texto):
        """Procesa una línea ingresada por el usuario (comando TM o valor para IN).
        Retorna lista de líneas de salida."""
        texto = texto.strip()

        if self.estado == "WAITING_INPUT":
            if not texto:
                return ["Valor inválido. Ingrese un número: "]
            try:
                if self._pending_in_is_float or "." in texto:
                    val = float(texto)
                else:
                    val = int(texto)
            except ValueError:
                return ["Illegal value. Ingrese un número válido (ej. 5 o 3.14): "]

            self.reg[self._pending_in_reg] = val
            self._executed_steps += 1
            if self._running_cmd != "g":
                self._stepcnt -= 1
            self.estado = "RUNNING"
            return self._continuar_ejecucion()

        if self.estado != "WAITING_COMMAND":
            return []

        if not texto:
            return []

        partes = texto.split()
        cmd = partes[0].lower()[0]
        salidas = []

        if cmd == "h":
            salidas.extend([
                "COMANDOS DE LA MAQUINA TM:",
                " h        Mostrar esta ayuda",
                " v        Ver codigo intermedio (.ci)",
                " i b n    Ver n instrucciones TM desde la direccion b",
                " d b n    Ver n posiciones de memoria de datos desde b",
                " r        Ver el contenido de los registros",
                " s [n]    Ejecutar n instrucciones (por defecto 1)",
                " g        Ejecutar el programa hasta HALT",
                " t        Activar/desactivar rastreo de instrucciones",
                " p        Activar/desactivar contador de instrucciones",
                " c        Reiniciar registros y memoria de datos",
                " q        Salir del simulador",
            ])
        elif cmd == "v":
            salidas.extend(self._mostrar_ci())
        elif cmd == "t":
            self.traceflag = not self.traceflag
            salidas.append(f"Tracing now {'on' if self.traceflag else 'off'}.")
        elif cmd == "p":
            self.icountflag = not self.icountflag
            salidas.append(f"Printing instruction count now {'on' if self.icountflag else 'off'}.")
        elif cmd == "r":
            fila1 = "  ".join(f"{i}: {self._formatear_valor(self.reg[i]):>6}" for i in range(4))
            fila2 = "  ".join(f"{i}: {self._formatear_valor(self.reg[i]):>6}" for i in range(4, 8))
            salidas.extend([fila1, fila2])
        elif cmd == "i":
            b = int(partes[1]) if len(partes) > 1 and partes[1].lstrip("-").isdigit() else self.iloc
            n = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 1
            self.iloc = b
            for _ in range(n):
                if 0 <= self.iloc < self.IADDR_SIZE:
                    salidas.append(self._formatear_instruccion(self.iloc))
                    self.iloc += 1
        elif cmd == "d":
            b = int(partes[1]) if len(partes) > 1 and partes[1].lstrip("-").isdigit() else self.dloc
            n = int(partes[2]) if len(partes) > 2 and partes[2].isdigit() else 1
            self.dloc = b
            for _ in range(n):
                if 0 <= self.dloc < self.DADDR_SIZE:
                    salidas.append(f"{self.dloc:5d}: {self._formatear_valor(self.dMem[self.dloc]):>8}")
                    self.dloc += 1
        elif cmd == "c":
            self.reiniciar_memoria()
            salidas.append("Registros y memoria de datos reiniciados.")
        elif cmd == "q":
            self.estado = "FINISHED"
            salidas.append("Fin de la simulacion TM.")
        elif cmd == "g":
            self._running_cmd = "g"
            self._stepcnt = 1
            self._executed_steps = 0
            self.estado = "RUNNING"
            salidas.extend(self._continuar_ejecucion())
        elif cmd == "s":
            n = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 1
            self._running_cmd = "s"
            self._stepcnt = abs(n)
            self._executed_steps = 0
            self.estado = "RUNNING"
            salidas.extend(self._continuar_ejecucion())
        else:
            salidas.append(f"Comando '{cmd}' desconocido. Escriba 'h' para ayuda.")

        return salidas
