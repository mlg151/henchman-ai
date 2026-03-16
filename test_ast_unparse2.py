"""Test how ast.unparse handles very long function definitions."""
import ast
import textwrap

# Create a function with many parameters so it's definitely too long for one line
src = textwrap.dedent("""\
    @decorator1
    @decorator2(arg1, arg2, arg3)
    def very_long_function_name_with_many_characters(
        parameter1: VeryLongTypeNameThatMakesTheLineLong,
        parameter2: AnotherVeryLongTypeNameThatAlsoMakesItLonger,
        parameter3: YetAnotherExtremelyLongTypeNameForTestingPurposes,
        parameter4: TypeNameThatPushesItOverTheEdge,
    ) -> ReturnTypeThatIsAlsoVeryLongAndMakesTheSignatureExceedTypicalLineLength:
        return something
""")

tree = ast.parse(src)
func_node = tree.body[0]  # The FunctionDef node

print("ast.unparse result:")
unparsed = ast.unparse(func_node)
print(repr(unparsed))

print("\n" + "=" * 60 + "\n")
print("Lines from ast.unparse:")
for i, line in enumerate(unparsed.split('\n')):
    print(f"{i}: {repr(line)}")
    if len(line) > 100:
        print(f"   (length: {len(line)})")

print("\n" + "=" * 60 + "\n")
print("What _extract_signature would return:")
lines = unparsed.split('\n')
for line in lines:
    if line.strip().startswith(("def ", "async def ")):
        result = line[:120]
        print(f"Found: {repr(result)}")
        print(f"Length: {len(line)}, Truncated to: {len(result)}")
        if len(line) > 120:
            print("WARNING: Signature truncated!")
        break
else:
    print("No 'def' line found")