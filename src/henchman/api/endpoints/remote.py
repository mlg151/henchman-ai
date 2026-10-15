"""Remote-session, websocket, and OAuth endpoints for Tier 8."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from henchman.api.auth import verify_api_key
from henchman.api.oauth import OAuthService
from henchman.api.remote_sessions import RemoteSessionManager
from henchman.api.state import state

router = APIRouter(prefix="/v1", tags=["remote"])


class RemoteSessionCreateRequest(BaseModel):
    """Request model for remote session creation."""

    client_id: str = Field(description="Remote client identifier")
    title: str = Field(description="Human-readable session title")


class RemoteSessionResponse(BaseModel):
    """Response model for remote session metadata."""

    session_id: str
    client_id: str
    title: str
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    last_event: dict[str, Any] | None = None


class OAuthAuthorizeRequest(BaseModel):
    """Authorization request model."""

    client_id: str
    redirect_uri: str
    scopes: list[str] = Field(default_factory=list)


class OAuthAuthorizeResponse(BaseModel):
    """Authorization response model."""

    state: str
    authorization_url: str
    scopes: list[str]


class OAuthTokenRequest(BaseModel):
    """Token exchange request model."""

    client_id: str
    state: str
    code: str


class OAuthTokenResponse(BaseModel):
    """Token exchange response model."""

    access_token: str
    token_type: str
    client_id: str
    scopes: list[str]


def _require_remote_session_manager() -> RemoteSessionManager:
    """Return the remote session manager or raise a service error."""
    manager = getattr(state, "remote_session_manager", None)
    if not isinstance(manager, RemoteSessionManager):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Remote sessions are unavailable",
        )
    return manager


def _require_oauth_service() -> OAuthService:
    """Return the OAuth service or raise a service error."""
    oauth_service = getattr(state, "oauth_service", None)
    if not isinstance(oauth_service, OAuthService):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth service is unavailable",
        )
    return oauth_service


@router.post(
    "/remote/sessions",
    response_model=RemoteSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_remote_session(
    request: RemoteSessionCreateRequest,
    api_key_valid: Annotated[bool, Depends(verify_api_key)],
) -> RemoteSessionResponse:
    """Create a remote session."""
    if not api_key_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    session = _require_remote_session_manager().create_session(
        client_id=request.client_id,
        title=request.title,
    )
    return RemoteSessionResponse.model_validate(session)


@router.get("/remote/sessions", response_model=list[RemoteSessionResponse])
async def list_remote_sessions(
    api_key_valid: Annotated[bool, Depends(verify_api_key)],
) -> list[RemoteSessionResponse]:
    """List all remote sessions."""
    if not api_key_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return [
        RemoteSessionResponse.model_validate(session)
        for session in _require_remote_session_manager().list_sessions()
    ]


@router.get("/remote/sessions/{session_id}", response_model=RemoteSessionResponse)
async def get_remote_session(
    session_id: str,
    api_key_valid: Annotated[bool, Depends(verify_api_key)],
) -> RemoteSessionResponse:
    """Get one remote session by ID."""
    if not api_key_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    session = _require_remote_session_manager().get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return RemoteSessionResponse.model_validate(session)


@router.post("/oauth/authorize", response_model=OAuthAuthorizeResponse)
async def authorize_remote_client(
    request: OAuthAuthorizeRequest,
    api_key_valid: Annotated[bool, Depends(verify_api_key)],
) -> OAuthAuthorizeResponse:
    """Create a pending OAuth authorization request."""
    if not api_key_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    authorization = _require_oauth_service().create_authorization_request(
        client_id=request.client_id,
        redirect_uri=request.redirect_uri,
        scopes=request.scopes,
    )
    return OAuthAuthorizeResponse(
        state=authorization.state,
        authorization_url=authorization.authorization_url,
        scopes=list(authorization.scopes),
    )


@router.post("/oauth/token", response_model=OAuthTokenResponse)
async def exchange_remote_token(
    request: OAuthTokenRequest,
    api_key_valid: Annotated[bool, Depends(verify_api_key)],
) -> OAuthTokenResponse:
    """Exchange a pending OAuth request for a bearer token."""
    if not api_key_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    try:
        token = _require_oauth_service().exchange_code(
            client_id=request.client_id,
            state=request.state,
            code=request.code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OAuthTokenResponse(
        access_token=token.access_token,
        token_type=token.token_type,
        client_id=token.client_id,
        scopes=list(token.scopes),
    )


@router.websocket("/remote/sessions/{session_id}/ws")
async def remote_session_websocket(websocket: WebSocket, session_id: str) -> None:
    """Echo websocket events into the remote session event log."""
    manager = getattr(state, "remote_session_manager", None)
    if manager is None or manager.get_session(session_id) is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            event_name = str(payload.get("event", "message"))
            event_payload = payload.get("payload", {})
            if not isinstance(event_payload, dict):
                event_payload = {"value": event_payload}
            event_record = manager.publish_event(session_id, event_name, event_payload)
            await websocket.send_json(event_record)
    except WebSocketDisconnect:
        return
