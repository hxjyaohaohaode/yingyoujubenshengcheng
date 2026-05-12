import json
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from websocket.manager import WebSocketManager


class FakeWebSocket:
    def __init__(self, fail_on_send: bool = False):
        self.accepted = False
        self.messages = []
        self.fail_on_send = fail_on_send

    async def accept(self):
        self.accepted = True

    async def send_text(self, data: str):
        if self.fail_on_send:
            raise RuntimeError("send failed")
        self.messages.append(data)


class WebSocketManagerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_connect_and_broadcast(self):
        manager = WebSocketManager()
        ws = FakeWebSocket()

        await manager.connect("project-1", ws)
        await manager.broadcast_to_project("project-1", {"type": "notification", "message": "ok"})

        self.assertTrue(ws.accepted)
        self.assertEqual(len(ws.messages), 1)
        self.assertEqual(json.loads(ws.messages[0])["message"], "ok")

    async def test_send_agent_update_uses_agent_status_contract(self):
        manager = WebSocketManager()
        ws = FakeWebSocket()

        await manager.connect("project-1", ws)
        await manager.send_agent_update("project-1", "审计Agent", "running", "全项目审计")

        payload = json.loads(ws.messages[0])
        self.assertEqual(payload["type"], "agent_status")
        self.assertEqual(payload["agent_name"], "审计Agent")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["current_task"], "全项目审计")

    async def test_disconnects_failed_websocket(self):
        manager = WebSocketManager()
        healthy = FakeWebSocket()
        broken = FakeWebSocket(fail_on_send=True)

        await manager.connect("project-1", healthy)
        await manager.connect("project-1", broken)
        await manager.broadcast_to_project("project-1", {"type": "notification", "message": "cleanup"})

        self.assertEqual(len(manager.active_connections["project-1"]), 1)
        self.assertIs(manager.active_connections["project-1"][0], healthy)


if __name__ == "__main__":
    unittest.main()
