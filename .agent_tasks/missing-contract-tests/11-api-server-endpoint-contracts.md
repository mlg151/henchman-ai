# Missing Contract: Additional API Server Endpoints

**Severity:** Medium  
**Location:** `src/henchman/api/server.py`, `src/henchman/api/endpoints/` (health, remote, chat)

## The gap

The existing `test_api_contracts.py` covers:
- `GET /v1/health` → `HealthResponse` ✅
- `POST /v1/chat/completions` → `ChatResponse` ✅
- `POST /v1/chat/completions/stream` → SSE chunks ✅
- `POST /v1/remote/sessions` → `RemoteSessionResponse` ✅
- `POST /v1/oauth/authorize` → `OAuthAuthorizeResponse` ✅
- `POST /v1/oauth/token` → `OAuthTokenResponse` ✅

The following **server-level contracts are missing**:

### 1. Error response shape

The API error responses (raised by `HTTPException`) have no contract test.
FastAPI defaults produce `{"detail": "..."}` but custom error handling could
add `code`, `type` fields. A contract should exist for:

```jsonc
{
  "type": "object",
  "required": ["detail"],
  "properties": {
    "detail": {"type": "string"}
  }
}
```

### 2. Chat history endpoint

`POST /v1/chat/history` returns `list[ChatMessage]`. This endpoint is defined
in `chat.py` but has no contract test.

### 3. Clear history endpoint

`POST /v1/chat/history/clear` returns `dict[str, str]` ("ok" message). This
endpoint has no contract test.

### 4. API metrics endpoint

`GET /v1/metrics` is defined in `health.py` but may not be covered in the
contract test (confirmed only for `MetricsResponse` model shape, not the
endpoint integration).

### 5. API usage endpoint

`GET /v1/usage` — same as above.

## Recommended contract test

Add to `tests/contracts/test_api_contracts.py`:

```python
def test_error_response_matches_contract(contract_suite):
    """API error responses must conform to a predictable shape."""
    from henchman.api.server import app
    with TestClient(app) as client:
        # Send a malformed request
        response = client.post("/v1/chat/completions", json={})
    assert response.status_code == 422
    payload = response.json()
    # FastAPI's default validation error shape
    assert "detail" in payload


def test_chat_history_endpoint_matches_contract(contract_suite):
    """Chat history endpoint must return contract-compliant message list."""
    from henchman.api.server import app
    # Similar setup to test_chat_completion_endpoint_matches_contract
    ...


def test_clear_history_endpoint_matches_contract(contract_suite):
    """Clear history endpoint must return a contract-compliant response."""
    ...
```

## Priority

Medium — these are consumer-facing API contracts. Any change to error shapes
would break API clients without a contract guard.
