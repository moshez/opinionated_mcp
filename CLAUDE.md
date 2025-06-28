# Claude Development Guidance

This file contains important guidance for AI assistants working on this codebase.

## Code Quality and Testing Requirements

### Test Coverage
- **Target: 100% test coverage** - No exceptions
- Use `# pragma: no cover` only for functions with:
  - No branches or loops
  - No internal functions/classes
  - Simple, straightforward execution paths
- If code is "complex to test", refactor it to make it testable rather than accepting lower coverage
- **Avoid using `# pragma: no cover` unless it's impossible to test. If it's merely complicated, do the right thing.**

### Testing Framework
- Use `virtue` test framework (unittest-style with Twisted)
- Use `hamcrest` matchers for assertions
- Import from top level, never inside functions
- All tests must pass before completion

### Code Organization
- Prefer editing existing files over creating new ones
- Separate concerns into logical modules
- Don't create documentation files unless explicitly requested
- Follow existing code conventions and patterns

### Dependencies and Build
- Update `pyproject.toml` with all required dependencies
- Regenerate requirements using `nox -e refresh_deps` 
- Run tests with `nox -r -e tests-3.12`
- Handle dependency installation before running tests

### Development Process
- Use TodoWrite tool to plan and track multi-step tasks
- Mark todos as completed immediately after finishing (don't batch)
- For complex tasks, break into smaller, trackable components
- Always run lint/typecheck commands if available

## Key Principles

1. **Do what has been asked; nothing more, nothing less**
2. **Always prefer editing existing files to creating new ones** 
3. **Never proactively create documentation files**
4. **Testability is a design requirement, not a nice-to-have**
5. **100% coverage means refactoring untestable code, not accepting lower coverage**
6. **Use logging library instead of print statements for proper application logging**

## Testing Patterns

- Mock external dependencies (httpx, uvicorn, etc.)
- Test both success and failure paths
- Use async/await properly in tests
- Test decorators by calling them directly
- Extract complex logic into separate, testable functions when needed

## Commands Reference

```bash
# Regenerate dependencies
cd src/opinionated_mcp && nox -e refresh_deps

# Run tests
cd src/opinionated_mcp && nox -r -e tests-3.12

# Run lint
cd src/opinionated_mcp && nox -r -e lint

# Run mypy type checking
cd src/opinionated_mcp && nox -r -e mypy

# Build documentation
cd src/opinionated_mcp && nox -r -e docs

# Apply black formatting (if lint fails)
cd src/opinionated_mcp && /opt/kalyke/homedir/src/opinionated_mcp/build/nox/lint/bin/black src/ noxfile.py

# Check specific command patterns
cd /path && command  # Correct
cd /path; command    # Also acceptable
cd /path && command  # Preferred for clarity
```