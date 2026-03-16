"""Test how ast.unparse handles multi-line function definitions."""
import ast
import textwrap

src = textwrap.dedent("""\
    @decorator
    def func(
        x: int,
        y: int,
    ) -> int:
        return x + y
""")

tree = ast.parse(src)
func_node = tree.body[0]  # The FunctionDef node

print("Original source:")
print(repr(src))
print("\n" + "=" * 60 + "\n")

print("ast.unparse result:")
unparsed = ast.unparse(func_node)
print(repr(unparsed))

print("\n" + "=" * 60 + "\n")
print("Lines from ast.unparse:")
for i, line in enumerate(unparsed.split('\n')):
    print(f"{i}: {repr(line)}")

print("\n" + "=" * 60 + "\n")
print("What _extract_signature would return:")
lines = unparsed.split('\n')
for line in lines:
    if line.strip().startswith(("def ", "async def ")):
        print(f"Found: {repr(line[:120])}")
        break
else:
    print("No 'def' line found, would return: ", repr(lines[0][:120] if lines else "def func(...)"))