"""
internal/repository/driver_repo.py - Driver Persistence Contracts & Implementations.
"""

from abc import ABC, abstractmethod
import copy
import threading
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

    @abstractmethod
    def atomic_compare_and_swap(
        self, driver_id: str, expected_version: int, updated_driver: Driver
    ) -> bool:
        """
        Atomically updates driver if and only if driver.version == expected_version.
        Returns True if swap succeeded, False if version conflict detected.
        """
        pass


class InMemoryDriverRepository(DriverRepository):
    """Thread-safe in-memory implementation of DriverRepository with OCC."""

    def __init__(self) -> None:
        self._drivers: Dict[str, Driver] = {}
        self._lock = threading.Lock()

    def register(self, driver: Driver) -> None:
        with self._lock:
            self._drivers[driver.driver_id] = copy.copy(driver)

    def get_by_id(self, driver_id: str) -> Optional[Driver]:
        with self._lock:
            d = self._drivers.get(driver_id)
            return copy.copy(d) if d else None

    def list_available(self) -> List[Driver]:
        with self._lock:
            return [copy.copy(d) for d in self._drivers.values() if d.state == DriverState.IDLE]

    def list_all(self) -> List[Driver]:
        with self._lock:
            return [copy.copy(d) for d in self._drivers.values()]

    def update(self, driver: Driver) -> None:
        with self._lock:
            self._drivers[driver.driver_id] = copy.copy(driver)

    def atomic_compare_and_swap(
        self, driver_id: str, expected_version: int, updated_driver: Driver
    ) -> bool:
        with self._lock:
            current = self._drivers.get(driver_id)
            if not current:
                return False
            if current.version != expected_version:
                return False
            self._drivers[driver_id] = copy.copy(updated_driver)
            return True
