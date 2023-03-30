from CLexer import CLexer
from CParser import CParser
import sys


def main():
    inFile = open(sys.argv[1], "r")
    inData = inFile.read()
    inFile.close()
    lexer = CLexer()
    parser = CParser()
    try:
        result = parser.parse(lexer.tokenize(inData))
        result = "\n".join(result)
        outFile = open(sys.argv[2], "w")
        outFile.write(result)
        outFile.close()
    except TypeError as e:
        print("Compilation failed!")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
