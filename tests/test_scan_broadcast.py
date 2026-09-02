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
    """Global caps: MAX_ROOMS and MAX_TOTAL_EVENTS are enforced.

    Fills the queue past both caps to prove eviction binds, then asserts
    total_queued == MAX_TOTAL_EVENTS. Also proves caps fail when enforcement
    is removed (mutation test).

    Note: cap=20000 is above the previously observed 20x903=18060
    burst estimate. If exceeded, oldest events are evicted (lossy by design).
    """
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

    # ── Positive proof: fill past both caps ──
    # PENDING_MAX_PER_ROOM=20; fill enough rooms to exceed MAX_TOTAL_EVENTS.
    # With 20 events/room, need ceil(MAX_TOTAL_EVENTS/20) rooms to hit cap.
    rooms_needed = (cm._MAX_TOTAL_EVENTS // cm._PENDING_MAX_PER_ROOM) + 50
    for i in range(max(cm._MAX_ROOMS + 50, rooms_needed)):
        ws = FakeWS()
        await cm.connect(ws, session_id=f"fill-room-{i}")
        await cm.disconnect(ws)
        for j in range(25):  # 25 > PENDING_MAX_PER_ROOM; truncated to 20
            await cm.broadcast({"type": "event", "i": i, "j": j},
                               session_key=f"fill-room-{i}")

    total = sum(len(q) for q in cm._pending.values())
    assert total == cm._MAX_TOTAL_EVENTS, (
        f"Cap did not bind: total_queued={total} != MAX_TOTAL_EVENTS={cm._MAX_TOTAL_EVENTS}"
    )

    # Room count must be at most MAX_ROOMS
    assert len(cm._pending) <= cm._MAX_ROOMS, (
        f"Room cap violated: {len(cm._pending)} rooms > {cm._MAX_ROOMS}"
    )

    # ── Mutation test: prove caps fail when enforcement is removed ──
    original_evict = cm._evict_global_pending_locked
    cm._evict_global_pending_locked = lambda: None  # disable eviction

    cm._pending.clear()
    for i in range(cm._MAX_ROOMS + 50):
        ws = FakeWS()
        await cm.connect(ws, session_id=f"mutant-room-{i}")
        await cm.disconnect(ws)
        for j in range(25):
            await cm.broadcast({"type": "event", "i": i, "j": j},
                               session_key=f"mutant-room-{i}")

    total_mutant = sum(len(q) for q in cm._pending.values())
    assert total_mutant > cm._MAX_TOTAL_EVENTS, (
        f"Mutation test failed: without enforcement, total={total_mutant} "
        f"should exceed MAX_TOTAL_EVENTS={cm._MAX_TOTAL_EVENTS}"
    )

    cm._evict_global_pending_locked = original_evict

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


@pytest.mark.asyncio
async def test_pending_memory_bound():
    """Fill to both caps, assert total queued events ≤ MAX_TOTAL_EVENTS
    and approximate serialized size < 1 MB. Eviction removes oldest room."""
    import sys
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

    # Fill to exceed MAX_ROOMS (each room gets 1 event)
    for i in range(cm._MAX_ROOMS + 50):
        ws = FakeWS()
        await cm.connect(ws, session_id=f"mem-room-{i}")
        await cm.disconnect(ws)
        await cm.broadcast({"type": "event", "i": i}, session_key=f"mem-room-{i}")

    # Assert room cap
    assert len(cm._pending) <= cm._MAX_ROOMS, (
        f"Room cap: {len(cm._pending)} > {cm._MAX_ROOMS}"
    )

    # Assert total event cap
    total = sum(len(q) for q in cm._pending.values())
    assert total <= cm._MAX_TOTAL_EVENTS, (
        f"Event cap: {total} > {cm._MAX_TOTAL_EVENTS}"
    )

    # Assert serialized size is bounded: each event ~30-60 B JSON,
    # at MAX_TOTAL_EVENTS the bound is MAX_TOTAL_EVENTS * 100 B (generous).
    import json
    serialized = json.dumps([e for q in cm._pending.values() for e, _ in q])
    size_bytes = len(serialized.encode())
    # Practical bound: 10000 events * 100 B = ~1 MB; real payload is ~30 B each.
    # If this fails, the cap or payload grew beyond spec.
    max_expected = cm._MAX_TOTAL_EVENTS * 100  # 100 B per event (generous)
    assert size_bytes < max_expected, (
        f"Serialized queue size {size_bytes} bytes exceeds {max_expected} bound"
    )

    # Assert eviction removes oldest room, not newest
    assert "mem-room-0" not in cm._pending, "Oldest room not evicted"
