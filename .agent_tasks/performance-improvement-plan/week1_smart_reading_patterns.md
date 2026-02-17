# Smart File Reading Patterns for Agent Performance

## Problem Statement
Agents frequently re-read entire files or read more than needed, leading to:
1. **Context window waste**: Reading irrelevant sections
2. **Performance overhead**: Unnecessary file operations
3. **Cognitive load**: Processing more information than needed
4. **Timeout risks**: Large files exceeding context limits

## Solution: Targeted Reading Strategies

### Pattern 1: Initial Exploration (First Look)
**When to use**: When encountering a new file for the first time
**Goal**: Understand file structure and purpose

```python
# Read first 50 lines for overview
content = await read_file(path, start_line=1, end_line=50)

# Also check last 20 lines for recent changes
recent = await read_file(path, start_line=-20, end_line=-1)

# Look for key markers
if "__init__" in content:
    # It's a package init file
    pass
elif "class " in content and "def " in content:
    # It's a module with classes/functions
    pass
```

**Optimization**: Combine with grep for specific patterns
```python
# Check if file contains specific patterns
has_classes = await grep("^class ", path)
has_functions = await grep("^def ", path)
```

### Pattern 2: Error Analysis (Debugging)
**When to use**: When investigating an error at specific line
**Goal**: Understand context around error

```python
# Read lines around error (error_line ± 10)
context_start = max(1, error_line - 10)
context_end = error_line + 10
error_context = await read_file(
    path, 
    start_line=context_start, 
    end_line=context_end
)

# Also read function/class definition containing error
# Find containing scope
if "def " in lines_before_error:
    # Read from function start
    function_start = find_function_start(lines, error_line)
    function_code = await read_file(
        path,
        start_line=function_start,
        end_line=error_line + 5
    )
```

### Pattern 3: Function/Class Analysis
**When to use**: When examining specific functionality
**Goal**: Understand a specific function or class

```python
# First, find the function/class definition
definition_line = await find_definition(path, "function_name")

if definition_line:
    # Read the entire function/class
    # Estimate 50 lines for typical function
    function_code = await read_file(
        path,
        start_line=definition_line,
        end_line=definition_line + 50
    )
    
    # If function is longer, read in chunks
    # Look for next function/class definition or end of indentation
    next_def = await find_next_definition(path, definition_line)
    if next_def:
        function_code = await read_file(
            path,
            start_line=definition_line,
            end_line=next_def - 1
        )
```

### Pattern 4: Recent Changes Analysis
**When to use**: When checking what changed recently
**Goal**: Understand recent modifications

```python
# Read last 100 lines for recent activity
recent_content = await read_file(path, start_line=-100, end_line=-1)

# Look for recent imports, new functions, TODO comments
recent_imports = [line for line in recent_content.split('\n') 
                  if 'import ' in line and '# Added' in line]
                  
# Check git history for this file if available
git_history = await shell(f"git log -n 5 --oneline -- {path}")
```

### Pattern 5: Structure Analysis (Architecture)
**When to use**: When understanding file organization
**Goal**: Get high-level structure without details

```python
# Read only imports and class/function definitions
imports = await grep("^import |^from ", path)
classes = await grep("^class ", path)
functions = await grep("^def ", path)

# Read first line of each class/function for summary
summaries = []
for class_line in classes:
    class_name = class_line.split('class ')[1].split('(')[0]
    # Read next 2 lines for docstring or inheritance
    class_start = get_line_number(class_line)
    class_info = await read_file(path, start_line=class_start, end_line=class_start+2)
    summaries.append(f"Class: {class_name} - {class_info}")
```

### Pattern 6: Configuration Analysis
**When to use**: When reading config files (YAML, JSON, INI)
**Goal**: Extract specific configuration values

```python
# For YAML/JSON configs, read entire file (usually small)
if path.endswith(('.yaml', '.yml', '.json', '.toml')):
    content = await read_file(path)
    # Parse structure
    config = parse_config(content)
    
# For .env files, read specific variables
elif path.endswith('.env'):
    # Read entire file (small)
    content = await read_file(path)
    # Extract specific variable
    target_var = "DATABASE_URL"
    for line in content.split('\n'):
        if line.startswith(f"{target_var}="):
            value = line.split('=', 1)[1]
            break
```

