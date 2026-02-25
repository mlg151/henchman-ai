# Phase 2.3: API Server Mode Implementation

## Overview
Implement a REST API server mode for Henchman-AI to enable programmatic access and integration with other tools.

## Requirements from Roadmap
**Problem**: CLI-only limits integration possibilities.

**Features**:
- REST API for programmatic access
- WebSocket for real-time streaming
- Authentication (API keys, OAuth)
- Rate limiting and quotas
- OpenAPI/Swagger documentation

**Implementation**:
- Use FastAPI for REST endpoints
- Add `henchman serve` command
- Implement API key management
- Create client libraries (Python, JavaScript)

**Success Metrics**:
- 100+ API users within 3 months
- 5+ integrations with other tools
- API uptime: 99.9%

## Current Status
- No API server implementation exists
- Need to add FastAPI dependency
- Need to design API endpoints
- Need to implement authentication and rate limiting

## Architecture Design

### 1. Server Structure
```
src/henchman/api/
├── __init__.py
├── server.py          # FastAPI app and main server logic
├── endpoints/
│   ├── __init__.py
│   ├── chat.py       # Chat completion endpoints
│   ├── tools.py      # Tool management endpoints
│   ├── sessions.py   # Session management endpoints
│   └── health.py     # Health check endpoints
├── auth.py           # Authentication middleware
├── rate_limit.py     # Rate limiting middleware
├── models.py         # Pydantic request/response models
└── client.py         # Python client library
```

### 2. API Endpoints

#### Chat Endpoints
- `POST /v1/chat/completions` - Chat completion (streaming and non-streaming)
- `POST /v1/chat/completions/stream` - WebSocket streaming endpoint
- `GET /v1/chat/history` - Get conversation history
- `DELETE /v1/chat/history` - Clear conversation history

#### Tool Endpoints
- `GET /v1/tools` - List available tools
- `POST /v1/tools/execute` - Execute a tool
- `GET /v1/tools/{tool_name}/schema` - Get tool schema

#### Session Endpoints
- `GET /v1/sessions` - List sessions
- `POST /v1/sessions` - Create session
- `GET /v1/sessions/{session_id}` - Get session
- `PUT /v1/sessions/{session_id}` - Update session
- `DELETE /v1/sessions/{session_id}` - Delete session

#### Health & Metrics
- `GET /v1/health` - Health check
- `GET /v1/metrics` - Performance metrics
- `GET /v1/usage` - Token usage and costs

### 3. Authentication
- API key authentication via header: `X-API-Key: <key>`
- Support for multiple API keys with different permissions
- API key generation and revocation
- Optional OAuth2 support for future

### 4. Rate Limiting
- Per-API key rate limiting
- Configurable limits (requests per minute/hour/day)
- Burst allowance
- Rate limit headers in responses

### 5. WebSocket Support
- Real-time streaming for chat completions
- Bi-directional communication for tool execution
- Connection management and heartbeats

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Add FastAPI and related dependencies
2. Create basic server structure
3. Implement `henchman serve` command
4. Add health check endpoint
5. Basic authentication middleware

### Phase 2: Core Endpoints (Week 2)
1. Implement chat completion endpoints
2. Add tool execution endpoints
3. Create session management endpoints
4. Add WebSocket support for streaming

### Phase 3: Advanced Features (Week 3)
1. Implement rate limiting
2. Add API key management
3. Create OpenAPI/Swagger documentation
4. Add metrics and usage endpoints

### Phase 4: Client Libraries (Week 4)
1. Create Python client library
2. Add JavaScript/TypeScript client library
3. Write documentation and examples
4. Test integrations

## Dependencies to Add
- `fastapi>=0.104`
- `uvicorn>=0.24` (ASGI server)
- `python-multipart` (for file uploads)
- `python-jose[cryptography]` (for JWT if implementing OAuth)
- `websockets>=12.0`

## Configuration
Add to settings.yaml:
```yaml
api:
  host: "127.0.0.1"
  port: 8000
  workers: 1
  reload: false
  api_keys:
    - key: "default-key"
      name: "Default"
      rate_limit: "100/hour"
  rate_limits:
    default: "100/hour"
    premium: "1000/hour"
  cors:
    enabled: true
    origins: ["*"]
```

## Testing Strategy
- Unit tests for all endpoints
- Integration tests with real API calls
- Load testing for rate limiting
- Security testing for authentication

## Success Criteria
- All endpoints working with proper authentication
- WebSocket streaming functional
- Rate limiting effective
- Client libraries usable
- Documentation complete
- 100% test coverage for new code