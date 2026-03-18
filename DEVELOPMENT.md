# Development Guide

## Code Quality Tools

This project uses multiple tools to ensure high code quality:

### **Ruff** - Fast Python Linter & Formatter
- **Linting**: `uv run ruff check .`
- **Auto-fix**: `uv run ruff check --fix .`
- **Formatting**: `uv run ruff format .`

### **MyPy** - Static Type Checker
- **Type checking**: `uv run mypy newrelic_mcp/`
- Catches type mismatches and improves code reliability
- Configured with strict settings (`disallow_untyped_defs`, `strict_equality`, `warn_unreachable`, etc.)

### **Pylint** - Additional Code Analysis
- **Code analysis**: `uv run pylint newrelic_mcp/`
- Detects code smells, complexity issues, and potential bugs

### **Pre-commit Hooks** (Recommended)
Automatically run quality checks before each commit:

```bash
# Install pre-commit hooks (one-time setup)
uv run pre-commit install

# Run all hooks manually
uv run pre-commit run --all-files
```

## Development Workflow

### **Quick Commands**
```bash
# Format code
uv run ruff format .

# Check all linting rules
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Run type checking
uv run mypy newrelic_mcp/

# Run tests
uv run pytest tests/

# Run all quality checks
uv run ruff check . && uv run mypy newrelic_mcp/ && uv run pylint newrelic_mcp/
```

### **Hatch Scripts**
Convenience scripts are defined in `pyproject.toml` under `[tool.hatch.envs.dev.scripts]`:
```bash
uv run hatch run dev:lint        # Run ruff, mypy, and pylint
uv run hatch run dev:format      # Format with ruff
uv run hatch run dev:test        # Run pytest
uv run hatch run dev:all-checks  # All checks including format verification
```

### **Testing**
Tests use `pytest` with `pytest-asyncio` for async test support. The `asyncio_mode = "auto"` setting in `pyproject.toml` means async test methods are detected automatically — no `@pytest.mark.asyncio` decorator needed.

```bash
# Run all tests
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_base_client.py

# Stop on first failure
uv run pytest tests/ -x -q
```

### **IDE Integration**

#### **IntelliJ/PyCharm**
1. Install Ruff plugin
2. Configure MyPy as external tool
3. Enable "Format on save" with Ruff

#### **VS Code** 
1. Install Ruff extension (`charliermarsh.ruff`)
2. Install Pylance for type checking
3. Add to settings.json:
```json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.linting.enabled": true,
    "ruff.enabled": true,
    "python.formatting.provider": "ruff"
}
```

## Configuration Files

- **`pyproject.toml`**: Ruff, MyPy, and Pylint configuration
- **`.pre-commit-config.yaml`**: Pre-commit hooks setup
- **Ruff settings**: Line length 120, Python 3.11+ target
- **MyPy settings**: Strict mode with `disallow_untyped_defs` and `strict_equality`

## Code Style Standards

### **Type Hints**
- Use modern Python 3.11+ syntax: `dict[str, Any]` instead of `Dict[str, Any]`
- Prefer `str | None` over `Optional[str]`
- Add type hints to new functions and methods

### **Code Organization**
- Keep functions focused and small
- Extract common logic to avoid duplication
- Use descriptive variable names (no single letters except for loops)
- Add docstrings for public APIs

### **Error Handling**
- Use exception chaining: `raise CustomError("message") from e`
- Prefer specific exception types over generic `Exception`
- Add meaningful error messages

## Future Improvements

Potential areas for further tooling improvements:

- Add `bandit` for security scanning
- Enable additional Ruff rule sets as the codebase matures
- Add test coverage reporting with `pytest-cov`