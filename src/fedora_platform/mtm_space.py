"""Orchestration helpers for FEDORA Mobility and Transport Multimodal Spaces."""

from __future__ import annotations

from typing import Iterable, Optional

from fedora_platform.communication import InMemoryMessageBus
from fedora_platform.components import ComponentState, FedoraComponent, MessageBus


class MTMSpace:
    """Container that wires components to a shared communication system."""

    def __init__(
        self,
        space_id: str,
        bus: Optional[MessageBus] = None,
    ) -> None:
        self.space_id = space_id
        self.bus = bus or InMemoryMessageBus()
        self.components: dict[str, FedoraComponent] = {}

    def register(self, component: FedoraComponent) -> FedoraComponent:
        component.attach_bus(self.bus)
        self.components[component.component_id] = component
        return component

    def register_many(
        self, components: Iterable[FedoraComponent]
    ) -> list[FedoraComponent]:
        return [self.register(component) for component in components]

    def subscribe(self, topic: str, component_id: str) -> None:
        self.bus.subscribe(topic, component_id)

    def step(self) -> None:
        for component in list(self.components.values()):
            if component.state not in {
                ComponentState.STOPPED,
                ComponentState.FAILED,
            }:
                component.step()

    def stop(self) -> None:
        for component in list(self.components.values()):
            if component.state != ComponentState.STOPPED:
                component.stop()
