"""
internal/domain/ledger.py - Double-Entry Bookkeeping Ledger & Cents Precision Billing.

Zero external dependencies. Pure financial invariants.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import List, Optional
from internal.domain.trip import DomainError


class DoubleEntryLedgerError(DomainError):
    """Base exception for financial ledger violations."""
    pass


class UnbalancedJournalEntryError(DoubleEntryLedgerError):
    """Raised when sum(Debits) != sum(Credits)."""
    pass


class InsufficientFundsError(DoubleEntryLedgerError):
    """Raised when an account cannot satisfy a debit operation."""
    pass


class AccountType(str, Enum):
    ASSET = "ASSET"          # e.g., Cash, Rider Wallet
    LIABILITY = "LIABILITY"  # e.g., Driver Payout Owed
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"      # e.g., Platform Commission Revenue
    EXPENSE = "EXPENSE"


class PostingDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class Account:
    """Represents a financial ledger account tracked strictly in integer cents."""

    def __init__(
        self,
        account_id: str,
        holder_id: str,
        account_type: AccountType,
        initial_balance_cents: int = 0,
    ) -> None:
        if not account_id or not account_id.strip():
            raise DoubleEntryLedgerError("Account ID cannot be empty")
        if not holder_id or not holder_id.strip():
            raise DoubleEntryLedgerError("Holder ID cannot be empty")
        if not isinstance(initial_balance_cents, int):
            raise DoubleEntryLedgerError("Balance must be an integer (cents)")

        self.account_id = account_id
        self.holder_id = holder_id
        self.account_type = account_type
        self.balance_cents = initial_balance_cents

    def apply_posting(self, direction: PostingDirection, amount_cents: int) -> None:
        """
        Applies a posting adhering to double-entry accounting rules:
        - For ASSET: Debit increases funds, Credit decreases funds (or pays out).
          For a consumer wallet, spending funds is a reduction in wallet balance.
        - For REVENUE & LIABILITY: Credit increases accumulated revenue / owed payouts.
        """
        if amount_cents <= 0:
            raise DoubleEntryLedgerError("Posting amount must be strictly positive")

        if self.account_type == AccountType.ASSET:
            if direction == PostingDirection.DEBIT:
                # Deducting funds from user's wallet
                if self.balance_cents < amount_cents:
                    raise InsufficientFundsError(
                        f"Insufficient funds in account {self.account_id}: "
                        f"Balance {self.balance_cents}c < Required {amount_cents}c"
                    )
                self.balance_cents -= amount_cents
            else:
                self.balance_cents += amount_cents

        elif self.account_type in {AccountType.LIABILITY, AccountType.REVENUE}:
            if direction == PostingDirection.CREDIT:
                self.balance_cents += amount_cents
            else:
                self.balance_cents -= amount_cents


@dataclass(frozen=True)
class Posting:
    """An individual debit or credit line in a journal entry."""
    account_id: str
    amount_cents: int
    direction: PostingDirection

    def __post_init__(self) -> None:
        if not isinstance(self.amount_cents, int) or self.amount_cents <= 0:
            raise DoubleEntryLedgerError(
                f"Posting amount must be strictly positive integer cents. Got: {self.amount_cents}"
            )


@dataclass(frozen=True)
class JournalEntry:
    """
    Atomic Double-Entry Journal Entry.
    Enforces the Invariant: Sum of Debits == Sum of Credits.
    """
    entry_id: str
    idempotency_key: str
    correlation_id: str
    description: str
    postings: List[Posting]
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if len(self.postings) < 2:
            raise DoubleEntryLedgerError("A journal entry must contain at least 2 postings")

        debits = sum(p.amount_cents for p in self.postings if p.direction == PostingDirection.DEBIT)
        credits = sum(p.amount_cents for p in self.postings if p.direction == PostingDirection.CREDIT)

        if debits != credits:
            raise UnbalancedJournalEntryError(
                f"Unbalanced journal entry {self.entry_id}: Total Debits ({debits}c) != Total Credits ({credits}c)"
            )

    @property
    def total_debit_cents(self) -> int:
        return sum(p.amount_cents for p in self.postings if p.direction == PostingDirection.DEBIT)

    @property
    def total_credit_cents(self) -> int:
        return sum(p.amount_cents for p in self.postings if p.direction == PostingDirection.CREDIT)
