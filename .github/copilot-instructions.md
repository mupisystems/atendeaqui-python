# AtendeAqui Python SDK — Copilot Instructions

## Build & Test

```bash
# Install (with dev deps)
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_client.py

# Run a single test
pytest tests/test_client.py::TestOnboarding::test_get_structure
```

No linter is configured in the project yet.

## Architecture

The SDK is a thin HTTP wrapper around the AtendeAqui REST API.

```
AtendeAquiClient (src/atendeaqui/client.py)
├── HttpClient (_http.py)          — shared requests.Session, error handling
├── ClientsModule (clients/)       — client.clients.*
└── OnboardingModule (onboarding/) — client.onboarding.*
```

`AtendeAquiClient` requires at least one of `api_token` (Bearer token for admin endpoints) or `flow_key` (public UUID for onboarding endpoints). Both can be provided together.

`HttpClient` is the only transport layer. All modules receive it in their `__init__` and call `self._http.get/post/patch/put/delete(path, ...)`. It handles error parsing and maps API error codes to SDK exceptions via `ERROR_CODE_MAP` in `exceptions.py`.

## Key Conventions

### Models
All response models are plain `@dataclass` classes with a single `from_dict(cls, data: dict)` classmethod. They never raise — missing fields fall back to safe defaults (empty strings, `[]`, `{}`).

```python
@dataclass
class MyModel:
    field: str

    @classmethod
    def from_dict(cls, data: dict) -> MyModel:
        return cls(field=data.get('field', ''))
```

All model and module files use `from __future__ import annotations`.

### Adding a New Module
1. Create `src/atendeaqui/<module>/` with `__init__.py` (the module class) and `models.py`.
2. The module class takes `http: HttpClient` as its only required constructor arg. Add optional default params (e.g., `default_flow_key`) as keyword-only args.
3. Expose the module as a `@property` on `AtendeAquiClient` in `client.py`.
4. Export all public symbols from `src/atendeaqui/__init__.py`.

### Exception Hierarchy
All exceptions inherit from `AtendeAquiError(message, code, status_code, response)`. Specific codes are mapped in `exceptions.ERROR_CODE_MAP`. When adding new API error codes, add them to the map and create a new exception class if semantically distinct.

### Testing Pattern
Tests use the `responses` library to mock HTTP calls. Fixtures are in `tests/conftest.py`:

- `client` — `flow_key` only (public onboarding API)
- `admin_client` — `api_token` + `flow_key`
- `admin_only_client` — `api_token` only

All fixtures use `_base_url='https://test.atendeaqui.com.br/api'` (private param, for tests only). Mock the exact URL the module would call:

```python
@responses.activate
def test_something(self, client, mocked_responses):
    mocked_responses.add(responses.GET, f'{BASE_URL}/api/resource/', json={...})
    result = client.module.method()
    assert result.field == 'expected'
```

### API URL Structure
- Production: `https://api.atendeaqui.com.br/v1`
- Sandbox: `https://api.homolog.atendeaqui.com.br/v1`
- Paths use trailing slashes: `clients/`, `clients/{id}/`, `clients/{id}/team/`
