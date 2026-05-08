"""Communication systems and adapter templates for FEDORA components."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from fedora_platform.components import Message


@dataclass(frozen=True)
class CommunicationTemplate:
    """Blueprint for implementing an external communication adapter."""

    name: str
    protocol: str
    python_dependencies: tuple[str, ...]
    best_for: str
    message_pattern: str
    notes: str


def available_communication_templates() -> dict[str, CommunicationTemplate]:
    """Return transport templates that can back the FEDORA MessageBus protocol."""

    return {
        "tcp": CommunicationTemplate(
            name="TCPMessageBus",
            protocol="TCP",
            python_dependencies=(),
            best_for="Reliable component-to-component streams inside a trusted network.",
            message_pattern="newline-delimited JSON Message envelopes over sockets",
            notes="Use when message order and delivery are more important than latency.",
        ),
        "udp": CommunicationTemplate(
            name="UDPMessageBus",
            protocol="UDP",
            python_dependencies=(),
            best_for="High-frequency sensor telemetry where occasional packet loss is acceptable.",
            message_pattern="compact JSON or binary Message envelopes in datagrams",
            notes="Add sequence numbers and timestamps when consumers need loss detection.",
        ),
        "rest": CommunicationTemplate(
            name="RESTAPIMessageBus",
            protocol="HTTP REST",
            python_dependencies=("fastapi", "uvicorn", "httpx"),
            best_for="Request-response integration with dashboards, services, and data platforms.",
            message_pattern="POST /messages with JSON Message bodies; GET /messages for polling",
            notes="Simple to secure and operate; less suitable for low-latency streaming.",
        ),
        "soap": CommunicationTemplate(
            name="SOAPAPIMessageBus",
            protocol="SOAP",
            python_dependencies=("zeep",),
            best_for="Legacy authority or enterprise systems with WSDL contracts.",
            message_pattern="SOAP operations carrying serialized Message envelopes",
            notes="Useful when the partner interface is contract-first and XML-based.",
        ),
        "websocket": CommunicationTemplate(
            name="WebSocketMessageBus",
            protocol="WebSocket",
            python_dependencies=("websockets",),
            best_for="Bidirectional live feeds between pilots, user interfaces, and digital twins.",
            message_pattern="JSON Message envelopes over persistent WebSocket connections",
            notes="Good default for live sensor/control loops that cross process boundaries.",
        ),
        "blockchain": CommunicationTemplate(
            name="BlockchainMessageBus",
            protocol="EVM-compatible blockchain",
            python_dependencies=("web3",),
            best_for="Auditable commitments, settlement events, and cross-organization trust anchors.",
            message_pattern="hash large payloads off-chain; write commitments/events on-chain",
            notes="Do not put raw traffic telemetry on-chain; store references and proofs.",
        ),
    }


class InMemoryMessageBus:
    """Simple in-process message bus for experiments and tests."""

    def __init__(self, interaction_store: Optional[Any] = None) -> None:
        self._inboxes: dict[str, deque[Message]] = defaultdict(deque)
        self._subscriptions: dict[str, set[str]] = defaultdict(set)
        self._interaction_store = interaction_store

    def attach_interaction_store(self, interaction_store: Any) -> None:
        """Attach a store with a ``record_interaction(message)`` method."""

        self._interaction_store = interaction_store

    def register(self, component_id: str) -> None:
        self._inboxes[component_id]

    def subscribe(self, topic: str, component_id: str) -> None:
        self.register(component_id)
        self._subscriptions[topic].add(component_id)

    def publish(self, message: Message) -> None:
        if self._interaction_store is not None:
            self._interaction_store.record_interaction(message)

        receivers: set[str] = set()
        if message.receiver is not None:
            receivers.add(message.receiver)
        receivers.update(self._subscriptions.get(message.topic, set()))

        for receiver in receivers:
            self.register(receiver)
            self._inboxes[receiver].append(message)

    def drain(
        self, component_id: str, topics: Optional[Iterable[str]] = None
    ) -> list[Message]:
        topic_filter = set(topics) if topics is not None else None
        inbox = self._inboxes[component_id]
        selected: list[Message] = []
        remaining: deque[Message] = deque()

        while inbox:
            message = inbox.popleft()
            if topic_filter is None or message.topic in topic_filter:
                selected.append(message)
            else:
                remaining.append(message)

        self._inboxes[component_id] = remaining
        return selected
