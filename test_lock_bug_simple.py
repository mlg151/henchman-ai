"""Simple demonstration of threading.Lock reentrancy issue."""

import asyncio
import threading
import time

def demonstrate_threading_lock_reentrancy():
    """Show that threading.Lock is reentrant in same thread."""
    print("=== Demonstrating threading.Lock reentrancy ===")
    
    lock = threading.Lock()
    events = []
    
    def in_lock():
        with lock:
            events.append("enter1")
            # Do some work
            time.sleep(0.01)
            events.append("exit1")
    
    # In same thread, we can acquire the lock again
    # This shows reentrancy
    print("1. First acquisition:")
    in_lock()
    print(f"   Events: {events}")
    
    print("\n2. Can acquire again in same thread (reentrant):")
    in_lock()
    print(f"   Events: {events}")
    
    # Now show the async problem
    print("\n=== Async problem with threading.Lock ===")
    
    async def async_demo():
        lock = threading.Lock()
        events = []
        
        async def task1():
            with lock:
                events.append("task1_enter")
                await asyncio.sleep(0.01)  # Yield to event loop
                events.append("task1_exit")
        
        async def task2():
            await asyncio.sleep(0.001)  # Let task1 acquire lock first
            with lock:
                events.append("task2_enter")
                events.append("task2_exit")
        
        await asyncio.gather(task1(), task2())
        return events
    
    events = asyncio.run(async_demo())
    print(f"Async events: {events}")
    
    # Check if task2 entered before task1 exited
    if "task2_enter" in events:
        task1_exit_idx = events.index("task1_exit")
        task2_enter_idx = events.index("task2_enter")
        
        if task2_enter_idx < task1_exit_idx:
            print("BUG CONFIRMED: task2 entered critical section before task1 exited!")
            print("This breaks mutual exclusion.")
        else:
            print("Unexpected: threading.Lock provided mutual exclusion in async context")
            print("This might be implementation-dependent or timing-specific.")

if __name__ == "__main__":
    demonstrate_threading_lock_reentrancy()