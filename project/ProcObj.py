from enum import Enum


class ValueType(Enum):
    NUM = 0
    VAR = 1


class OpType(Enum):
    ADD = 0
    SUB = 1
    MUL = 2
    DIV = 3
    MOD = 4
    EQ = 5
    NEQ = 6
    GT = 7
    LT = 8
    GE = 9
    LE = 10


class ValueObject:
    vType: "ValueType"

    def __init__(self, t: "ValueType", data):
        self.vType = t
        self.data = data

    def __str__(self) -> str:
        return str(self.data)


class ExpObject:
    oType: "OpType"

    def __init__(self, t: "OpType", left, right, dest=None):
        self.oType = t
        self.left = left
        self.right = right
        self.dest = dest

    def setDest(self, dest):
        self.dest = dest
