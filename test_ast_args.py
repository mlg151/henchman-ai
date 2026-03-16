"""Test AST argument nodes."""
import ast
import textwrap

src = textwrap.dedent("""\
    def func(
        pos_only: int, /,
        normal: str,
        *args: tuple,
        kw_only: float = 0.0,
        **kwargs: dict,
    ) -> None:
        pass
""")

tree = ast.parse(src)
func_node = tree.body[0]

print("Function node attributes:")
print(f"  args.posonlyargs: {func_node.args.posonlyargs}")
print(f"  args.args: {func_node.args.args}")
print(f"  args.vararg: {func_node.args.vararg}")
print(f"  args.kwonlyargs: {func_node.args.kwonlyargs}")
print(f"  args.kwarg: {func_node.args.kwarg}")

print("\nArgument details:")
for i, arg in enumerate(func_node.args.posonlyargs):
    print(f"  posonlyargs[{i}]: {arg.arg}, annotation: {arg.annotation}")
for i, arg in enumerate(func_node.args.args):
    print(f"  args[{i}]: {arg.arg}, annotation: {arg.annotation}")
if func_node.args.vararg:
    print(f"  vararg: {func_node.args.vararg.arg}, annotation: {func_node.args.vararg.annotation}")
for i, arg in enumerate(func_node.args.kwonlyargs):
    print(f"  kwonlyargs[{i}]: {arg.arg}, annotation: {arg.annotation}")
if func_node.args.kwarg:
    print(f"  kwarg: {func_node.args.kwarg.arg}, annotation: {func_node.args.kwarg.annotation}")