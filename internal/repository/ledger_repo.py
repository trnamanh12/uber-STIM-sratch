"""
internal/repository/ledger_repo.py - Persistence Contracts & In-Memory Store for Ledger.
"""

from abc import ABC, abstractmethod
import copy
import threading
from typing import Dict, List, Optional
from internal.domain.ledger import Account, DoubleEntryLedgerError, JournalEntry


class LedgerRepository(ABC):
    @abstractmethod
    def create_account(self, account: Account) -> None:
        pass

    @abstractmethod
    def get_account(self, account_id: str) -> Optional[Account]:
        pass

    @abstractmethod
    def post_journal_entry(self, entry: JournalEntry) -> None:
        pass

    @abstractmethod
    def get_journal_entry_by_idempotency_key(self, key: str) -> Optional[JournalEntry]:
        pass


class InMemoryLedgerRepository(LedgerRepository):
    """Thread-safe transactional in-memory ledger repository."""

    def __init__(self) -> None:
        self._accounts: Dict[str, Account] = {}
        self._entries: Dict[str, JournalEntry] = {}
        self._idempotency_registry: Dict[str, str] = {}  # key -> entry_id
        self._lock = threading.Lock()

    def create_account(self, account: Account) -> None:
        with self._lock:
            self._accounts[account.account_id] = copy.copy(account)

    def get_account(self, account_id: str) -> Optional[Account]:
        with self._lock:
            acc = self._accounts.get(account_id)
            return copy.copy(acc) if acc else None

    def get_journal_entry_by_idempotency_key(self, key: str) -> Optional[JournalEntry]:
        with self._lock:
            entry_id = self._idempotency_registry.get(key)
            if entry_id:
                return self._entries.get(entry_id)
            return None

    def post_journal_entry(self, entry: JournalEntry) -> None:
        """
        Atomically applies all postings in a journal entry.
        Rolls back on any error to guarantee ACID consistency.
        """
        with self._lock:
            if entry.idempotency_key in self._idempotency_registry:
                # Idempotency deduplication: already posted
                return

            # Stage account snapshots for rollback capability
            staged_accounts = {}
            for posting in entry.postings:
                if posting.account_id not in self._accounts:
                    raise DoubleEntryLedgerError(f"Account not found: {posting.account_id}")
                if posting.account_id not in staged_accounts:
                    staged_accounts[posting.account_id] = copy.copy(self._accounts[posting.account_id])

            # Apply all postings to staged copies
            for posting in entry.postings:
                acc = staged_accounts[posting.account_id]
                acc.apply_posting(posting.direction, posting.amount_cents)

            # If all succeeded without exception, commit staged accounts and record entry
            for acc_id, acc in staged_accounts.items():
                self._accounts[acc_id] = acc

            self._entries[entry.entry_id] = entry
            self._idempotency_registry[entry.idempotency_key] = entry.entry_id
