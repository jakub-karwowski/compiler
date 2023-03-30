from sly import Parser
from CLexer import CLexer
from CProcessor import *
from ProcObj import *


class CParser(Parser):
    tokens = CLexer.tokens
    start = "program_all"
    proc = CProcessor()

    @_("")
    def empty(self, p):
        pass

    @_("procedures main")
    def program_all(self, p):
        self.proc.tree_walk(p.main)
        self.proc.tree_walk_proc(p.procedures)
        t = self.proc.process_list(p.main)
        f = self.proc.process_list_procedures(p.procedures)
        t1 = self.proc.fin_glue_outer(t)
        f1 = self.proc.fin_glue_proc(f)
        t1 = self.proc.fin_merge(t1, f1)
        t1 = self.proc.substitute_consts(t1)
        t1 = self.proc.substitute_labels(t1)
        return t1

    @_("procedures PROCEDURE proc_head IS VAR declarations BEGIN commands END")
    def procedures(self, p):
        name = p.proc_head[0]
        self.proc.createProc(name)
        self.proc.initVars(name, p.declarations)
        self.proc.initRefs(name, p.proc_head[1])
        p.procedures.append([name, p.commands])
        return p.procedures

    @_("procedures PROCEDURE proc_head IS BEGIN commands END")
    def procedures(self, p):
        name = p.proc_head[0]
        self.proc.createProc(name)
        self.proc.initRefs(f"{name}", p.proc_head[1])
        p.procedures.append([f"{p.proc_head[0]}", p.commands])
        return p.procedures

    @_("empty")
    def procedures(self, p):
        return []

    @_("PROGRAM IS VAR declarations BEGIN commands END")
    def main(self, p):
        self.proc.createMain()
        self.proc.initVars("main", p.declarations)
        return ["main", p.commands]

    @_("PROGRAM IS BEGIN commands END")
    def main(self, p):
        self.proc.createProc("main")
        return ["main", p.commands]

    @_("commands command")
    def commands(self, p):
        if p.command is not None:
            p.commands.extend(p.command)
        return p.commands

    @_("command")
    def commands(self, p):
        return p.command

    @_("ID ASSIGN expression SCOLON")
    def command(self, p):
        return self.proc.a_assign(p.ID, p.expression)

    @_("IF condition THEN commands ELSE commands ENDIF")
    def command(self, p):
        if p.commands0 is None and p.commands1 is None:
            return None
        return self.proc.a_ife(p.condition, p.commands0, p.commands1)

    @_("IF condition THEN commands ENDIF")
    def command(self, p):
        if p.commands is None:
            return None
        return self.proc.a_if(p.condition, p.commands)

    @_("WHILE condition DO commands ENDWHILE")
    def command(self, p):
        if p.commands is None:
            return None
        return self.proc.a_while(p.condition, p.commands)

    @_("REPEAT commands UNTIL condition SCOLON")
    def command(self, p):
        if p.commands is None:
            return None
        return self.proc.a_until(p.condition, p.commands)

    @_("proc_head SCOLON")
    def command(self, p):
        return self.proc.a_proc(p.proc_head[0], p.proc_head[1])

    @_("READ ID SCOLON")
    def command(self, p):
        return self.proc.a_read(p.ID)

    @_("WRITE value SCOLON")
    def command(self, p):
        return self.proc.a_write(p.value)

    @_("ID LPAREN declarations_proc RPAREN")
    def proc_head(self, p):
        return (p.ID, p.declarations_proc)

    @_("declarations COMMA ID")
    def declarations(self, p):
        p.declarations.append(p.ID)
        return p.declarations

    @_("ID")
    def declarations(self, p):
        return [p.ID]

    @_("declarations_proc COMMA ID")
    def declarations_proc(self, p):
        p.declarations_proc.append(p.ID)
        return p.declarations_proc

    @_("ID")
    def declarations_proc(self, p):
        return [p.ID]

    @_("value ADD value")
    def expression(self, p):
        return ExpObject(OpType.ADD, p.value0, p.value1)

    @_("value SUB value")
    def expression(self, p):
        return ExpObject(OpType.SUB, p.value0, p.value1)

    @_("value MUL value")
    def expression(self, p):
        return ExpObject(OpType.MUL, p.value0, p.value1)

    @_("value DIV value")
    def expression(self, p):
        return ExpObject(OpType.DIV, p.value0, p.value1)

    @_("value MOD value")
    def expression(self, p):
        return ExpObject(OpType.MOD, p.value0, p.value1)

    @_("value EQ value")
    def condition(self, p):
        return ExpObject(OpType.EQ, p.value0, p.value1)

    @_("value NEQ value")
    def condition(self, p):
        return ExpObject(OpType.NEQ, p.value0, p.value1)

    @_("value GT value")
    def condition(self, p):
        return ExpObject(OpType.GT, p.value0, p.value1)

    @_("value LT value")
    def condition(self, p):
        return ExpObject(OpType.LT, p.value0, p.value1)

    @_("value GE value")
    def condition(self, p):
        return ExpObject(OpType.GE, p.value0, p.value1)

    @_("value LE value")
    def condition(self, p):
        return ExpObject(OpType.LE, p.value0, p.value1)

    @_("value")
    def expression(self, p):
        return p.value

    @_("NUMBER")
    def value(self, p):
        return ValueObject(ValueType.NUM, p.NUMBER)

    @_("ID")
    def value(self, p):
        return ValueObject(ValueType.VAR, p.ID)

    @_("LEXERR")
    def command(self, p):
        raise Exception("syntax error")