### Pattern 7: Test File Analysis
**When to use**: When examining test files
**Goal**: Understand test structure and coverage

```python
# Read test class and method definitions
test_classes = await grep("^class Test", path)
test_methods = await grep("^    def test_", path)

# For specific test, read it and setup/teardown
test_line = await find_test_definition(path, "test_specific_function")
if test_line:
    # Read test method and its setup
    test_content = await read_file(
        path,
        start_line=test_line - 10,  # Include setup
        end_line=test_line + 30     # Include test body
    )
```

## Optimization Techniques

### 1. Caching Frequently Accessed Files
```python
# Maintain simple cache of recently read files
FILE_CACHE = {}
CACHE_SIZE = 10

async def smart_read_file(path: str, **kwargs):
    # Check cache first
    cache_key = f"{path}:{kwargs}"
    if cache_key in FILE_CACHE:
        return FILE_CACHE[cache_key]
    
    # Read file
    content = await read_file(path, **kwargs)
    
    # Update cache (LRU)
    if len(FILE_CACHE) >= CACHE_SIZE:
        # Remove oldest
        oldest = next(iter(FILE_CACHE))
        del FILE_CACHE[oldest]
    
    FILE_CACHE[cache_key] = content
    return content
```

### 2. Predictive Reading
```python
# Based on file type, predict what to read
FILE_TYPE_PATTERNS = {
    '.py': {
        'initial_lines': 50,
        'key_sections': ['imports', 'class_defs', 'main_function'],
        'skip_sections': ['docstrings', 'comments']
    },
    '.md': {
        'initial_lines': 100,
        'key_sections': ['headers', 'code_blocks'],
        'skip_sections': []
    },
    '.yaml': {
        'initial_lines': -1,  # Read all (config files are small)
        'key_sections': ['top_level_keys'],
        'skip_sections': []
    }
}
```

### 3. Sequential Reading with Context
```python
# Read file in logical chunks
async def read_file_chunked(path: str, chunk_size: int = 100):
    file_size = await get_file_size(path)
    chunks = []
    
    for start in range(1, file_size, chunk_size):
        end = min(start + chunk_size - 1, file_size)
        chunk = await read_file(path, start_line=start, end_line=end)
        chunks.append(chunk)
        
        # Process chunk and decide if more needed
        if found_what_we_need(chunk):
            break
    
    return '\n'.join(chunks)
```

## Decision Framework: What to Read When

### Decision Tree for File Reading

```
Is this the first time seeing this file?
├── Yes → Use Pattern 1 (Initial Exploration)
└── No → What's the purpose?
    ├── Debugging error → Pattern 2 (Error Analysis)
    ├── Understanding function → Pattern 3 (Function Analysis)
    ├── Checking recent changes → Pattern 4 (Recent Changes)
    ├── Architectural review → Pattern 5 (Structure Analysis)
    ├── Config review → Pattern 6 (Configuration Analysis)
    └── Test review → Pattern 7 (Test File Analysis)
```

### File Size Considerations
```
File Size < 100 lines → Read entire file
100 < Size < 1000 lines → Read targeted sections
Size > 1000 lines → ALWAYS use line ranges
Size > 10000 lines → Consider alternative approaches
```

## Common Anti-Patterns to Avoid

### ❌ Anti-Pattern 1: Reading Entire Large Files
```python
# BAD: Reading 10,000 line file completely
content = await read_file("large_log_file.txt")  # Will fail/be slow

# GOOD: Read only what's needed
error_context = await read_file("large_log_file.txt", start_line=-100, end_line=-1)
```

### ❌ Anti-Pattern 2: Repeated Full Reads
```python
# BAD: Reading same file multiple times
content1 = await read_file("config.py")  # First read
# ... some processing ...
content2 = await read_file("config.py")  # Same file again!

# GOOD: Read once, store in working memory
if "config.py" not in working_memory.recent_files:
    content = await read_file("config.py")
    update_working_memory({"recent_files": [{"path": "config.py", "content": content}]})
else:
    content = get_from_memory("config.py")
```

