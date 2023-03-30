import re
from ProcObj import *
from enum import Enum


class Mode(Enum):
    REF = 0
    VAR = 1


class Variable:
    address: int
    mode: "Mode"
    isSet: bool

    def __init__(self, address, mode):
        self.address = address
        self.mode = mode
        self.isSet = False

    def refresh(self):
        self.isSet = True

    def check_init(self):
        if self.mode == Mode.REF:
            return True
        else:
            return self.isSet


class Procedure:
    def __init__(self, proc_name, cproc: "CProcessor"):
        self.symbols = {}
        self.params = []
        self.proc_no = cproc.getProcNo()
        self.__pname = proc_name
        self.__thisLabel = cproc.createLabel()
        self.__is_called = False
        self.__back = None
        self.__times_called = 0

    def inline(self):
        self.__is_called = False

    def getName(self):
        return self.__pname

    def getLabel(self):
        return self.__thisLabel

    def canCall(self, other_proc):
        return other_proc.proc_no < self.proc_no

    def getBackAdd(self):
        return self.__back.address

    def isCalled(self):
        return self.__is_called

    def call(self):
        self.__is_called = True
        self.__times_called += 1

    def getTimesCalled(self):
        return self.__times_called

    def initJumpBack(self, cproc):
        self.__back = Variable(cproc.getNewAddress(), Mode.VAR)

    def initVars(self, cproc, vars):
        for var in vars:
            if var in self.symbols:
                raise Exception("Redeclaration of a variable")
            self.symbols[var] = Variable(cproc.getNewAddress(), Mode.VAR)

    def initRefs(self, cproc, refs):
        for ref in refs:
            t = Variable(cproc.getNewAddress(), Mode.REF)
            self.symbols[ref] = t
            self.params.append(t)

    def touch_var(self, var):
        if var not in self.symbols:
            return False
        self.symbols[var].refresh()
        return True

    def check_evar(self, var):
        return var in self.symbols

    def check_ivar(self, var):
        if var not in self.symbols:
            return False
        return self.symbols[var].check_init()

    def get_var(self, var) -> "Variable":
        return self.symbols[var]


