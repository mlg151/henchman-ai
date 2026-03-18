"""Test lock behavior with async tasks - simpler version."""

import asyncio
import threading

async def test_threading_lock():
    """Test threading.Lock with async tasks."""
    print("Testing threading.Lock...")
    lock = threading.Lock()
    acquired = [False, False]
    
    async def task1():
        print("  task1: trying to acquire lock")
        with lock:
            print("  task1: acquired lock")
            acquired[0] = True
            await asyncio.sleep(0.1)
            print("  task1: releasing lock")
    
    async def task2():
        await asyncio.sleep(0.01)  # Let task1 acquire first
        print("  task2: trying to acquire lock")
        with lock:
            print("  task2: acquired lock")
            acquired[1] = True
            await asyncio.sleep(0.05)
            print("  task2: releasing lock")
    
    t1 = asyncio.create_task(task1())
    t2 = asyncio.create_task(task2())
    
    # Add timeout
    try:
        await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
        print("  Both tasks completed")
        print(f"  task1 acquired: {acquired[0]}, task2 acquired: {acquired[1]}")
    except asyncio.TimeoutError:
        print("  TIMEOUT! Deadlock!")
        return False
    
    return acquired[0] and acquired[1]

async def test_asyncio_lock():
    """Test asyncio.Lock with async tasks."""
    print("Testing asyncio.Lock...")
    lock = asyncio.Lock()
    acquired = [False, False]
    
    async def task1():
        print("  task1: trying to acquire lock")
        async with lock:
            print("  task1: acquired lock")
            acquired[0] = True
            await asyncio.sleep(0.1)
            print("  task1: releasing lock")
    
    async def task2():
        await asyncio.sleep(0.01)  # Let task1 acquire first
        print("  task2: trying to acquire lock")
        async with lock:
            print("  task2: acquired lock")
            acquired[1] = True
            await asyncio.sleep(0.05)
            print("  task2: releasing lock")
    
    t1 = asyncio.create_task(task1())
    t2 = asyncio.create_task(task2())
    
    try:
        await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
        print("  Both tasks completed")
        print(f"  task1 acquired: {acquired[0]}, task2 acquired: {acquired[1]}")
    except asyncio.TimeoutError:
        print("  TIMEOUT! Deadlock!")
        return False
    
    return acquired[0] and acquired[1]

async def main():
    print("=" * 50)
    result1 = await test_threading_lock()
    print(f"threading.Lock test: {'PASS' if result1 else 'FAIL/DEADLOCK'}")
    
    print("\n" + "=" * 50)
    result2 = await test_asyncio_lock()
    print(f"asyncio.Lock test: {'PASS' if result2 else 'FAIL/DEADLOCK'}")

if __name__ == "__main__":
    asyncio.run(main())