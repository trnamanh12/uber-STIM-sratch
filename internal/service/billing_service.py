"""
internal/service/billing_service.py - Trip Fare Billing & Ledger Settlement Service.
"""

import uuid
from internal.domain.ledger import (
    DoubleEntryLedgerError,
    JournalEntry,
    Posting,
    PostingDirection,
)
from internal.repository.ledger_repo import LedgerRepository


class BillingService:
    """
    Application Service: Orchestrates fare settlement using Double-Entry Bookkeeping.
    Guarantees no funds are created or lost, and all math uses integer cents.
    """

    def __init__(self, ledger_repo: LedgerRepository) -> None:
        self.ledger_repo = ledger_repo

    def settle_trip_fare(
        self,
        trip_id: str,
        rider_account_id: str,
        driver_account_id: str,
        platform_account_id: str,
        fare_cents: int,
        platform_fee_percent: float = 0.20,
    ) -> JournalEntry:
        """
        Settles a completed trip:
        - Debit Rider Wallet by fare_cents
        - Credit Driver Payout by driver_share
        - Credit Platform Revenue by platform_share
        """
        if fare_cents <= 0:
            raise DoubleEntryLedgerError("Fare cents must be strictly positive")
        if not (0.0 <= platform_fee_percent <= 0.50):
            raise DoubleEntryLedgerError("Platform fee percent must be between 0% and 50%")

        platform_fee_cents = int(round(fare_cents * platform_fee_percent))
        driver_payout_cents = fare_cents - platform_fee_cents

        postings = [
            Posting(
                account_id=rider_account_id,
                amount_cents=fare_cents,
                direction=PostingDirection.DEBIT,
            ),
            Posting(
                account_id=driver_account_id,
                amount_cents=driver_payout_cents,
                direction=PostingDirection.CREDIT,
            ),
            Posting(
                account_id=platform_account_id,
                amount_cents=platform_fee_cents,
                direction=PostingDirection.CREDIT,
            ),
        ]

        entry = JournalEntry(
            entry_id=f"je-{uuid.uuid4().hex[:8]}",
            idempotency_key=f"pay-{trip_id}",
            correlation_id=trip_id,
            description=f"Fare settlement for trip {trip_id}",
            postings=postings,
        )

        self.ledger_repo.post_journal_entry(entry)
        return entry
