# Running Unit Tests

## Prerequisites

Install test dependencies:

```bash
pip install pytest pytest-mock
```

## Run All Tests

From the repo root:

```bash
pytest
```

Or with verbose output:

```bash
pytest -v
```

## Run Specific Test

```bash
pytest tests/test_api_features.py::test_get_data_success -v
```

## What the Tests Cover

### Features Payload Configuration
- Building default and custom features payloads
- Zone number override
- Empty zones handling
- Multiple zones support

### API Read Operations
- Successful data retrieval with BSB and v2 endpoints
- Fallback to legacy PlantHome endpoint on error
- Custom features payload usage in legacy reads
- Data parsing and RemoconData object creation

### API Write Operations
- Setting DHW temperatures (comfort/reduced)
- Setting DHW mode
- Setting arbitrary data items via v2 API

### Error Handling
- Authentication errors
- Empty data responses
- Connection failures

### Feature Flag Combinations
- Multiple zones with different settings
- Preserving custom fields in payload

## No External Dependencies Required

These tests use mocked `requests.Session` objects, so they:
- Don't require actual Remocon-Net credentials
- Don't make real API calls
- Run entirely offline
- Complete in milliseconds

## Troubleshooting

If imports fail, ensure you're running from the repo root:

```bash
cd c:\Users\photo\source\repos\ha-remocon
pytest
```

If you get `ModuleNotFoundError: No module named 'custom_components'`, verify `conftest.py` is in the `tests/` directory.