class CProcessor:
    __const_tag = "@#"
    __to_label = "TO#"
    __dest_label = "LBL#"
    __to_label_next = "TO#$"
    __max_const = 2**63 - 1

    def __init__(self):
        self.data = {}
        self.symbols_proc = {}
        self.__protected_add = 0
        self.__dataSection = []
        self.__label_no = 0
        self.__loop_depth = 0
        self.__proc_counter = 0
        self.__helper_reg = []
        self.__mul_label = None
        self.__outerMulIsUsed = False
        self.__div_label = None
        self.__outerDivIsUsed = False
        self.__mod_label = None
        self.__outerModIsUsed = False
        self.__no_divs = 0
        self.__no_mods = 0
        self.__no_muls = 0

    def getModLabel(self):
        if self.__mod_label is None:
            self.__mod_label = self.createLabel()
        return self.__mod_label

    def getMulLabel(self):
        if self.__mul_label is None:
            self.__mul_label = self.createLabel()
        return self.__mul_label

    def getDivLabel(self):
        if self.__div_label is None:
            self.__div_label = self.createLabel()
        return self.__div_label

    def getHelperReg(self, n):
        if len(self.__helper_reg) == n:
            self.__helper_reg.append(self.getNewAddress())
        elif len(self.__helper_reg) < n:
            raise Exception("Helper regiseter error")
        return self.__helper_reg[n]

    def getProcNo(self):
        self.__proc_counter += 1
        return self.__proc_counter

    def createMain(self):
        self.symbols_proc["main"] = Procedure("main", self)

    def createProc(self, name):
        self.symbols_proc[name] = Procedure(name, self)
        t = self.symbols_proc[name]
        t.initJumpBack(self)

    def initVars(self, name, vars):
        self.symbols_proc[name].initVars(self, vars)

    def initRefs(self, name, refs):
        self.symbols_proc[name].initRefs(self, refs)

    def getNewAddress(self):
        self.__protected_add += 1
        return self.__protected_add

    # asm
    def c_load(self, id: "str", sym_proc):
        if sym_proc.get_var(id).mode == Mode.VAR:
            return f"LOAD {sym_proc.get_var(id).address}"
        else:
            return f"LOADI {sym_proc.get_var(id).address}"

    def c_store(self, id: "str", sym_proc):
        if sym_proc.get_var(id).mode == Mode.VAR:
            return f"STORE {sym_proc.get_var(id).address}"
        else:
            return f"STOREI {sym_proc.get_var(id).address}"

    def c_add(self, id: "str", sym_proc):
        if sym_proc.get_var(id).mode == Mode.VAR:
            return f"ADD {sym_proc.get_var(id).address}"
        else:
            return f"ADDI {sym_proc.get_var(id).address}"

    def c_sub(self, id: "str", sym_proc):
        if sym_proc.get_var(id).mode == Mode.VAR:
            return f"SUB {sym_proc.get_var(id).address}"
        else:
            return f"SUBI {sym_proc.get_var(id).address}"

    #!asm
    # parse
    def a_read(self, id):
        return [("#read", id)]

    def b_read(self, id: str, sym_proc):
        if not sym_proc.check_evar(id):
            raise Exception(f"Undeclared variable {id}")
        sym_proc.touch_var(id)
        if sym_proc.get_var(id).mode == Mode.VAR:
            return [
                f"GET {sym_proc.get_var(id).address}",
            ]
        else:
            return [
                f"GET 0",
                f"STOREI {sym_proc.get_var(id).address}",
            ]

    def a_write(self, val):
        return [("#write", val)]

    def b_write(self, val: "ValueObject", sym_proc):
        if val.vType == ValueType.VAR:
            if not sym_proc.check_ivar(val.data):
                if self.__loop_depth == 0:
                    raise Exception(f"Uninitialized variable {val.data}")
                else:
                    print(f"WARINIG: {val.data} may be used before set")
            if sym_proc.get_var(val.data).mode == Mode.VAR:
                return [
                    f"PUT {sym_proc.get_var(val.data).address}",
                ]
            else:
                return [
                    f"LOADI {sym_proc.get_var(val.data).address}",
                    f"PUT 0",
                ]
        else:
            if self.__loop_depth == 0:
                return [
                    f"SET {val.data}",
                    f"PUT 0",
                ]
            else:
                return [
                    f"PUT {self.const_tag(val.data)}",
                ]

    def a_assign(self, id, val):
        return [("#assign", id, val)]

    def b_assign(self, id, val: "ValueObject", sym_proc):
        if not sym_proc.touch_var(id):
            raise Exception(f"Undeclared variable {id}")
        if id == val.data:
            return []
        if val.vType == ValueType.VAR:
            if not sym_proc.check_ivar(val.data):
                if self.__loop_depth == 0:
                    raise Exception(f"Uninitialized variable {val.data}")
                else:
                    print(f"WARINIG: {val.data} may be used before set")
            return [
                self.c_load(val.data, sym_proc),
                self.c_store(id, sym_proc),
            ]
        else:
            return [
                f"SET {val.data}",
                self.c_store(id, sym_proc),
            ]

    def b_assign_e(self, id, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.VAR and (not sym_proc.check_ivar(exp.left.data)):
            if self.__loop_depth == 0:
                raise Exception(f"Uninitialized variable {exp.left.data}")
            else:
                print(f"WARINIG: {exp.left.data} may be used before set")
        if exp.right.vType == ValueType.VAR and (
            not sym_proc.check_ivar(exp.right.data)
        ):
            if self.__loop_depth == 0:
                raise Exception(f"Uninitialized variable {exp.right.data}")
            else:
                print(f"WARINIG: {exp.right.data} may be used before set")
        if not sym_proc.touch_var(id):
            raise Exception(f"Undeclared variable {id}")
        exp.setDest(id)
        if exp.oType == OpType.ADD:
            return self.b_add(exp, sym_proc)
        elif exp.oType == OpType.SUB:
            return self.b_sub(exp, sym_proc)
        elif exp.oType == OpType.MUL:
            return self.b_mul(exp, sym_proc)
        elif exp.oType == OpType.DIV:
            return self.b_div(exp, sym_proc)
        elif exp.oType == OpType.MOD:
            return self.b_mod(exp, sym_proc)

    def b_add(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            v = int(exp.left.data) + int(exp.right.data)
            if v <= self.__max_const:
                return [
                    f"SET {v}",
                    self.c_store(exp.dest, sym_proc),
                ]
            else:
                if v % 2 == 0:
                    return [
                        f"SET {v // 2}",
                        f"ADD 0",
                        self.c_store(exp.dest, sym_proc),
                    ]
                else:
                    return [
                        f"SET {exp.left.data}",
                        self.c_store(exp.dest, sym_proc),
                        f"SET {exp.right.data}",
                        self.c_add(exp.dest, sym_proc),
                        self.c_store(exp.dest, sym_proc),
                    ]
        elif exp.left.vType == ValueType.NUM:
            if int(exp.left.data) == 0:
                if exp.right.data == exp.dest:
                    return []
                else:
                    return [
                        self.c_load(exp.right.data, sym_proc),
                        self.c_store(exp.dest, sym_proc),
                    ]
            else:
                return [
                    f"SET {exp.left.data}",
                    self.c_add(exp.right.data, sym_proc),
                    self.c_store(exp.dest, sym_proc),
                ]
        elif exp.right.vType == ValueType.NUM:
            if int(exp.right.data) == 0:
                if exp.left.data == exp.dest:
                    return []
                else:
                    return [
                        self.c_load(exp.left.data, sym_proc),
                        self.c_store(exp.dest, sym_proc),
                    ]
            else:
                return [
                    f"SET {exp.right.data}",
                    self.c_add(exp.left.data, sym_proc),
                    self.c_store(exp.dest, sym_proc),
                ]
        else:
            return [
                self.c_load(exp.left.data, sym_proc),
                self.c_add(exp.right.data, sym_proc),
                self.c_store(exp.dest, sym_proc),
            ]

    def b_sub(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            l = int(exp.left.data)
            r = int(exp.right.data)
            v = 0
            if r <= l:
                v = l - r
            return [
                f"SET {v}",
                self.c_store(exp.dest, sym_proc),
            ]
        elif exp.left.vType == ValueType.NUM:
            if int(exp.left.data) == 0:
                return [
                    f"SET 0",
                    self.c_store(exp.dest, sym_proc),
                ]
            else:
                return [
                    f"SET {exp.left.data}",
                    self.c_sub(exp.right.data, sym_proc),
                    self.c_store(exp.dest),
                ]
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0:
                if exp.left.data == exp.dest:
                    return []
                else:
                    return [
                        self.c_load(exp.left.data, sym_proc),
                        self.c_store(exp.dest, sym_proc),
                    ]
            i = self.const_tag(r)
            return [
                self.c_load(exp.left.data, sym_proc),
                f"SUB {i}",
                self.c_store(exp.dest, sym_proc),
            ]
        else:
            return [
                self.c_load(exp.left.data, sym_proc),
                self.c_sub(exp.right.data, sym_proc),
                self.c_store(exp.dest, sym_proc),
            ]

    def b_mul(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            v = int(exp.left.data) * int(exp.right.data)
            if v <= self.__max_const:
                return [
                    f"SET {v}",
                    self.c_store(exp.dest, sym_proc),
                ]
            else:
                if v // 2 <= self.__max_const:
                    if v % 2 == 0:
                        return [
                            f"SET {v // 2}",
                            f"ADD 0",
                            self.c_store(exp.dest, sym_proc),
                        ]
                    else:
                        t = v - (v // 2)
                        return [
                            f"SET {t}",
                            self.c_store(exp.dest, sym_proc),
                            f"SET {v // 2}",
                            self.c_add(exp.dest, sym_proc),
                            self.c_store(exp.dest, sym_proc),
                        ]
                else:
                    q = v // self.__max_const
                    r = v % self.__max_const
                    label_back = self.createLabel()
                    h0 = self.getHelperReg(0)
                    h1 = self.getHelperReg(1)
                    ret = self.getHelperReg(2)
                    back = self.getHelperReg(3)
                    self.__outerMulIsUsed = True
                    code = [
                        "SET 0",
                        f"STORE {ret}",
                        f"SET {self.to_label(label_back)}",
                        f"STORE {back}",
                        f"SET {self.__max_const}",
                        f"STORE {h0}",
                        f"SET {q}",
                        f"JUMP {self.to_label(self.getMulLabel())}",
                    ]
                    if r > 0:
                        code.extend(
                            [
                                f"SET {r} {self.dest_label(label_back)}",
                                f"ADD {ret}",
                                self.c_store(exp.dest, sym_proc),
                            ]
                        )
                    else:
                        code.extend(
                            [
                                f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(label_back)}",
                            ]
                        )
                    return code
        else:
            if exp.right.vType == ValueType.NUM:
                exp.right, exp.left = exp.left, exp.right
            if exp.left.vType == ValueType.NUM:
                l = int(exp.left.data)
                if l == 0:
                    return [
                        f"SET 0",
                        self.c_store(exp.dest, sym_proc),
                    ]
                elif l == 1:
                    if exp.right.data == exp.dest:
                        return []
                    else:
                        return [
                            self.c_load(exp.right.data, sym_proc),
                            self.c_store(exp.dest, sym_proc),
                        ]
                elif ((l & (l - 1)) == 0) and (
                    (l <= 2**16 and self.__no_muls > 0)
                    or (l <= 2**32 and self.__no_muls == 0)
                ):
                    t = [self.c_load(exp.right.data, sym_proc)]
                    while l > 1:
                        t.append("ADD 0")
                        l //= 2
                    t.append(self.c_store(exp.dest, sym_proc))
                    return t
                elif l == 3:
                    return [
                        self.c_load(exp.right.data, sym_proc),
                        "ADD 0",
                        self.c_add(exp.right.data, sym_proc),
                        self.c_store(exp.dest, sym_proc),
                    ]
                elif (
                    l < 2**11 and self.__no_muls > 0 and (l >> 2).bit_count() <= 3
                ) or (
                    l < 2**32 and self.__no_muls == 0 and (l >> 2).bit_count() <= 5
                ):
                    h0 = self.getHelperReg(0)
                    h1 = self.getHelperReg(1)
                    t = [
                        "SET 0",
                        f"STORE {h1}",
                        self.c_load(exp.right.data, sym_proc),
                    ]
                    while l > 0:
                        if l == 1:
                            t.append(f"ADD {h1}")
                            break
                        elif l % 2 == 1:
                            t.append(f"STORE {h0}")
                            t.append(f"ADD {h1}")
                            t.append(f"STORE {h1}")
                            t.append(f"LOAD {h0}")
                        t.append("ADD 0")
                        l //= 2
                    t.append(self.c_store(exp.dest, sym_proc))
                    return t
                else:
                    label_back = self.createLabel()
                    h0 = self.getHelperReg(0)
                    h1 = self.getHelperReg(1)
                    ret = self.getHelperReg(2)
                    back = self.getHelperReg(3)
                    self.__outerMulIsUsed = True
                    return [
                        "SET 0",
                        f"STORE {ret}",
                        f"SET {self.to_label(label_back)}",
                        f"STORE {back}",
                        self.c_load(exp.right.data, sym_proc),
                        f"STORE {h0}",
                        f"SET {l}",
                        f"JUMP {self.to_label(self.getMulLabel())}",
                        f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(label_back)}",
                    ]
            else:
                label_back = self.createLabel()
                h0 = self.getHelperReg(0)
                h1 = self.getHelperReg(1)
                ret = self.getHelperReg(2)
                back = self.getHelperReg(3)
                self.__outerMulIsUsed = True
                return [
                    "SET 0",
                    f"STORE {ret}",
                    f"SET {self.to_label(label_back)}",
                    f"STORE {back}",
                    self.c_load(exp.right.data, sym_proc),
                    f"STORE {h0}",
                    self.c_load(exp.left.data, sym_proc),
                    f"JUMP {self.to_label(self.getMulLabel())}",
                    f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(label_back)}",
                ]

    def b_div(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            v = int(exp.left.data) // int(exp.right.data)
            return [
                f"SET {v}",
                self.c_store(exp.dest, sym_proc),
            ]
        else:
            if exp.right.vType == ValueType.NUM:
                r = int(exp.right.data)
                if r == 0:
                    return [
                        "SET 0",
                        self.c_store(exp.dest, sym_proc),
                    ]
                elif r == 1:
                    if exp.dest == exp.left.data:
                        return []
                    else:
                        return [
                            self.c_load(exp.left.data, sym_proc),
                            self.c_store(exp.dest, sym_proc),
                        ]
                elif (r & (r - 1)) == 0:
                    t = [self.c_load(exp.left.data, sym_proc)]
                    while r > 1:
                        t.append("HALF")
                        r //= 2
                    t.append(self.c_store(exp.dest, sym_proc))
                    return t
                else:
                    self.__outerDivIsUsed = True
                    d = self.getHelperReg(0)
                    q = self.getHelperReg(1)
                    rem = self.getHelperReg(2)
                    od = self.getHelperReg(3)
                    back = self.getHelperReg(4)
                    back_label = self.createLabel()
                    return [
                        f"SET {self.to_label(back_label)}",
                        f"STORE {back}",
                        f"SET 0",
                        f"STORE {q}",
                        self.c_load(exp.left.data, sym_proc),
                        f"STORE {rem}",
                        f"SET {exp.right.data}",
                        f"STORE {d}",
                        f"STORE {od}",
                        f"JUMP {self.to_label(self.getDivLabel())}",
                        f"LOAD {q} {self.dest_label(back_label)}",
                        self.c_store(exp.dest, sym_proc),
                    ]
            elif exp.left.vType == ValueType.NUM:
                l = int(exp.left.data)
                if l == 0:
                    return [
                        "SET 0",
                        self.c_store(exp.dest, sym_proc),
                    ]
                elif l == 1:
                    skip_label = self.createLabel()
                    skip_label2 = self.createLabel()
                    return [
                        self.c_load(exp.right.data, sym_proc),
                        f"JZERO {self.to_label(skip_label)}",
                        "HALF",
                        f"JPOS {self.to_label(skip_label)}",
                        "SET 1",
                        f"JUMP {self.to_label(skip_label2)}",
                        f"SET 0 {self.dest_label(skip_label)}",
                        f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(skip_label2)}",
                    ]
                else:
                    self.__outerDivIsUsed = True
                    d = self.getHelperReg(0)
                    q = self.getHelperReg(1)
                    r = self.getHelperReg(2)
                    od = self.getHelperReg(3)
                    back = self.getHelperReg(4)
                    back_label = self.createLabel()
                    skip_zero = self.createLabel()
                    return [
                        f"SET {self.to_label(back_label)}",
                        f"STORE {back}",
                        f"SET 0",
                        f"STORE {q}",
                        f"SET {l}",
                        f"STORE {r}",
                        self.c_load(exp.right.data, sym_proc),
                        f"JZERO {self.to_label(skip_zero)}",
                        f"STORE {d}",
                        f"STORE {od}",
                        f"JUMP {self.to_label(self.getDivLabel())}",
                        f"LOAD {q} {self.dest_label(back_label)} {self.dest_label(skip_zero)}",
                        self.c_store(exp.dest, sym_proc),
                    ]
            else:
                self.__outerDivIsUsed = True
                d = self.getHelperReg(0)
                q = self.getHelperReg(1)
                r = self.getHelperReg(2)
                od = self.getHelperReg(3)
                back = self.getHelperReg(4)
                back_label = self.createLabel()
                skip_zero = self.createLabel()
                return [
                    f"SET {self.to_label(back_label)}",
                    f"STORE {back}",
                    f"SET 0",
                    f"STORE {q}",
                    self.c_load(exp.left.data, sym_proc),
                    f"STORE {r}",
                    self.c_load(exp.right.data, sym_proc),
                    f"JZERO {self.to_label(skip_zero)}",
                    f"STORE {d}",
                    f"STORE {od}",
                    f"JUMP {self.to_label(self.getDivLabel())}",
                    f"LOAD {q} {self.dest_label(back_label)} {self.dest_label(skip_zero)}",
                    self.c_store(exp.dest, sym_proc),
                ]

    def b_mod(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            v = int(exp.left.data) % int(exp.right.data)
            return [
                f"SET {v}",
                self.c_store(exp.dest, sym_proc),
            ]
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0 or r == 1:
                return [
                    "SET 0",
                    self.c_store(exp.dest, sym_proc),
                ]
            elif r == 2:
                skip1 = self.createLabel()
                skip2 = self.createLabel()
                return [
                    self.c_load(exp.left.data, sym_proc),
                    "HALF",
                    "ADD 0",
                    f"ADD {self.const_tag(1)}",
                    self.c_sub(exp.left.data, sym_proc),
                    f"JPOS {self.to_label(skip1)}",
                    "SET 1",
                    f"JUMP {self.to_label(skip2)}",
                    f"SET 0 {self.dest_label(skip1)}",
                    f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(skip2)}",
                ]
            else:
                if self.__no_divs == 0:
                    self.__outerModIsUsed = True
                    d = self.getHelperReg(0)
                    _ = self.getHelperReg(1)
                    rem = self.getHelperReg(2)
                    od = self.getHelperReg(3)
                    back = self.getHelperReg(4)
                    back_label = self.createLabel()
                    return [
                        f"SET {self.to_label(back_label)}",
                        f"STORE {back}",
                        self.c_load(exp.left.data, sym_proc),
                        f"STORE {rem}",
                        f"SET {r}",
                        f"STORE {d}",
                        f"STORE {od}",
                        f"JUMP {self.to_label(self.getModLabel())}",
                        f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(back_label)}",
                    ]
                else:
                    self.__outerDivIsUsed = True
                    d = self.getHelperReg(0)
                    _ = self.getHelperReg(1)
                    rem = self.getHelperReg(2)
                    od = self.getHelperReg(3)
                    back = self.getHelperReg(4)
                    back_label = self.createLabel()
                    return [
                        f"SET {self.to_label(back_label)}",
                        f"STORE {back}",  # q not set
                        self.c_load(exp.left.data, sym_proc),
                        f"STORE {rem}",
                        f"SET {exp.right.data}",
                        f"STORE {d}",
                        f"STORE {od}",
                        f"JUMP {self.to_label(self.getDivLabel())}",
                        f"LOAD {rem} {self.dest_label(back_label)}",
                        self.c_store(exp.dest, sym_proc),
                    ]
        elif exp.left.vType == ValueType.NUM:
            l = int(exp.left.data)
            if l == 0:
                return [
                    "SET 0",
                    self.c_store(exp.dest, sym_proc),
                ]
            else:
                if self.__no_divs == 0:
                    self.__outerModIsUsed = True
                    d = self.getHelperReg(0)
                    _ = self.getHelperReg(1)
                    rem = self.getHelperReg(2)
                    od = self.getHelperReg(3)
                    back = self.getHelperReg(4)
                    back_label = self.createLabel()
                    skip_zero = self.createLabel()
                    return [
                        f"SET {self.to_label(back_label)}",
                        f"STORE {back}",
                        f"SET {l}",
                        f"STORE {rem}",
                        self.c_load(exp.right.data, sym_proc),
                        f"JZERO {self.to_label(skip_zero)}",
                        f"STORE {d}",
                        f"STORE {od}",
                        f"JUMP {self.to_label(self.getModLabel())}",
                        f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(back_label)} {self.dest_label(skip_zero)}",
                    ]
                else:
                    self.__outerDivIsUsed = True
                    d = self.getHelperReg(0)
                    _ = self.getHelperReg(1)
                    rem = self.getHelperReg(2)
                    od = self.getHelperReg(3)
                    back = self.getHelperReg(4)
                    back_label = self.createLabel()
                    skip_zero = self.createLabel()
                    return [
                        f"SET {self.to_label(back_label)}",
                        f"STORE {back}",  # q not set
                        f"SET {l}",
                        f"STORE {rem}",
                        self.c_load(exp.right.data, sym_proc),
                        f"JZERO {self.to_label(skip_zero)}",
                        f"STORE {d}",
                        f"STORE {od}",
                        f"JUMP {self.to_label(self.getDivLabel())}",
                        f"LOAD {rem} {self.dest_label(back_label)}",
                        f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(skip_zero)}",
                    ]
        else:
            if self.__no_divs == 0:
                self.__outerModIsUsed = True
                d = self.getHelperReg(0)
                _ = self.getHelperReg(1)
                rem = self.getHelperReg(2)
                od = self.getHelperReg(3)
                back = self.getHelperReg(4)
                back_label = self.createLabel()
                skip_zero = self.createLabel()
                return [
                    f"SET {self.to_label(back_label)}",
                    f"STORE {back}",
                    self.c_load(exp.left.data, sym_proc),
                    f"STORE {rem}",
                    self.c_load(exp.right.data, sym_proc),
                    f"JZERO {self.to_label(skip_zero)}",
                    f"STORE {d}",
                    f"STORE {od}",
                    f"JUMP {self.to_label(self.getModLabel())}",
                    f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(back_label)} {self.dest_label(skip_zero)}",
                ]
            else:
                self.__outerDivIsUsed = True
                d = self.getHelperReg(0)
                _ = self.getHelperReg(1)
                rem = self.getHelperReg(2)
                od = self.getHelperReg(3)
                back = self.getHelperReg(4)
                back_label = self.createLabel()
                skip_zero = self.createLabel()
                return [
                    f"SET {self.to_label(back_label)}",
                    f"STORE {back}",  # q not set
                    self.c_load(exp.left.data, sym_proc),
                    f"STORE {rem}",
                    self.c_load(exp.right.data, sym_proc),
                    f"JZERO {self.to_label(skip_zero)}",
                    f"STORE {d}",
                    f"STORE {od}",
                    f"JUMP {self.to_label(self.getDivLabel())}",
                    f"LOAD {rem} {self.dest_label(back_label)}",
                    f"{self.c_store(exp.dest, sym_proc)} {self.dest_label(skip_zero)}",
                ]

    # result in p_0; a in p_0, b in helper regs 1; back in reg 3
    def outer_mul(self):
        one = self.const_tag(1)
        label_fin = self.createLabel()
        label_skip = self.createLabel()
        label_back = self.createLabel()
        h0 = self.getHelperReg(0)
        h1 = self.getHelperReg(1)
        ret = self.getHelperReg(2)
        back = self.getHelperReg(3)
        return [
            f"JZERO {self.to_label(label_fin)} {self.dest_label(label_back)} {self.dest_label(self.getMulLabel())} [mul]",
            f"STORE {h1}",
            "HALF",
            "ADD 0",
            f"ADD {one}",
            f"SUB {h1}",
            f"JPOS {self.to_label(label_skip)}",
            f"LOAD {h0}",
            f"ADD {ret}",
            f"STORE {ret}",
            f"LOAD {h0} {self.dest_label(label_skip)}",
            "ADD 0",
            f"STORE {h0}",
            f"LOAD {h1}",
            "HALF",
            f"JUMP {self.to_label(label_back)}",
            f"LOAD {ret} {self.dest_label(label_fin)}",
            f"JUMPI {back}",
        ]

    def outer_div(self):
        d = self.getHelperReg(0)
        q = self.getHelperReg(1)
        r = self.getHelperReg(2)
        od = self.getHelperReg(3)
        back = self.getHelperReg(4)
        loop1 = self.createLabel()
        loop2 = self.createLabel()
        out1 = self.createLabel()
        out2 = self.createLabel()
        skip1 = self.createLabel()
        return [
            f"ADD 0 {self.dest_label(loop1)} {self.dest_label(self.getDivLabel())} [div]",
            f"SUB {r}",
            f"JPOS {self.to_label(out1)}",
            f"LOAD {d}",
            "ADD 0",
            f"STORE {d}",
            f"JUMP {self.to_label(loop1)}",
            f"LOAD {d} {self.dest_label(out1)} {self.dest_label(loop2)}",
            f"SUB {r}",
            f"JPOS {self.to_label(skip1)}",
            f"LOAD {q}",
            f"ADD {self.const_tag(1)}",
            f"STORE {q}",
            f"LOAD {r}",
            f"SUB {d}",
            f"STORE {r}",
            f"LOAD {d} {self.dest_label(skip1)}",
            "HALF",
            f"STORE {d}",
            f"LOAD {od}",
            f"SUB {d}",
            f"JPOS {self.to_label(out2)}",
            f"LOAD {q}",
            "ADD 0",
            f"STORE {q}",
            f"JUMP {self.to_label(loop2)}",
            f"JUMPI {back} {self.dest_label(out2)}",
        ]

    # reminder in p_0
    def outer_mod(self):
        d = self.getHelperReg(0)
        _ = self.getHelperReg(1)
        r = self.getHelperReg(2)
        od = self.getHelperReg(3)
        back = self.getHelperReg(4)
        loop1 = self.createLabel()
        loop2 = self.createLabel()
        out1 = self.createLabel()
        out2 = self.createLabel()
        skip1 = self.createLabel()
        return [
            f"ADD 0 {self.dest_label(loop1)} {self.dest_label(self.getModLabel())} [mod]",
            f"SUB {r}",
            f"JPOS {self.to_label(out1)}",
            f"LOAD {d}",
            "ADD 0",
            f"STORE {d}",
            f"JUMP {self.to_label(loop1)}",
            f"LOAD {d} {self.dest_label(out1)} {self.dest_label(loop2)}",
            f"SUB {r}",
            f"JPOS {self.to_label(skip1)}",
            f"LOAD {r}",
            f"SUB {d}",
            f"STORE {r}",
            f"LOAD {d} {self.dest_label(skip1)}",
            "HALF",
            f"STORE {d}",
            f"LOAD {od}",
            f"SUB {d}",
            f"JPOS {self.to_label(out2)}",
            f"JUMP {self.to_label(loop2)}",
            f"LOAD {r} {self.dest_label(out2)}",
            f"JUMPI {back}",
        ]

    def b_cond(self, dest, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.VAR and (not sym_proc.check_ivar(exp.left.data)):
            if self.__loop_depth == 0:
                raise Exception(f"Uninitialized variable {exp.left.data}")
            else:
                print(f"WARINIG: {exp.left.data} may be used before set")
        if exp.right.vType == ValueType.VAR and (
            not sym_proc.check_ivar(exp.right.data)
        ):
            if self.__loop_depth == 0:
                raise Exception(f"Uninitialized variable {exp.right.data}")
            else:
                print(f"WARINIG: {exp.right.data} may be used before set")
        exp.dest = self.to_label(dest)
        if exp.oType == OpType.EQ:
            return self.b_eq(exp, sym_proc)
        elif exp.oType == OpType.NEQ:
            return self.b_neq(exp, sym_proc)
        elif exp.oType == OpType.GT:
            return self.b_gt(exp, sym_proc)
        elif exp.oType == OpType.LT:
            return self.b_lt(exp, sym_proc)
        elif exp.oType == OpType.GE:
            return self.b_ge(exp, sym_proc)
        elif exp.oType == OpType.LE:
            return self.b_le(exp, sym_proc)

    # jeśli fałsz: jump do dest (poza instrukcją warunkową); jeśli prawda: nic
    def b_eq(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            if int(exp.left.data) == int(exp.right.data):
                return ([], 1)
            else:
                return ([], 0)
        elif exp.left.vType == ValueType.NUM:
            l = int(exp.left.data)
            if l == 0:
                return (
                    [
                        self.c_load(exp.right.data, sym_proc),
                        f"JPOS {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(l)
            return (
                [
                    self.c_load(exp.right.data, sym_proc),
                    f"SUB {i}",
                    f"JPOS {exp.dest}",
                    f"LOAD {i}",
                    self.c_sub(exp.right.data, sym_proc),
                    f"JPOS {exp.dest}",
                ],
                -1,
            )
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0:
                return (
                    [
                        self.c_load(exp.left.data, sym_proc),
                        f"JPOS {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(r)
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    f"SUB {i}",
                    f"JPOS {exp.dest}",
                    f"LOAD {i}",
                    self.c_sub(exp.left.data, sym_proc),
                    f"JPOS {exp.dest}",
                ],
                -1,
            )
        else:
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    self.c_sub(exp.right.data, sym_proc),
                    f"JPOS {exp.dest}",
                    self.c_load(exp.right.data, sym_proc),
                    self.c_sub(exp.left.data, sym_proc),
                    f"JPOS {exp.dest}",
                ],
                -1,
            )

    def b_neq(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            if int(exp.left.data) == int(exp.right.data):
                return ([], 0)
            else:
                return ([], 1)
        elif exp.left.vType == ValueType.NUM:
            l = int(exp.left.data)
            if l == 0:
                return (
                    [
                        self.c_load(exp.right.data, sym_proc),
                        f"JZERO {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(l)
            true_label = self.createLabel()
            return (
                [
                    self.c_load(exp.right.data, sym_proc),
                    f"SUB {i}",
                    f"JPOS {self.to_label_next(true_label)}",
                    f"LOAD {i}",
                    self.c_sub(exp.right.data, sym_proc),
                    f"JZERO {exp.dest} {self.dest_label(true_label)}",
                ],
                -1,
            )
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0:
                return (
                    [
                        self.c_load(exp.left.data, sym_proc),
                        f"JZERO {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(r)
            true_label = self.createLabel()
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    f"SUB {i}",
                    f"JPOS {self.to_label_next(true_label)}",
                    f"LOAD {i}",
                    self.c_sub(exp.left.data, sym_proc),
                    f"JZERO {exp.dest} {self.dest_label(true_label)}",
                ],
                -1,
            )
        else:
            true_label = self.createLabel()
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    self.c_sub(exp.right.data, sym_proc),
                    f"JPOS {self.to_label_next(true_label)}",
                    self.c_load(exp.right.data, sym_proc),
                    self.c_sub(exp.left.data, sym_proc),
                    f"JZERO {exp.dest} {self.dest_label(true_label)}",
                ],
                -1,
            )

    def b_gt(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            if int(exp.left.data) > int(exp.right.data):
                return ([], 1)
            else:
                return ([], 0)
        elif exp.left.vType == ValueType.NUM:
            l = int(exp.left.data)
            if l == 0:
                return ([], 0)
            if l == 1:
                return (
                    [
                        self.c_load(exp.right.data, sym_proc),
                        f"JPOS {exp.dest}",
                    ],
                    -1,
                )
            return (
                [
                    f"SET {l}",
                    self.c_sub(exp.right.data, sym_proc),
                    f"JZERO {exp.dest}",
                ],
                -1,
            )
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0:
                return (
                    [
                        self.c_load(exp.left.data, sym_proc),
                        f"JZERO {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(r)
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    f"SUB {i}",
                    f"JZERO {exp.dest}",
                ],
                -1,
            )
        else:
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    self.c_sub(exp.right.data, sym_proc),
                    f"JZERO {exp.dest}",
                ],
                -1,
            )

    def b_lt(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            if int(exp.left.data) < int(exp.right.data):
                return ([], 1)
            else:
                return ([], 0)
        elif exp.left.vType == ValueType.NUM:
            l = int(exp.left.data)
            if l == 0:
                return (
                    [
                        self.c_load(exp.right.data, sym_proc),
                        f"JZERO {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(l)
            return (
                [
                    self.c_load(exp.right.data, sym_proc),
                    f"SUB {i}",
                    f"JZERO {exp.dest}",
                ],
                -1,
            )
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0:
                return ([], 0)
            if r == 1:
                return (
                    [
                        self.c_load(exp.left.data, sym_proc),
                        f"JPOS {exp.dest}",
                    ],
                    -1,
                )
            return (
                [
                    f"SET {r}",
                    self.c_sub(exp.left.data, sym_proc),
                    f"JZERO {exp.dest}",
                ],
                -1,
            )
        else:
            return (
                [
                    self.c_load(exp.right.data, sym_proc),
                    self.c_sub(exp.left.data, sym_proc),
                    f"JZERO {exp.dest}",
                ],
                -1,
            )

    def b_ge(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            if int(exp.left.data) >= int(exp.right.data):
                return ([], 1)
            else:
                return ([], 0)
        elif exp.left.vType == ValueType.NUM:
            l = int(exp.left.data)
            if l == 0:
                return (
                    [
                        self.c_load(exp.right.data, sym_proc),
                        f"JPOS {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(l)
            return (
                [
                    self.c_load(exp.right.data, sym_proc),
                    f"SUB {i}",
                    f"JPOS {exp.dest}",
                ],
                -1,
            )
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0:
                return ([], 1)
            if r == 1:
                return (
                    [
                        self.c_load(exp.left.data, sym_proc),
                        f"JZERO {exp.dest}",
                    ],
                    -1,
                )
            return (
                [
                    f"SET {r}",
                    self.c_sub(exp.left.data, sym_proc),
                    f"JPOS {exp.dest}",
                ],
                -1,
            )
        else:
            return (
                [
                    self.c_load(exp.right.data, sym_proc),
                    self.c_sub(exp.left.data, sym_proc),
                    f"JPOS {exp.dest}",
                ],
                -1,
            )

    def b_le(self, exp: "ExpObject", sym_proc):
        if exp.left.vType == ValueType.NUM and exp.right.vType == ValueType.NUM:
            if int(exp.left.data) <= int(exp.right.data):
                return ([], 1)
            else:
                return ([], 0)
        elif exp.left.vType == ValueType.NUM:
            l = int(exp.left.data)
            if l == 0:
                return ([], 1)
            if l == 1:
                return (
                    [
                        self.c_load(exp.right.data, sym_proc),
                        f"JZERO {exp.dest}",
                    ],
                    -1,
                )
            return (
                [
                    f"SET {l}",
                    self.c_sub(exp.right.data, sym_proc),
                    f"JPOS {exp.dest}",
                ],
                -1,
            )
        elif exp.right.vType == ValueType.NUM:
            r = int(exp.right.data)
            if r == 0:
                return (
                    [
                        self.c_load(exp.left.data, sym_proc),
                        f"JPOS {exp.dest}",
                    ],
                    -1,
                )
            i = self.const_tag(r)
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    f"SUB{i}",
                    f"JPOS {exp.dest}",
                ],
                -1,
            )
        else:
            return (
                [
                    self.c_load(exp.left.data, sym_proc),
                    self.c_sub(exp.right.data, sym_proc),
                    f"JPOS {exp.dest}",
                ],
                -1,
            )

    def a_if(self, cond, cmds):
        flabel = self.createLabel()
        return [("#if", flabel, cond, cmds)]

    def a_ife(self, cond, cmdst, cmdsf):
        flabel = self.createLabel()
        tlabel = self.createLabel()
        return [("#ife", flabel, tlabel, cond, cmdst, cmdsf)]

    def b_if(self, flabel, cond, cmds, sym_proc):
        cond_code, cond_stat = self.b_cond(flabel, cond, sym_proc)
        if cond_stat == 0:
            return []
        elif cond_stat == 1:
            return self.process_list_inner(cmds, sym_proc)
        else:
            return [("#if", flabel, cond_code, self.process_list_inner(cmds, sym_proc))]

    def b_ife(self, flabel, tlabel, cond, cmdst, cmdsf, sym_proc):
        cond_code, cond_stat = self.b_cond(flabel, cond, sym_proc)
        if cond_stat == 0:
            return self.process_list_inner(cmdsf, sym_proc)
        elif cond_stat == 1:
            return self.process_list_inner(cmdst, sym_proc)
        else:
            return [
                (
                    "#ife",
                    flabel,
                    tlabel,
                    cond_code,
                    self.process_list_inner(cmdst, sym_proc),
                    self.process_list_inner(cmdsf, sym_proc),
                )
            ]

    def a_while(self, cond, cmds):
        flabel = self.createLabel()
        blabel = self.createLabel()
        return [("#while", flabel, blabel, cond, cmds)]

    def b_while(self, flabel, blabel, cond, cmds, sym_proc):
        cond_code, cond_stat = self.b_cond(flabel, cond, sym_proc)
        if cond_stat == 0:
            return []
        elif cond_stat == 1:
            self.__loop_depth += 1
            t = [("#inf", blabel, self.process_list_inner(cmds, sym_proc), sym_proc)]
            self.__loop_depth -= 1
            return t
        else:
            self.__loop_depth += 1
            t = [
                (
                    "#while",
                    flabel,
                    blabel,
                    cond_code,
                    self.process_list_inner(cmds, sym_proc),
                )
            ]
            self.__loop_depth -= 1
            return t

    def a_until(self, cond, cmds):
        flabel = self.createLabel()
        return [("#until", flabel, cond, cmds)]

    def b_until(self, flabel, cond, cmds, sym_proc):
        cond_code, cond_stat = self.b_cond(flabel, cond, sym_proc)
        if cond_stat == 0:
            self.__loop_depth += 1
            t = [("#inf", flabel, self.process_list_inner(cmds, sym_proc), sym_proc)]
            self.__loop_depth -= 1
            return t
        elif cond_stat == 1:
            return self.process_list_inner(cmds, sym_proc)
        else:
            self.__loop_depth += 1
            t = [
                (
                    "#until",
                    flabel,
                    cond_code,
                    self.process_list_inner(cmds, sym_proc),
                )
            ]
            self.__loop_depth -= 1
            return t

    def a_proc(self, id, refs):
        if id not in self.symbols_proc:
            raise Exception(f"Unknown procedure: {id}")
        blabel = self.createLabel()
        return [("#proc", id, blabel, refs)]

    def b_proc(self, id, blabel, refs, sym_proc):
        self.symbols_proc[id].call()
        code = []
        proc = self.symbols_proc[id]
        for idx, r in enumerate(refs):
            proc.params[idx].isSet = sym_proc.symbols[r].isSet
            if not sym_proc.touch_var(r):
                raise Exception(f"Unknown variable {r}")
            if sym_proc.get_var(r).mode == Mode.VAR:
                code.append(f"SET {sym_proc.get_var(r).address}")
                code.append(f"STORE {proc.params[idx].address}")
            else:
                code.append(f"LOAD {sym_proc.get_var(r).address}")
                code.append(f"STORE {proc.params[idx].address}")
        code.append(f"SET {self.to_label(blabel)}")
        code.append(f"STORE {proc.getBackAdd()}")
        code.append(f"JUMP {self.to_label(proc.getLabel())}")
        return [("#proc", blabel, code)]

    #!parse
    # tree walk
    def tree_walk_inner(self, l, proc):
        for line in l:
            if line[0] == "#assign":
                if type(line[2]) is ExpObject:
                    if line[2].oType == OpType.DIV:
                        if line[2].right.vType == ValueType.NUM:
                            right = int(line[2].right.data)
                            if not (
                                (right & (right - 1)) == 0 or right == 0 or right == 1
                            ):
                                self.__no_divs += 1
                        else:
                            self.__no_divs += 1
                    elif line[2].oType == OpType.MOD:
                        if line[2].right.vType == ValueType.NUM:
                            right = int(line[2].right.data)
                            if right > 2:
                                self.__no_mods += 1
                        else:
                            self.__no_mods += 1
                    elif (
                        (line[2].oType == OpType.MUL)
                        and (line[2].left.vType == line[2].right.vType)
                        and (line[2].left.vType == ValueType.VAR)
                    ):
                        self.__no_muls += 1
            elif line[0] == "#if":
                self.tree_walk_inner(line[3], proc)
            elif line[0] == "#ife":
                self.tree_walk_inner(line[4], proc)
                self.tree_walk_inner(line[5], proc)
            elif line[0] == "#while":
                self.tree_walk_inner(line[4], proc)
            elif line[0] == "#until":
                self.tree_walk_inner(line[3], proc)
            elif line[0] == "#proc":
                if not proc.canCall(self.symbols_proc[line[1]]):
                    raise Exception(
                        f"{line[1]} cannot be called from inside {proc.getName()}"
                    )
                else:
                    p = self.symbols_proc[line[1]]
                    p.call()

    def tree_walk(self, l):
        proc = self.symbols_proc[l[0]]
        self.tree_walk_inner(l[1], proc)

    def tree_walk_proc(self, l):
        for proc in reversed(l):
            if self.symbols_proc[proc[0]].isCalled():
                self.tree_walk(proc)
        return self.h_filter_proc(l)

    def h_filter_proc(self, procs):
        filtered = []
        for proc in procs:
            if self.symbols_proc[proc[0]].isCalled():
                filtered.append(proc)
        return filtered

    #!tree walk
    # transform
    def process_list_procedures(self, l):
        called_proc = []
        for proc in reversed(l):
            name = proc[0]
            if self.symbols_proc[name].isCalled():
                t = self.process_list(proc)
                t.append(f"JUMPI {self.symbols_proc[name].getBackAdd()}")
                called_proc.append((t, self.symbols_proc[name].getLabel()))
        return called_proc

    def process_list(self, l):
        self.__loop_depth = 0
        proc_name = l[0]
        sym_proc = self.symbols_proc[proc_name]
        return self.process_list_inner(l[1], sym_proc)

    def process_list_inner(self, l, sym_proc):
        curr = []
        for line in l:
            if line[0] == "#assign":
                if type(line[2]) is ValueObject:
                    curr.extend(self.b_assign(line[1], line[2], sym_proc))
                else:
                    curr.extend(self.b_assign_e(line[1], line[2], sym_proc))
            elif line[0] == "#write":
                curr.extend(self.b_write(line[1], sym_proc))
            elif line[0] == "#read":
                curr.extend(self.b_read(line[1], sym_proc))
            elif line[0] == "#if":
                curr.extend(self.b_if(line[1], line[2], line[3], sym_proc))
            elif line[0] == "#ife":
                curr.extend(
                    self.b_ife(line[1], line[2], line[3], line[4], line[5], sym_proc)
                )
            elif line[0] == "#while":
                curr.extend(self.b_while(line[1], line[2], line[3], line[4], sym_proc))
            elif line[0] == "#until":
                curr.extend(self.b_until(line[1], line[2], line[3], sym_proc))
            elif line[0] == "#proc":
                if not sym_proc.canCall(self.symbols_proc[line[1]]):
                    raise Exception(
                        f"{line[1]} cannot be called from inside {sym_proc.getName()}"
                    )
                else:
                    curr.extend(self.b_proc(line[1], line[2], line[3], sym_proc))
        return curr

    #!transform
    # glue
    def createLabel(self):
        self.__label_no += 1
        return self.__label_no

    def dest_label(self, label):
        return f" [{self.__dest_label}{label}]"

    def to_label_next(self, label):
        return f" [{self.__to_label_next}{label}]"

    def to_label(self, label):
        return f" [{self.__to_label}{label}]"

    def fin_glue(self, code):
        out = []
        label = []
        setLabel = False
        for elem in code:
            if type(elem) is tuple:
                # (#if, flabel, cond, block)
                if elem[0] == "#if":
                    if setLabel:
                        for l in label:
                            elem[2][0] += self.dest_label(l)
                        setLabel = False
                        label = []
                    setLabel = True
                    label.append(elem[1])
                    out.extend(elem[2])
                    (block, bSetL, bLabel) = self.fin_glue(elem[3])
                    if bSetL:
                        label.extend(bLabel)
                    out.extend(block)
                # (#ife, flabel, tlabel, cond, tblock, fblock)
                elif elem[0] == "#ife":
                    if setLabel:
                        for l in label:
                            elem[3][0] += self.dest_label(l)
                        setLabel = False
                        label = []
                    out.extend(elem[3])
                    (block0, bSetL0, bLabel0) = self.fin_glue(elem[4])
                    if bSetL0:
                        label.extend(bLabel0)
                    out.extend(block0)
                    out.append(f"JUMP {self.to_label(elem[2])}")
                    (block1, bSetL1, bLabel1) = self.fin_glue(elem[5])
                    if bSetL1:
                        label.extend(bLabel1)
                    block1[0] += self.dest_label(elem[1])
                    out.extend(block1)
                    setLabel = True
                    label.append(elem[2])
                # (#inf, loop_label, block)
                elif elem[0] == "#inf":
                    (block, bSetL, bLabel) = self.fin_glue(elem[2])
                    if setLabel:
                        for l in label:
                            block[0] += self.dest_label(l)
                        setLabel = False
                        label = []
                    block[0] += self.dest_label(elem[1])
                    if bSetL:
                        for l in bLabel:
                            block[0] += self.dest_label(l)
                    label = []
                    setLabel = False
                    out.extend(block)
                    out.append(f"JUMP {self.to_label(elem[1])}")
                    break
                # (#while, flabel, back_label, cond, block)
                elif elem[0] == "#while":
                    if setLabel:
                        for l in label:
                            elem[3][0] += self.dest_label(l)
                        label = []
                        setLabel = False
                    elem[3][0] += self.dest_label(elem[2])
                    (block, bSetL, bLabel) = self.fin_glue(elem[4])
                    if bSetL:
                        for l in bLabel:
                            elem[3][0] += self.dest_label(l)
                    out.extend(elem[3])
                    out.extend(block)
                    out.append(f"JUMP {self.to_label(elem[2])}")
                    setLabel = True
                    label.append(elem[1])
                # (#until, back_label, cond, block)
                elif elem[0] == "#until":
                    (block, bSetL, bLabel) = self.fin_glue(elem[3])
                    if setLabel:
                        for l in label:
                            block[0] += self.dest_label(l)
                        setLabel = False
                        label = []
                    block[0] += self.dest_label(elem[1])
                    out.extend(block)
                    if bSetL:
                        for l in bLabel:
                            elem[2][0] += self.dest_label(l)
                    out.extend(elem[2])
                # (#proc, blabel, code)
                elif elem[0] == "#proc":
                    if setLabel:
                        for l in label:
                            elem[2][0] += self.dest_label(l)
                        setLabel = False
                        label = []
                    out.extend(elem[2])
                    label.append(elem[1])
                    setLabel = True
            else:
                if setLabel:
                    for l in label:
                        elem += self.dest_label(l)
                    setLabel = False
                    label = []
                out.append(elem)
        return (out, setLabel, label)

    def fin_glue_outer(self, code):
        (block, bSetL, bLabel) = self.fin_glue(code)
        block.append("HALT")
        if bSetL:
            for l in bLabel:
                block[-1] += self.dest_label(l)
        return block

    def fin_glue_proc(self, proc):
        out = []
        for (p, label) in proc:
            (code, _, _) = self.fin_glue(p)
            code[0] += self.dest_label(label)
            out.extend(code)
        return out

    def fin_merge(self, main, proc):
        if self.__outerMulIsUsed:
            main.extend(self.outer_mul())
        if self.__outerDivIsUsed:
            main.extend(self.outer_div())
        if self.__outerModIsUsed:
            main.extend(self.outer_mod())
        main.extend(proc)
        return main

    def substitute_consts(self, code):
        for idx, line in enumerate(code):
            for match in re.finditer(r"\[@\#[^\]]+\]", line):
                temp = line[match.start() + 3 : match.end() - 1]
                i = self.getConst(int(temp))
                code[idx] = line[: match.start()] + f"{i}" + line[(match.end() + 1) :]
        code = self.__dataSection + code
        return code

    def substitute_labels(self, code):
        labels = {}
        for idx, line in enumerate(code):
            for match in re.finditer(r"\[LBL\#[^\]]+\]", line):
                temp = line[match.start() + 5 : match.end() - 1]
                labels[int(temp)] = idx
        for idx, line in enumerate(code):
            for match in re.finditer(r"\[TO\#[^\]]+\]", line):
                next = 0
                if line[match.start() + 4] == "$":
                    next = 1
                temp = line[(match.start() + 4 + next) : match.end() - 1]
                code[idx] = (
                    line[: match.start()]
                    + f"{labels[int(temp)] + next} "
                    + line[match.start() :]
                )
        return code

    #!glue
    def createConst(self, num: int):
        i = self.getNewAddress()
        self.data[num] = i
        self.__dataSection.append(f"SET {num}")
        self.__dataSection.append(f"STORE {i} [const]")
        return i

    def getConst(self, num: int):
        if num in self.data:
            return self.data[num]
        else:
            return self.createConst(num)

    def const_tag(self, const: int):
        return f" [{self.__const_tag}{const}]"
