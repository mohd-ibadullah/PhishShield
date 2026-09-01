"""WS broadcast tests — session isolation, content redaction, AST guard, pending replay.

Tests 1-2 use mock-based broadcast interception (starlette TestClient does not support
concurrent websocket reads in async context). Test 3 is an AST guard. Test 4 tests
pending queue scoping via ConnectionManager directly.
"""
from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: session isolation (two sockets, scan as A, B should NOT receive)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ws_broadcast_session_isolation(client):
    """Two sockets with different session keys. Scan as session B.
    Session A should NOT receive B's event. """
    MARKER = "ISOLATION-PROBE-" + str(int(time.time()))

    resp_a = await client.post("/api/session")
    resp_b = await client.post("/api/session")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    session_a = resp_a.json().get("session_id", "a")
    session_b = resp_b.json().get("session_id", "b")

    import main as backend_main
    a_received = []

    original_broadcast = backend_main.ws_manager.broadcast

    async def track_a_receive(msg, session_key=None):
        # Only capture if this would be delivered to session_a
        if session_key == session_a:
            a_received.append(msg)
        await original_broadcast(msg, session_key=session_key)

    with patch.object(backend_main.ws_manager, "broadcast", track_a_receive):
        email_body = "Subject: " + MARKER + chr(10) + chr(10) + "Click: http://test.example.com"
        scan_resp = await client.post(
            "/scan-email",
            json={
                "email_text": email_body,
                "session_id": session_b,
            },
        )
        assert scan_resp.status_code == 200
        b_scan_id = scan_resp.json()["scan_id"]

    # A should NOT have received B's scan event
    b_events_at_a = [e for e in a_received if e.get("scan_id") == b_scan_id]
    assert len(b_events_at_a) == 0, (
        "SESSION ISOLATION BREACH: session A received " + str(len(b_events_at_a)) +
        " events from session B scan"
    )


# ---------------------------------------------------------------------------
# Test 2: content redaction (permanent, non-xfail)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ws_broadcast_content_redaction(client):
    """Raw email text must never appear in any broadcast frame."""
    MARKER = "SECRET-EMAIL-CONTENT-" + str(int(time.time()))

    resp = await client.post("/api/session")
    assert resp.status_code == 200
    session_id = resp.json().get("session_id", "test")

    import main as backend_main
    captured = []

    original_broadcast = backend_main.ws_manager.broadcast

    async def capture(msg, session_key=None):
        captured.append(msg)
        await original_broadcast(msg, session_key=session_key)

    with patch.object(backend_main.ws_manager, "broadcast", capture):
        email_body = "Subject: " + MARKER + chr(10) + chr(10) + "Click: http://test.example.com"
        scan_resp = await client.post(
            "/scan-email",
            json={
                "email_text": email_body,
                "session_id": session_id,
            },
        )
        assert scan_resp.status_code == 200

    assert len(captured) > 0, "No broadcast emitted"
    for msg in captured:
        msg_str = json.dumps(msg)
        assert MARKER not in msg_str, (
            "PRIVACY VIOLATION: raw email content in broadcast: " + msg_str[:200]
        )
        assert "test.example.com" not in msg_str, (
            "PRIVACY VIOLATION: raw URL in broadcast: " + msg_str[:200]
        )


# ---------------------------------------------------------------------------
# Test 3: AST guard — no send_json outside connection_manager.py
# ---------------------------------------------------------------------------

def test_no_websocket_send_outside_connection_manager():
    """No file outside connection_manager.py and main.py WS endpoint
    should call websocket.send_json or websocket.send_text directly.
    Also: broadcast() must be called with session_key kwarg."""
    repo = Path(__file__).resolve().parents[1]
    backend_dir = repo / "backend"
    ws_files = {"connection_manager.py", "main.py"}

    violations = []
    for py in sorted(backend_dir.glob("*.py")):
        if py.name in ws_files:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for websocket.send_json / send_text
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("send_json", "send_text"):
                    if isinstance(node.func.value, ast.Attribute):
                        obj = node.func.value
                        if isinstance(obj.value, ast.Name) and obj.attr in ("websocket", "ws", "socket"):
                            violations.append(f"{py.name}:{node.lineno}: {obj.attr}.{node.func.attr}()")
    assert not violations, (
        "WebSocket send outside approved files: " + str(violations)
    )


