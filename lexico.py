class Token:
    def __init__(self, tipo, lexema, linea, columna):
        self.tipo = tipo
        self.lexema = lexema
        self.linea = linea
        self.columna = columna

    def __str__(self):
        return f"<{self.tipo}, '{self.lexema}', L:{self.linea} C:{self.columna}>"

class AnalizadorLexico:
    def __init__(self):
        # Palabras reservadas 
        self.palabras_reservadas = {
            'if', 'else', 'end', 'do', 'while', 'switch', 
            'case', 'int', 'float', 'main', 'cin', 'cout'
        }

    def analizar(self, codigo):
        tokens = []
        errores = []
        pos = 0
        linea = 1
        columna = 1
        n = len(codigo)

        while pos < n:
            estado = "INICIO"
            lexema = ""
            col_inicio = columna
            linea_inicio = linea 
            
            # variables para regresar en el tiempo si el operador no se completa
            saved_pos = pos
            saved_linea = linea
            saved_columna = columna

            while estado != "HECHO" and pos < n:
                c = codigo[pos]

                # ==========================================
                # ESTADO: INICIO
                # ==========================================
                if estado == "INICIO":
                    if c.isspace():
                        if c == '\n':
                            linea += 1
                            columna = 0
                        pos += 1
                        columna += 1
                        col_inicio = columna
                        linea_inicio = linea 
                        continue  
                    elif c.isalpha():
                        estado = "IN_ID"
                        lexema += c
                        pos += 1
                        columna += 1
                    elif c.isdigit():
                        estado = "IN_NUM"
                        lexema += c
                        pos += 1
                        columna += 1
                    elif c in "<>=":
                        estado = "B_RELACIONAL"
                        lexema += c
                        pos += 1; columna += 1
                        saved_pos = pos; saved_linea = linea; saved_columna = columna
                    elif c == '!':
                        estado = "B_NOT_OR_NEQ"
                        lexema += c
                        pos += 1; columna += 1
                        saved_pos = pos; saved_linea = linea; saved_columna = columna
                    elif c == '&':
                        estado = "B_AND"
                        lexema += c
                        pos += 1; columna += 1
                        saved_pos = pos; saved_linea = linea; saved_columna = columna
                    elif c == '|':
                        estado = "B_OR"
                        lexema += c
                        pos += 1; columna += 1
                        saved_pos = pos; saved_linea = linea; saved_columna = columna
                    elif c == '+':
                        estado = "B_SUMA"
                        lexema += c
                        pos += 1; columna += 1
                        saved_pos = pos; saved_linea = linea; saved_columna = columna
                    elif c == '-':
                        estado = "B_RESTA"
                        lexema += c
                        pos += 1; columna += 1
                        saved_pos = pos; saved_linea = linea; saved_columna = columna
                    elif c == '/':
                        estado = "B_COMENTARIO"
                        lexema += c
                        pos += 1; columna += 1
                        saved_pos = pos; saved_linea = linea; saved_columna = columna
                    elif c == '"':
                        estado = "B_STRING"
                        lexema += c
                        pos += 1
                        columna += 1
                    elif c == "'":
                        estado = "B_CHAR"
                        lexema += c
                        pos += 1
                        columna += 1
                    elif c in "(){},;*%^":
                        lexema += c
                        tipo = "SIMBOLO" if c in "(){},;" else "ARITMETICO"
                        tokens.append(Token(tipo, lexema, linea_inicio, col_inicio))
                        pos += 1
                        columna += 1
                        estado = "HECHO"
                    else:
                        errores.append(f"Error léxico: Carácter inválido '{c}' en línea: {linea_inicio}, columna: {col_inicio}")
                        pos += 1
                        columna += 1
                        estado = "HECHO"

                # ==========================================
                # ESTADOS: IDENTIFICADORES Y NÚMEROS
                # ==========================================
                elif estado == "IN_ID":
                    if c.isalnum():
                        lexema += c
                        pos += 1
                        columna += 1
                    else:
                        tipo = "RESERVADA" if lexema in self.palabras_reservadas else "ID"
                        tokens.append(Token(tipo, lexema, linea_inicio, col_inicio))
                        estado = "HECHO"

                elif estado == "IN_NUM":
                    if c.isdigit():
                        lexema += c
                        pos += 1
                        columna += 1
                    elif c == '.':
                        estado = "B_REALES"
                        lexema += c
                        pos += 1
                        columna += 1
                    else:
                        tokens.append(Token("NUM_ENTERO", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"

                elif estado == "B_REALES":
                    if c.isdigit():
                        estado = "IN_REAL"
                        lexema += c
                        pos += 1
                        columna += 1
                    else:
                        errores.append(f"Error léxico: Se esperaba dígito tras punto en línea: {linea_inicio}, columna: {columna}")
                        estado = "HECHO"

                elif estado == "IN_REAL":
                    if c.isdigit():
                        lexema += c
                        pos += 1
                        columna += 1
                    else:
                        tokens.append(Token("NUM_REAL", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"

                # ==========================================
                # ESTADOS: OPERADORES (IGNORANDO ESPACIOS)
                # ==========================================
                elif estado == "B_RELACIONAL":
                    if c.isspace(): # ABSORBER ESPACIOS Y SALTOS
                        if c == '\n': linea += 1; columna = 0
                        lexema += c; pos += 1; columna += 1
                    elif c == '=':
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("RELACIONAL", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    else:
                        real_lexema = lexema[0] # Solo toma el primer carácter
                        if real_lexema == "=":
                            tokens.append(Token("ASIGNACION", real_lexema, linea_inicio, col_inicio))
                        else:
                            tokens.append(Token("RELACIONAL", real_lexema, linea_inicio, col_inicio))
                        # restaurar el tiempo para que los espacios absorbidos se lean de nuevo
                        pos = saved_pos; linea = saved_linea; columna = saved_columna
                        estado = "HECHO"

                elif estado == "B_NOT_OR_NEQ":
                    if c.isspace():
                        if c == '\n': linea += 1; columna = 0
                        lexema += c; pos += 1; columna += 1
                    elif c == '=': 
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("RELACIONAL", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    else: 
                        tokens.append(Token("LOGICO", lexema[0], linea_inicio, col_inicio))
                        pos = saved_pos; linea = saved_linea; columna = saved_columna
                        estado = "HECHO"

                elif estado == "B_AND":
                    if c.isspace():
                        if c == '\n': linea += 1; columna = 0
                        lexema += c; pos += 1; columna += 1
                    elif c == '&':
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("LOGICO", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    else:
                        errores.append(f"Error léxico: Operador incompleto, se esperaba '&' en línea: {linea_inicio}, columna: {col_inicio}")
                        pos = saved_pos; linea = saved_linea; columna = saved_columna
                        estado = "HECHO"

                elif estado == "B_OR":
                    if c.isspace():
                        if c == '\n': linea += 1; columna = 0
                        lexema += c; pos += 1; columna += 1
                    elif c == '|':
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("LOGICO", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    else:
                        errores.append(f"Error léxico: Operador incompleto, se esperaba '|' en línea: {linea_inicio}, columna: {col_inicio}")
                        pos = saved_pos; linea = saved_linea; columna = saved_columna
                        estado = "HECHO"

                elif estado == "B_SUMA":
                    if c.isspace():
                        if c == '\n': linea += 1; columna = 0
                        lexema += c; pos += 1; columna += 1
                    elif c == '+':
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("ARITMETICO", lexema, linea_inicio, col_inicio)) 
                        estado = "HECHO"
                    else:
                        tokens.append(Token("ARITMETICO", lexema[0], linea_inicio, col_inicio)) 
                        pos = saved_pos; linea = saved_linea; columna = saved_columna
                        estado = "HECHO"

                elif estado == "B_RESTA":
                    if c.isspace():
                        if c == '\n': linea += 1; columna = 0
                        lexema += c; pos += 1; columna += 1
                    elif c == '-':
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("ARITMETICO", lexema, linea_inicio, col_inicio)) 
                        estado = "HECHO"
                    else:
                        tokens.append(Token("ARITMETICO", lexema[0], linea_inicio, col_inicio)) 
                        pos = saved_pos; linea = saved_linea; columna = saved_columna
                        estado = "HECHO"

                # ==========================================
                # ESTADOS: COMENTARIOS
                # ==========================================
                elif estado == "B_COMENTARIO":
                    if c == '/':
                        estado = "COMENTARIOL"
                        lexema += c; pos += 1; columna += 1
                    elif c == '*':
                        estado = "COMENTARIOM"
                        lexema += c; pos += 1; columna += 1
                    else:
                        tokens.append(Token("ARITMETICO", lexema[0], linea_inicio, col_inicio)) 
                        pos = saved_pos; linea = saved_linea; columna = saved_columna
                        estado = "HECHO"

                elif estado == "COMENTARIOL":
                    if c == '\n':
                        tokens.append(Token("COMENTARIO", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    else:
                        lexema += c; pos += 1; columna += 1

                elif estado == "COMENTARIOM":
                    if c == '*':
                        estado = "CIERRE_C"
                    elif c == '\n':
                        linea += 1; columna = 0
                    lexema += c; pos += 1; columna += 1

                elif estado == "CIERRE_C":
                    if c == '/':
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("COMENTARIO", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    elif c == '*':
                        lexema += c; pos += 1; columna += 1
                    else:
                        if c == '\n': linea += 1; columna = 0
                        lexema += c; pos += 1; columna += 1
                        estado = "COMENTARIOM"

                # ==========================================
                # ESTADOS: CADENAS Y CARACTERES
                # ==========================================
                elif estado == "B_STRING":
                    if c == '"':
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("CADENA", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    elif c == '\n':
                        errores.append(f"Error léxico: Cadena sin cerrar en línea: {linea_inicio}, columna: {col_inicio}")
                        estado = "HECHO"
                    else:
                        lexema += c; pos += 1; columna += 1

                elif estado == "B_CHAR":
                    if c == "'":
                        lexema += c; pos += 1; columna += 1
                        tokens.append(Token("CARACTER", lexema, linea_inicio, col_inicio))
                        estado = "HECHO"
                    elif c == '\n':
                        errores.append(f"Error léxico: Carácter sin cerrar en línea: {linea_inicio}, columna: {col_inicio}")
                        estado = "HECHO"
                    else:
                        lexema += c; pos += 1; columna += 1

            # ==========================================
            # MANEJO DE FIN DE ARCHIVO (EOF)
            # ==========================================
            if pos >= n and estado != "HECHO":
                if estado == "IN_ID":
                    tipo = "RESERVADA" if lexema in self.palabras_reservadas else "ID"
                    tokens.append(Token(tipo, lexema, linea_inicio, col_inicio))
                elif estado == "IN_NUM":
                    tokens.append(Token("NUM_ENTERO", lexema, linea_inicio, col_inicio))
                elif estado == "IN_REAL":
                    tokens.append(Token("NUM_REAL", lexema, linea_inicio, col_inicio))
                elif estado == "B_REALES":
                    errores.append(f"Error léxico: Se esperaba dígito en línea: {linea_inicio}, columna: {columna}")
                
                # manejo de EOF para operadores que ignoraron espacios
                elif estado in ["B_RELACIONAL", "B_SUMA", "B_RESTA"]:
                    real_lexema = lexema[0]
                    if real_lexema == "=":
                        tokens.append(Token("ASIGNACION", real_lexema, linea_inicio, col_inicio))
                    else:
                        tipo = "RELACIONAL" if estado == "B_RELACIONAL" else "ARITMETICO"
                        tokens.append(Token(tipo, real_lexema, linea_inicio, col_inicio))
                    pos = saved_pos; linea = saved_linea; columna = saved_columna
                elif estado == "B_NOT_OR_NEQ":
                    tokens.append(Token("LOGICO", lexema[0], linea_inicio, col_inicio))
                    pos = saved_pos; linea = saved_linea; columna = saved_columna
                elif estado in ["B_AND", "B_OR"]:
                    char_esperado = '&' if estado == "B_AND" else '|'
                    errores.append(f"Error léxico: Operador incompleto, se esperaba '{char_esperado}' en línea: {linea_inicio}, columna: {col_inicio}")
                    pos = saved_pos; linea = saved_linea; columna = saved_columna
                elif estado == "B_COMENTARIO":
                    tokens.append(Token("ARITMETICO", lexema[0], linea_inicio, col_inicio))
                    pos = saved_pos; linea = saved_linea; columna = saved_columna
                
                elif estado == "COMENTARIOL":
                    tokens.append(Token("COMENTARIO", lexema, linea_inicio, col_inicio))
                elif estado in ["COMENTARIOM", "CIERRE_C"]:
                    errores.append(f"Error léxico: Comentario multilínea sin cerrar en línea: {linea_inicio}, columna: {col_inicio}")
                    tokens.append(Token("COMENTARIO", lexema, linea_inicio, col_inicio))
                elif estado in ["B_STRING", "B_CHAR"]:
                    errores.append(f"Error léxico: Cadena o carácter sin cerrar en línea: {linea_inicio}, columna: {col_inicio}")
                    tipo_token = "CADENA" if estado == "B_STRING" else "CARACTER"
                    tokens.append(Token(tipo_token, lexema, linea_inicio, col_inicio))
                
                estado = "HECHO"

        return tokens, errores

# Bloque para pruebas
if __name__ == "__main__":
    codigo_prueba = """
    main sum@r 3.14+main)if{32.algo
34.34.34.34
{
int x,y,z;
real a,b,c;
 suma=45;
x=32.32;
x=23;
y=2+3-1;
z=y+7;
y=y+1;
a=24.0+4-1/3*2+34-1;
x=(5-3)*(8/2);
y=5+3-2*4/7-9;
z=8/2+15*4;
y=14.54;
if(2>3)then
        y=a+3;
  else
      if(4>2 && )then
             b=3.2;
       else
           b=5.0;
       end;
       y=y+1;
end;
a+

+;
c--;
x=3+4;
do
   y=(y+1)*2+1;
   while(x>7){x=6+8/9*8/3;   
    cin x; 
   mas=36/7; 
   };

 until(y=


=



5);
 while(y==0){
    cin mas;
    cout x;
};
}
    """
    analizador = AnalizadorLexico()
    tokens, errores = analizador.analizar(codigo_prueba)
    
    print("--- TOKENS ---")
    for t in tokens:
        print(t)
        
    print("\n--- ERRORES ---")
    for e in errores:
        print(e)