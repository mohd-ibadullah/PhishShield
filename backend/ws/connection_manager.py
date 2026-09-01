from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger("phishshield.ws")


class ConnectionManager:
    """Manages active WebSocket connections for live scan feed.

    Session-scoped: broadcasts are sent only to sockets in the same room.
    Pending events are queued per room.
    """

    def __init__(self) -> None:
        self._active: dict[str, WebSocket] = {}
        self._session_by_ws: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()
        self._pending: dict[str, list[tuple[dict[str, Any], datetime]]] = {}
        self._PENDING_MAX_PER_ROOM = 20
        self._PENDING_TTL_SECONDS = 60
        self._MAX_ROOMS = 500
        # TTL=60s; observed peak/min=903 (scan_logs.jsonl, n=80220, includes test bursts).
        # 20×903=18060; cap set to 10000 as practical bound. Peak includes test-written
        # records — production rate is lower. Events older than TTL are pruned.
        self._MAX_TOTAL_EVENTS = 10000

    def _prune_pending_locked(self, room: str) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        room_pending = self._pending.get(room, [])
        fresh: list[dict[str, Any]] = []
        kept: list[tuple[dict[str, Any], datetime]] = []
        for event, created_at in room_pending:
            age = (now - created_at).total_seconds()
            if age < self._PENDING_TTL_SECONDS:
                fresh.append(event)
                kept.append((event, created_at))
        self._pending[room] = kept
        # Evict oldest rooms if over global cap
        self._evict_global_pending_locked()
        return fresh

    def _evict_global_pending_locked(self) -> None:
        """Enforce MAX_TOTAL_EVENTS and MAX_ROOMS across all rooms."""
        # Evict oldest rooms first if room count exceeds cap
        while len(self._pending) > self._MAX_ROOMS:
            oldest_room = next(iter(self._pending))
            self._pending.pop(oldest_room, None)
        # Evict oldest events if total exceeds cap
        total = sum(len(q) for q in self._pending.values())
        while total > self._MAX_TOTAL_EVENTS and self._pending:
            oldest_room = next(iter(self._pending))
            room_q = self._pending[oldest_room]
            if room_q:
                room_q.pop(0)
                total -= 1
            if not room_q:
                self._pending.pop(oldest_room, None)

    def _is_open(self, ws: WebSocket) -> bool:
        return ws.client_state == WebSocketState.CONNECTED and ws.application_state == WebSocketState.CONNECTED

    async def connect(self, ws: WebSocket, session_id: str | None = None) -> str:
        await ws.accept()
        session_key = session_id or f"anonymous-{uuid4().hex}"
        fresh: list[dict[str, Any]] = []

        async with self._lock:
            existing = self._active.get(session_key)
            if existing is not None and existing is not ws:
                # 1c: Same session key from different identity -> reject new socket.
                try:
                    await ws.close(code=1008, reason="Session already connected")
                except Exception:
                    pass
                logger.warning("[WS] Rejected duplicate session key: %s", session_key)
                return session_key

            self._active[session_key] = ws
            self._session_by_ws[ws] = session_key
            fresh = self._prune_pending_locked(session_key)
            if fresh:
                self._pending.pop(session_key, None)
            logger.info("[WS] Connection accepted; replaying %s pending events", len(fresh))

        for event in fresh:
            try:
                await ws.send_json(event)
            except Exception:
                break

        logger.info("[WS] Client connected (%s active)", len(self._active))
        return session_key

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            session_key = self._session_by_ws.pop(ws, None)
            if session_key and self._active.get(session_key) is ws:
                self._active.pop(session_key, None)
            else:
                for key, active_ws in list(self._active.items()):
                    if active_ws is ws:
                        self._active.pop(key, None)
                        break
            logger.info("[WS] Client disconnected (%s active)", len(self._active))

    async def broadcast(self, message: dict[str, Any], session_key: str | None = None) -> None:
        """Broadcast to all sockets in the given room (session_key).

        session_key=None sends to nobody (not to all).
        """
        if session_key is None:
            logger.debug("[WS] broadcast with no session_key; dropping message")
            return

        async with self._lock:
            # Only send to the specific session socket.
            ws = self._active.get(session_key)
            if ws is None:
                # Queue for later replay, scoped to this room.
                room_pending = self._pending.setdefault(session_key, [])
                room_pending.append((message, datetime.now(timezone.utc)))
                if len(room_pending) > self._PENDING_MAX_PER_ROOM:
                    self._pending[session_key] = room_pending[-self._PENDING_MAX_PER_ROOM:]
                logger.debug("[WS] No active connection for session %s; event queued", session_key)
                return
            snapshot = [(session_key, ws)]

        dead: list[tuple[str, WebSocket]] = []
        for key, sock in snapshot:
            if not self._is_open(sock):
                dead.append((key, sock))
                continue
            try:
                await asyncio.wait_for(sock.send_json(message), timeout=3.0)
            except (asyncio.TimeoutError, Exception):
                dead.append((key, sock))

        if dead:
            async with self._lock:
                for key, sock in dead:
                    if self._active.get(key) is sock:
                        self._active.pop(key, None)
                    self._session_by_ws.pop(sock, None)

    async def ping_all(self) -> None:
        return
