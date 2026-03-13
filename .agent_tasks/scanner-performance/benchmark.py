#!/usr/bin/env python3
"""Benchmark the scanner performance."""

import time
from pathlib import Path
from tempfile import TemporaryDirectory

from henchman.knowledge.scanner import scan_repository
from henchman.knowledge.store import KnowledgeStore


def create_test_repo(num_files: int, imports_per_file: int = 3) -> Path:
    """Create a test repository with many Python files."""
    import subprocess
    
    with TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir) / "test_repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        
        # Create package structure
        src = repo / "src"
        src.mkdir()
        
        # Create many Python files with imports
        for i in range(num_files):
            file_path = src / f"module_{i:04d}.py"
            imports = [j for j in range(imports_per_file) if j != i]
            import_lines = "\n".join([f"import module_{j:04d}" for j in imports[:imports_per_file]])
            
            content = f'''"""Module {i}."""
{import_lines}

class Class{i}:
    """Class {i}."""
    pass

def func_{i}():
    """Function {i}."""
    pass
'''
            file_path.write_text(content)
        
        # Stage all files
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        
        # Return the repo path (TemporaryDirectory will clean up)
        return repo


def benchmark_scanner(num_files: int = 100) -> None:
    """Run performance benchmark."""
    print(f"Creating test repository with {num_files} files...")
    repo = create_test_repo(num_files)
    
    print(f"Running scanner benchmark...")
    store = KnowledgeStore(git_root=repo, base_dir=Path("/tmp/benchmark_kg"))
    
    # Time the scan
    start_time = time.time()
    processed = scan_repository(store, repo, incremental=False)
    end_time = time.time()
    
    elapsed = end_time - start_time
    print(f"Processed {processed} files in {elapsed:.2f} seconds")
    print(f"Average: {elapsed/processed:.4f} seconds per file")
    
    # Clean up
    import shutil
    if Path("/tmp/benchmark_kg").exists():
        shutil.rmtree("/tmp/benchmark_kg")


if __name__ == "__main__":
    # Run with different sizes
    for num_files in [10, 50, 100]:
        print(f"\n{'='*60}")
        print(f"Benchmark with {num_files} files")
        print('='*60)
        benchmark_scanner(num_files)