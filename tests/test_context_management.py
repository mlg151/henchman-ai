"""Validation tests for performance improvement plan context management.

These tests verify that the performance improvement plan guidelines in
.github/copilot-instructions.md are properly structured and complete.
"""

from pathlib import Path


class TestPerformanceImprovementPlanGuidelines:
    """Test that performance improvement guidelines are properly documented."""

    def setup_method(self):
        """Load copilot instructions for testing."""
        self.copilot_path = Path(__file__).parent.parent / ".github" / "copilot-instructions.md"
        with open(self.copilot_path, encoding='utf-8') as f:
            self.content = f.read()

    def test_working_memory_template_exists(self):
        """Verify working memory template is documented."""
        # Check for working memory section
        assert "working_memory:" in self.content, "Working memory template not found"

        # Check for key working memory fields
        required_fields = [
            "current_task:",
            "recent_files:",
            "active_context:",
            "decisions_made:",
            "completed_steps:",
            "next_actions:",
            "insights_gained:",
            "problems_encountered:"
        ]

        for field in required_fields:
            assert field in self.content, f"Required field {field} not found in working memory template"

    def test_smart_file_reading_patterns_exist(self):
        """Verify smart file reading patterns are documented."""
        # Check for smart file reading section
        assert "Smart File Reading Strategies" in self.content, "Smart file reading section not found"

        # Check for specific patterns mentioned in documentation
        pattern_indicators = [
            "Pattern 1: Initial Exploration",
            "Pattern 2: Error Analysis",
            "Pattern 3: Function/Class Analysis",
            "Pattern 4: Recent Changes",
            "Pattern 5: Structure Analysis",
            "File Size Guidelines"
        ]

        # At least some of these should be present
        pattern_count = sum(1 for pattern in pattern_indicators if pattern in self.content)
        assert pattern_count >= 3, f"Expected at least 3 smart file reading patterns, found {pattern_count}"

    def test_verification_requirements_exist(self):
        """Verify verification requirements for working memory are documented."""
        verification_indicators = [
            "✅ **Before reading a file**:",
            "✅ **After each action**:",
            "✅ **Every 5 tool calls**:",
            "✅ **Task completion**:",
            "✅ **Metrics tracking**:"
        ]

        # Count verification requirements
        verification_count = sum(1 for indicator in verification_indicators if indicator in self.content)
        assert verification_count >= 3, f"Expected at least 3 verification requirements, found {verification_count}"

    def test_file_size_guidelines_exist(self):
        """Verify file size guidelines are documented."""
        # Check for file size guidelines section
        size_guidelines_section = False

        # Look for the file size guidelines pattern
        lines = self.content.split('\n')
        for i, line in enumerate(lines):
            if "File Size Guidelines" in line or "file size guidelines" in line.lower():
                # Check next few lines for size ranges
                context = '\n'.join(lines[i:i+10])
                if any(size_indicator in context.lower() for size_indicator in ["< 100 lines", "100-500", "500-1000", "> 1000", "> 10000"]):
                    size_guidelines_section = True
                    break

        assert size_guidelines_section, "File size guidelines not found or incomplete"

    def test_structured_thinking_protocol_exists(self):
        """Verify structured thinking protocol is documented."""
        # Check for thinking protocol section
        assert "THINKING PROTOCOL:" in self.content, "Thinking protocol not found"

        # Check for phase indicators
        phase_indicators = [
            "## Phase 1: Problem Analysis",
            "## Phase 2: Context Gathering",
            "## Phase 3: Solution Design",
            "## Phase 4: Execution Planning"
        ]

        phase_count = sum(1 for phase in phase_indicators if phase in self.content)
        assert phase_count >= 2, f"Expected at least 2 thinking protocol phases, found {phase_count}"

    def test_delegation_optimization_exists(self):
        """Verify delegation optimization guidelines are documented."""
        # Check for delegation decision matrix
        assert "Delegation Decision Matrix" in self.content, "Delegation decision matrix not found"

        # Check for delegation checklist
        assert "Delegation Checklist" in self.content, "Delegation checklist not found"

        # Check for specialist roles in matrix
        specialist_roles = ["Planner", "Explorer", "Engineer"]
        role_count = sum(1 for role in specialist_roles if role in self.content and "When to Delegate" in self.content)
        assert role_count >= 2, f"Expected at least 2 specialist roles in delegation matrix, found {role_count}"

    def test_performance_metrics_tracking_exists(self):
        """Verify performance metrics tracking is documented."""
        # Check for performance metrics section
        assert "Performance Metrics Dashboard" in self.content, "Performance metrics dashboard not found"

        # Check for key metric categories
        metric_categories = [
            "Efficiency Metrics",
            "Quality Metrics",
            "Target Performance Metrics"
        ]

        category_count = sum(1 for category in metric_categories if category in self.content)
        assert category_count >= 2, f"Expected at least 2 metric categories, found {category_count}"

    def test_anti_patterns_documented(self):
        """Verify common anti-patterns are documented."""
        # Look for anti-pattern indicators
        anti_pattern_indicators = [
            "❌",
            "Anti-Pattern",
            "anti-pattern",
            "Common Anti-Patterns"
        ]

        indicator_count = sum(1 for indicator in anti_pattern_indicators if indicator in self.content)
        assert indicator_count >= 2, f"Expected at least 2 anti-pattern indicators, found {indicator_count}"

    def test_pre_flight_checklists_exist(self):
        """Verify pre-flight checklists are documented."""
        # Check for pre-flight checklists section
        assert "Pre-flight Checklists" in self.content, "Pre-flight checklists section not found"

        # Check for specific checklist types
        checklist_types = [
            "before_tests",
            "before_file_modification",
            "before_delegation"
        ]

        # Look for checklist headers
        checklist_count = 0
        for checklist in checklist_types:
            if f"**Before {checklist.replace('_', ' ')}**" in self.content or \
               f"{checklist.replace('_', ' ').title()}" in self.content:
                checklist_count += 1

        assert checklist_count >= 1, f"Expected at least 1 pre-flight checklist, found {checklist_count}"

    def test_tool_combination_patterns_exist(self):
        """Verify tool combination patterns are documented."""
        # Check for tool combination patterns section
        assert "Tool Combination Patterns" in self.content, "Tool combination patterns section not found"

        # Check for specific pattern types
        pattern_types = [
            "Research Task Pattern",
            "Debugging Task Pattern",
            "Implementation Task Pattern"
        ]

        pattern_count = sum(1 for pattern in pattern_types if pattern in self.content)
        assert pattern_count >= 2, f"Expected at least 2 tool combination patterns, found {pattern_count}"