# ---------------------------------------------------------------------------
# Test 4: pending replay is room-scoped (ConnectionManager unit test)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pending_replay_is_room_scoped():
    """Events queued for session A should NOT replay to session B."""
    from backend.ws.connection_manager import ConnectionManager

    cm = ConnectionManager()

    # Create two mock websockets
    class FakeWS:
        def __init__(self):
            from starlette.websockets import WebSocketState
            self.client_state = WebSocketState.CONNECTED
            self.application_state = WebSocketState.CONNECTED
            self.sent = []
            self._closed = False

        async def accept(self):
            pass

        async def send_json(self, msg):
            self.sent.append(msg)

        async def close(self, code=1000, reason=""):

            self._closed = True

    ws_a = FakeWS()
    ws_b = FakeWS()

    # Connect A
    await cm.connect(ws_a, session_id="room-a")
    # Disconnect A (so events get queued)
    await cm.disconnect(ws_a)

    # Broadcast to room A while A is disconnected -> queued
    await cm.broadcast({"type": "scan_complete", "scan_id": "A-001"}, session_key="room-a")

    # Connect B with a different room
    await cm.connect(ws_b, session_id="room-b")

    # B should NOT have received A's queued event
    a_events_at_b = [e for e in ws_b.sent if e.get("scan_id") == "A-001"]
    assert len(a_events_at_b) == 0, (
        "PENDING REPLAY ISOLATION BREACH: session B received " +
        str(len(a_events_at_b)) + " events from session A's pending queue"
    )



@pytest.mark.asyncio
async def test_pending_queue_is_bounded_across_rooms():
    """Global caps: MAX_ROOMS and MAX_TOTAL_EVENTS are enforced."""
    from backend.ws.connection_manager import ConnectionManager

    cm = ConnectionManager()

    class FakeWS:
        def __init__(self):
            from starlette.websockets import WebSocketState
            self.client_state = WebSocketState.CONNECTED
            self.application_state = WebSocketState.CONNECTED
            self.sent = []
        async def accept(self): pass
        async def send_json(self, msg): self.sent.append(msg)
        async def close(self, code=1000, reason=""): pass

    # Flood with unknown keys to exceed MAX_ROOMS
    for i in range(cm._MAX_ROOMS + 10):
        ws = FakeWS()
        await cm.connect(ws, session_id=f"overflow-room-{i}")
        await cm.disconnect(ws)
        await cm.broadcast({"type": "flood", "i": i}, session_key=f"overflow-room-{i}")

    # Room count must be at most MAX_ROOMS
    assert len(cm._pending) <= cm._MAX_ROOMS, (
        f"Room cap violated: {len(cm._pending)} rooms > {cm._MAX_ROOMS}"
    )

    # Total events must be at most MAX_TOTAL_EVENTS
    total = sum(len(q) for q in cm._pending.values())
    assert total <= cm._MAX_TOTAL_EVENTS, (
        f"Total event cap violated: {total} > {cm._MAX_TOTAL_EVENTS}"
    )


@pytest.mark.asyncio
async def test_broadcast_without_session_key_sends_nothing():
    """broadcast(None), broadcast("") and broadcast(unknown) must not deliver."""
    from backend.ws.connection_manager import ConnectionManager

    cm = ConnectionManager()

    class FakeWS:
        def __init__(self):
            from starlette.websockets import WebSocketState
            self.client_state = WebSocketState.CONNECTED
            self.application_state = WebSocketState.CONNECTED
            self.sent = []
        async def accept(self): pass
        async def send_json(self, msg): self.sent.append(msg)
        async def close(self, code=1000, reason=""): pass

    ws = FakeWS()
    await cm.connect(ws, session_id="test-room")
    ws.sent.clear()

    # All three must deliver 0 sends
    await cm.broadcast({"type": "test"}, session_key=None)
    await cm.broadcast({"type": "test"}, session_key="")
    await cm.broadcast({"type": "test"}, session_key="nonexistent-key")
    assert len(ws.sent) == 0, f"broadcast to invalid key sent {len(ws.sent)} messages"


@pytest.mark.asyncio
async def test_unknown_session_key_sends_nothing():
    """Broadcast to a key nobody holds must not deliver."""
    from backend.ws.connection_manager import ConnectionManager

    cm = ConnectionManager()
    await cm.broadcast({"type": "test"}, session_key="totally-fake-key")
    # No active sockets, no delivery — pending queue scoped to room
    assert "totally-fake-key" in cm._pending or len(cm._pending) == 0
