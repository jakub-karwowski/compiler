from sly import Lexer


class CLexer(Lexer):
    tokens = {
        PROCEDURE,
        IS,
        VAR,
        BEGIN,
        END,
        PROGRAM,
        ID,
        NUMBER,
        ASSIGN,
        IF,
        THEN,
        ELSE,
        ENDIF,
        WHILE,
        DO,
        ENDWHILE,
        REPEAT,
        UNTIL,
        READ,
        WRITE,
        LPAREN,
        RPAREN,
        SCOLON,
        COMMA,
        ADD,
        SUB,
        MUL,
        DIV,
        MOD,
        EQ,
        NEQ,
        GT,
        LT,
        GE,
        LE,
        LEXERR,
    }
    ignore = " \t"
    ignore_newline = r"\n+"
    ignore_comment = r"\[[^]]*\]"
    ID = r"[_a-z]+"
    NUMBER = r"[0-9]+"
    ADD = r"\+"
    SUB = r"-"
    MUL = r"\*"
    DIV = r"/"

    LPAREN = r"\("
    RPAREN = r"\)"
    MOD = r"%"
    ASSIGN = r":="
    NEQ = r"!="
    LE = r"<="
    GE = r">="
    LT = r"<"
    GT = r">"
    EQ = r"="
    SCOLON = r";"
    COMMA = r","
    PROCEDURE = r"PROCEDURE"
    IS = r"IS"
    VAR = r"VAR"
    BEGIN = r"BEGIN"
    PROGRAM = r"PROGRAM"
    IF = r"IF"
    THEN = r"THEN"
    ELSE = r"ELSE"
    ENDIF = r"ENDIF"
    ENDWHILE = r"ENDWHILE"
    END = r"END"
    WHILE = r"WHILE"
    DO = r"DO"
    REPEAT = r"REPEAT"
    UNTIL = r"UNTIL"
    READ = r"READ"
    WRITE = r"WRITE"
    LEXERR = r"[^\n \t;]+"

    def ignore_newline(self, t):
        self.lineno += 1

    def LEXERR(self, t):
        raise Exception(f"Line {self.lineno}: Unknown token {t.value}")
        # return t

    # def error(self, t):
    #     print(f"Line {self.lineno}: Unknown token {t.value}")
    #     self.index += 1