### ❌ Anti-Pattern 3: Reading Without Purpose
```python
# BAD: Reading file just because it exists
files = await glob("**/*.py")
for file in files:
    content = await read_file(file)  # Why? What are we looking for?

# GOOD: Have clear purpose before reading
# Looking for authentication-related code
auth_files = await grep("authenticate|auth|login", "src/", glob="*.py")
for file in auth_files:
    # Now read with purpose: find auth implementation
    content = await read_file(file, start_line=1, end_line=50)
```

## Performance Metrics

### Baseline Measurements (Before Optimization)
- Average file reads per task: 3.2
- Average lines read per file: 250
- Context window usage: 65%
- Time spent reading: 25% of task time

### Target Metrics (After Optimization)
- Average file reads per task: 1.3 (60% reduction)
- Average lines read per file: 80 (68% reduction)
- Context window usage: 40% (more efficient)
- Time spent reading: 10% of task time (60% reduction)

## Implementation Checklist

### Week 1 Goals
- [ ] Document all current file reading patterns
- [ ] Implement Pattern 1-3 for common use cases
- [ ] Add decision framework to prompts
- [ ] Create validation tests

### Week 2 Goals
- [ ] Implement Pattern 4-7
- [ ] Add caching mechanism
- [ ] Integrate with working memory
- [ ] Measure performance improvements

### Week 3 Goals
- [ ] Optimize based on metrics
- [ ] Add predictive reading
- [ ] Create training examples
- [ ] Refine decision framework

### Week 4 Goals
- [ ] Final optimization
- [ ] Comprehensive testing
- [ ] Documentation complete
- [ ] Rollout to all agents

## Example Scenarios

### Scenario 1: Debugging Test Failure
```
Test test_user_authentication fails at line 45 in test_auth.py

SMART APPROACH:
1. Read test_auth.py lines 35-55 (Pattern 2: Error Analysis)
2. Check imports at top of file (Pattern 1: Initial Exploration)
3. Read auth.py function being tested (Pattern 3: Function Analysis)
4. Check recent changes to auth.py (Pattern 4: Recent Changes)

Total lines read: ~120 lines
Traditional approach: ~500+ lines
Savings: 76%
```

### Scenario 2: Implementing New Feature
```
Add logging to data processing pipeline

SMART APPROACH:
1. Read pipeline.py structure (Pattern 5: Structure Analysis)
2. Read specific process_data() function (Pattern 3: Function Analysis)
3. Check config for logging settings (Pattern 6: Configuration Analysis)
4. Read existing tests for patterns (Pattern 7: Test File Analysis)

Total lines read: ~200 lines
Traditional approach: Read all related files (~800+ lines)
Savings: 75%
```

## Integration with Other Systems

### Working Memory Integration
```python
# After smart read, update working memory
async def smart_read_with_memory(path: str, purpose: str, **kwargs):
    content = await smart_read_file(path, **kwargs)
    
    update_working_memory({
        "recent_files": [{
            "path": path,
            "purpose": purpose,
            "lines_read": kwargs.get('end_line', 0) - kwargs.get('start_line', 0) + 1,
            "timestamp": datetime.now().isoformat()
        }]
    })
    
    return content
```

### Knowledge Graph Integration
```python
# Record reading patterns for learning
async def record_reading_pattern(file_type: str, pattern_used: str, efficiency: float):
    await kg_update(
        action="add_observation",
        entity_id="file-reading-patterns",
        observation=f"Used {pattern_used} for {file_type} with {efficiency:.1%} efficiency",
        source="smart_reading_system"
    )
```

## Conclusion

Smart file reading patterns can significantly improve agent performance by:
1. **Reducing context waste**: Reading only what's needed
2. **Improving efficiency**: Faster task completion
3. **Enabling larger projects**: Can work with bigger codebases
4. **Reducing errors**: More focused reading leads to better understanding

The key is to always have a clear purpose before reading and to use the appropriate pattern for that purpose.