class TestPatternsLearningDatabase:
    """Test that patterns learning database is properly structured."""

    def test_patterns_directory_exists(self):
        """Verify patterns directory exists."""
        patterns_dir = Path(__file__).parent.parent / ".agent_tasks" / "patterns"
        assert patterns_dir.exists(), "Patterns directory does not exist"
        assert patterns_dir.is_dir(), "Patterns path is not a directory"

    def test_pattern_files_exist(self):
        """Verify all required pattern files exist."""
        patterns_dir = Path(__file__).parent.parent / ".agent_tasks" / "patterns"
        required_files = [
            "successful_approaches.md",
            "common_errors.md",
            "tool_combinations.md",
            "debugging_patterns.md",
            "decision_frameworks.md",
            "README.md"
        ]

        missing_files = []
        for file in required_files:
            if not (patterns_dir / file).exists():
                missing_files.append(file)

        assert len(missing_files) == 0, f"Missing pattern files: {missing_files}"

    def test_pattern_files_have_content(self):
        """Verify pattern files have meaningful content."""
        patterns_dir = Path(__file__).parent.parent / ".agent_tasks" / "patterns"
        pattern_files = [
            "successful_approaches.md",
            "common_errors.md",
            "tool_combinations.md",
            "debugging_patterns.md",
            "decision_frameworks.md"
        ]

        for file in pattern_files:
            file_path = patterns_dir / file
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Check file has reasonable length (not empty)
            assert len(content) > 100, f"Pattern file {file} appears too short"
            # Check for pattern structure indicators
            # Different files may use different formats:
            # - Pattern files use "## Pattern:" or "**When to use**"
            # - Error files use "## Error" or "**Description**"
            # - Tool combination files use pattern names
            assert "## Pattern:" in content or "**When to use**" in content or \
                   "**Steps**:" in content or "**Success Rate**:" in content or \
                   "## Error" in content or "**Description**:" in content or \
                   "Pattern:" in content or "Sequence:" in content, \
                   f"Pattern file {file} doesn't follow expected format"
