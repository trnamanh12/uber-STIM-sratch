"""
internal/domain/offer.py - Ephemeral Driver Dispatch Offer Aggregate & State Machine.

Zero external dependencies. Pure domain logic.
"""

from enum import Enum
import time
from typing import Optional
from internal.domain.trip import DomainError


class OfferError(DomainError):
    """Base exception for dispatch offer errors."""
    pass


class OfferExpiredError(OfferError):
    """Raised when an action is attempted on an expired offer."""
    pass


class OfferIllegalStateError(OfferError):
    """Raised when an illegal transition is attempted on an offer."""
    pass


class OfferState(str, Enum):
    """Lifecycle states of an ephemeral driver dispatch offer."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class DispatchOffer:
    """
    Represents a time-bounded contract offered to an individual driver.
    Enforces expiration bounds and state transition legality.
    """

    def __init__(
        self,
        offer_id: str,
        trip_id: str,
        driver_id: str,
        ttl_seconds: float = 15.0,
        created_at: Optional[float] = None,
    ) -> None:
        self.offer_id = offer_id
        self.trip_id = trip_id
        self.driver_id = driver_id
        self.created_at = created_at if created_at is not None else time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.state = OfferState.PENDING

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def accept(self, current_time: Optional[float] = None) -> None:
        now = current_time if current_time is not None else time.time()
        if self.state != OfferState.PENDING:
            raise OfferIllegalStateError(
                f"Cannot accept offer in state {self.state.value}"
            )
        if now > self.expires_at:
            self.state = OfferState.EXPIRED
            raise OfferExpiredError(
                f"Offer {self.offer_id} expired at {self.expires_at} (current: {now})"
            )
        self.state = OfferState.ACCEPTED

    def decline(self) -> None:
        if self.state != OfferState.PENDING:
            raise OfferIllegalStateError(
                f"Cannot decline offer in state {self.state.value}"
            )
        self.state = OfferState.DECLINED

    def expire_if_timed_out(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        if self.state == OfferState.PENDING and now > self.expires_at:
            self.state = OfferState.EXPIRED
            return True
        return False
