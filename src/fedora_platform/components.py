"""Abstract component model for FEDORA MTM Spaces.

The project-level architecture treats optimizers, simulators, pilot systems,
storage backends, and communication mechanisms as stateful components. Each
component exposes the same lifecycle and communicates through messages.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Protocol
from uuid import uuid4


class ComponentRole(str, Enum):
    """High-level roles inside an MTM Space."""

    OPTIMIZATION_MODULE = "optimization_module"
    SIMULATOR = "simulator"
    PILOT_SYSTEM = "pilot_system"
    DATA_STORAGE = "data_storage"
    COMMUNICATION_SYSTEM = "communication_system"


class ComponentState(str, Enum):
    """Common finite-state lifecycle shared by FEDORA components."""

    CREATED = "created"
    CONFIGURED = "configured"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    FAILED = "failed"


class TransitionError(RuntimeError):
    """Raised when a component attempts an invalid lifecycle transition."""


@dataclass
class Message:
    """Message exchanged between FEDORA components."""

    topic: str
    sender: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    receiver: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MessageBus(Protocol):
    """Protocol implemented by communication systems."""

    def register(self, component_id: str) -> None:
        ...

    def subscribe(self, topic: str, component_id: str) -> None:
        ...

    def publish(self, message: Message) -> None:
        ...

    def drain(
        self, component_id: str, topics: Optional[Iterable[str]] = None
    ) -> list[Message]:
        ...


class FiniteStateMachine:
    """Small reusable finite-state machine for component lifecycles."""

    _allowed_transitions: dict[ComponentState, set[ComponentState]] = {
        ComponentState.CREATED: {
            ComponentState.CONFIGURED,
            ComponentState.STOPPED,
            ComponentState.FAILED,
        },
        ComponentState.CONFIGURED: {
            ComponentState.READY,
            ComponentState.STOPPED,
            ComponentState.FAILED,
        },
        ComponentState.READY: {
            ComponentState.RUNNING,
            ComponentState.STOPPED,
            ComponentState.FAILED,
        },
        ComponentState.RUNNING: {
            ComponentState.PAUSED,
            ComponentState.STOPPED,
            ComponentState.FAILED,
        },
        ComponentState.PAUSED: {
            ComponentState.RUNNING,
            ComponentState.STOPPED,
            ComponentState.FAILED,
        },
        ComponentState.STOPPED: {ComponentState.CONFIGURED, ComponentState.FAILED},
        ComponentState.FAILED: {ComponentState.STOPPED},
    }

    def __init__(self) -> None:
        self.state = ComponentState.CREATED
        self.state_history = [self.state]

    def transition_to(self, next_state: ComponentState) -> None:
        if next_state == self.state:
            return
        allowed = self._allowed_transitions[self.state]
        if next_state not in allowed:
            raise TransitionError(
                f"Cannot transition from {self.state.value} to {next_state.value}"
            )
        self.state = next_state
        self.state_history.append(next_state)


class FedoraComponent(FiniteStateMachine, ABC):
    """Base class for stateful FEDORA components."""

    def __init__(
        self,
        component_id: str,
        role: ComponentRole,
        bus: Optional[MessageBus] = None,
    ) -> None:
        super().__init__()
        self.component_id = component_id
        self.role = role
        self.bus = bus
        self.configuration: MutableMapping[str, Any] = {}
        if self.bus is not None:
            self.bus.register(self.component_id)

    def attach_bus(self, bus: MessageBus) -> None:
        self.bus = bus
        self.bus.register(self.component_id)

    def configure(self, configuration: Optional[Mapping[str, Any]] = None) -> None:
        self.configuration.update(dict(configuration or {}))
        if self.state == ComponentState.STOPPED:
            self.transition_to(ComponentState.CONFIGURED)
        elif self.state == ComponentState.CREATED:
            self.transition_to(ComponentState.CONFIGURED)
        self.transition_to(ComponentState.READY)

    def start(self) -> None:
        if self.state == ComponentState.CREATED:
            self.configure()
        if self.state == ComponentState.CONFIGURED:
            self.transition_to(ComponentState.READY)
        self.transition_to(ComponentState.RUNNING)

    def pause(self) -> None:
        self.transition_to(ComponentState.PAUSED)

    def stop(self) -> None:
        self.transition_to(ComponentState.STOPPED)

    def fail(self) -> None:
        self.transition_to(ComponentState.FAILED)

    def publish(
        self,
        topic: str,
        payload: Optional[Mapping[str, Any]] = None,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        if self.bus is None:
            return
        self.bus.publish(
            Message(
                topic=topic,
                sender=self.component_id,
                receiver=receiver,
                payload=payload or {},
                correlation_id=correlation_id or str(uuid4()),
            )
        )

    def receive(self, topics: Optional[Iterable[str]] = None) -> list[Message]:
        if self.bus is None:
            return []
        return self.bus.drain(self.component_id, topics=topics)

    def handle_message(self, message: Message) -> None:
        """Handle a message from another component.

        Concrete components override this when they support asynchronous
        interaction. The default intentionally ignores unknown messages.
        """

    @abstractmethod
    def step(self) -> None:
        """Advance the component FSM by one logical step."""


class OptimizationModule(FedoraComponent):
    """Abstract base for optimization and control modules."""

    def __init__(self, component_id: str, bus: Optional[MessageBus] = None) -> None:
        super().__init__(component_id, ComponentRole.OPTIMIZATION_MODULE, bus)

    @abstractmethod
    def optimize(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return an optimization result for the given context."""


class SimulatorModule(FedoraComponent):
    """Abstract base for simulator integrations."""

    def __init__(self, component_id: str, bus: Optional[MessageBus] = None) -> None:
        super().__init__(component_id, ComponentRole.SIMULATOR, bus)

    @abstractmethod
    def collect_results(self) -> Mapping[str, Any]:
        """Return simulator results collected so far."""


class PilotSystem(FedoraComponent):
    """Abstract base for pilot systems orchestrating real or simulated pilots."""

    def __init__(self, component_id: str, bus: Optional[MessageBus] = None) -> None:
        super().__init__(component_id, ComponentRole.PILOT_SYSTEM, bus)

    @abstractmethod
    def run(self) -> Mapping[str, Any]:
        """Run the pilot workflow to completion."""


class DataStorage(FedoraComponent):
    """Abstract base for storage backends."""

    def __init__(self, component_id: str, bus: Optional[MessageBus] = None) -> None:
        super().__init__(component_id, ComponentRole.DATA_STORAGE, bus)

    @abstractmethod
    def read(self, key: str) -> Any:
        """Read one record by key."""

    @abstractmethod
    def write(self, key: str, value: Any) -> None:
        """Write one record by key."""
