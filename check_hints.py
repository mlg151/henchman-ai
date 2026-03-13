import ast
import sys

def check_file(filename):
    with open(filename, "r") as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            missing_args = []
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    missing_args.append(arg.arg)
            
            for arg in node.args.kwonlyargs:
                if arg.annotation is None:
                    missing_args.append(arg.arg)
            
            if node.args.vararg and node.args.vararg.annotation is None:
                missing_args.append("*" + node.args.vararg.arg)
            
            if node.args.kwarg and node.args.kwarg.annotation is None:
                missing_args.append("**" + node.args.kwarg.arg)
                
            missing_return = node.returns is None
            
            if missing_args or missing_return:
                print(f"{filename}:{node.lineno}: Method '{node.name}' is missing hints for: {', '.join(missing_args)}" + (" and return type" if missing_return else ""))

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        check_file(arg)
