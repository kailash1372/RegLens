## Clean Code

Write production-quality, readable, maintainable Python following modern Python (3.11+) conventions.

* Follow PEP 8/257 and use clear, descriptive naming.
* Add type hints to public functions, methods, and reusable helpers.
* Keep functions focused; avoid duplication, deep nesting, magic values, hidden side effects, and unnecessary complexity.
* Use specific exceptions and proper error handling; never use bare `except`.
* Prefer modern Python idioms and built-in generics (`list[str]`, `X | None`, etc.).
* Add concise docstrings where they provide meaningful context; comments should explain **why**, not restate the code.
* Keep imports clean and remove dead/unused code.
* Run Ruff before considering work complete:

  ```bash
  ruff check . --fix
  ruff format .
  ```
* Do not suppress lint errors merely to make checks pass; fix the underlying issue unless suppression is genuinely justified.
