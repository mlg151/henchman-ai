"""Example module for testing test_gen tool."""

class Calculator:
    """A simple calculator class."""
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

async def async_divide(a: int, b: int) -> float:
    """Divide a by b asynchronously."""
    return a / b