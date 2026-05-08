from __future__ import annotations

import sys
import unittest
from uuid import uuid4
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fedora_platform.communication import (
    InMemoryMessageBus,
    available_communication_templates,
)
from fedora_platform.components import (
    ComponentRole,
    ComponentState,
    FedoraComponent,
    Message,
    TransitionError,
)
from fedora_platform.storage import SQLiteInteractionStore, available_storage_templates


class EchoComponent(FedoraComponent):
    def __init__(self, bus: InMemoryMessageBus):
        super().__init__("echo", role=ComponentRole.PILOT_SYSTEM, bus=bus)

    def step(self) -> None:
        for message in self.receive(["ping"]):
            self.publish("pong", {"seen": message.payload["value"]}, receiver="tester")


class CoreTests(unittest.TestCase):
    def test_component_lifecycle_rejects_invalid_transition(self) -> None:
        bus = InMemoryMessageBus()
        component = EchoComponent(bus)

        with self.assertRaises(TransitionError):
            component.transition_to(ComponentState.RUNNING)

        component.configure()
        component.start()
        self.assertEqual(component.state, ComponentState.RUNNING)

    def test_message_bus_routes_subscribed_topics_and_receivers(self) -> None:
        bus = InMemoryMessageBus()
        bus.register("tester")
        echo = EchoComponent(bus)
        bus.subscribe("ping", echo.component_id)

        bus.publish(Message(topic="ping", sender="tester", payload={"value": 7}))
        echo.step()

        messages = bus.drain("tester", ["pong"])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].payload["seen"], 7)

    def test_templates_include_requested_communication_and_storage_options(self) -> None:
        communication_templates = available_communication_templates()
        storage_templates = available_storage_templates()

        self.assertTrue(
            {"tcp", "udp", "rest", "soap", "websocket", "blockchain"}.issubset(
                communication_templates
            )
        )
        self.assertIn("sqlite", storage_templates)
        self.assertIn("postgresql", storage_templates)

    def test_sqlite_store_records_bus_interactions(self) -> None:
        db_path = ROOT / "runs" / f"test_interactions_{uuid4().hex}.sqlite3"
        db_path.parent.mkdir(exist_ok=True)
        try:
            store = SQLiteInteractionStore(db_path)
            bus = InMemoryMessageBus(interaction_store=store)
            bus.register("receiver")

            bus.publish(
                Message(
                    topic="sensor.snapshot",
                    sender="pilot",
                    receiver="receiver",
                    payload={"vehicles": 3},
                )
            )

            interactions = store.list_interactions(topic="sensor.snapshot")
            self.assertEqual(len(interactions), 1)
            self.assertEqual(interactions[0]["payload"]["vehicles"], 3)
        finally:
            db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
