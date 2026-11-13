"""
internal/repository/driver_repo.py - Driver Persistence Contracts & Implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from internal.domain.driver import Driver, DriverState


class DriverRepository(ABC):
    """Abstract interface defining the driver storage boundary."""

    @abstractmethod
    def register(self, driver: Driver) -> None:
        pass

    @abstractmethod
    def get_by_id(self, driver_id: str) -> Optional[Driver]:
        pass

    @abstractmethod
    def list_available(self) -> List[Driver]:
        pass

    @abstractmethod
    def list_all(self) -> List[Driver]:
        pass

    @abstractmethod
    def update(self, driver: Driver) -> None:
        pass


class InMemoryDriverRepository(DriverRepository):
    """In-memory implementation of DriverRepository."""

    def __init__(self) -> None:
        self._drivers: Dict[str, Driver] = {}

    def register(self, driver: Driver) -> None:
        self._drivers[driver.driver_id] = driver

    def get_by_id(self, driver_id: str) -> Optional[Driver]:
        return self._drivers.get(driver_id)

    def list_available(self) -> List[Driver]:
        return [d for d in self._drivers.values() if d.state == DriverState.IDLE]

    def list_all(self) -> List[Driver]:
        return list(self._drivers.values())

    def update(self, driver: Driver) -> None:
        self._drivers[driver.driver_id] = driver
