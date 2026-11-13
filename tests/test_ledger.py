"""
tests/test_ledger.py - Unit tests for Double-Entry Financial Ledger & Cents Precision Billing.
"""

import pytest
from internal.domain.ledger import (
    Account,
    AccountType,
    DoubleEntryLedgerError,
    InsufficientFundsError,
    JournalEntry,
    Posting,
    PostingDirection,
    UnbalancedJournalEntryError,
)
from internal.repository.ledger_repo import InMemoryLedgerRepository
from internal.service.billing_service import BillingService


def test_journal_entry_enforces_double_entry_balance():
    # 2000 cents fare ($20.00): 400 cents platform fee ($4.00) + 1600 cents driver payout ($16.00)
    postings = [
        Posting(account_id="ACC-RIDER", amount_cents=2000, direction=PostingDirection.DEBIT),
        Posting(account_id="ACC-PLATFORM", amount_cents=400, direction=PostingDirection.CREDIT),
        Posting(account_id="ACC-DRIVER", amount_cents=1600, direction=PostingDirection.CREDIT),
    ]

    entry = JournalEntry(
        entry_id="JE-001",
        idempotency_key="pay-key-1",
        correlation_id="trip-101",
        description="Trip settlement",
        postings=postings,
    )
    assert entry.total_debit_cents == 2000
    assert entry.total_credit_cents == 2000


def test_unbalanced_journal_entry_rejected():
    # Unbalanced: 2000 debit vs 1900 credit (leak of 100 cents!)
    bad_postings = [
        Posting(account_id="ACC-RIDER", amount_cents=2000, direction=PostingDirection.DEBIT),
        Posting(account_id="ACC-PLATFORM", amount_cents=400, direction=PostingDirection.CREDIT),
        Posting(account_id="ACC-DRIVER", amount_cents=1500, direction=PostingDirection.CREDIT),
    ]

    with pytest.raises(UnbalancedJournalEntryError, match="Unbalanced journal entry"):
        JournalEntry(
            entry_id="JE-BAD",
            idempotency_key="pay-key-bad",
            correlation_id="trip-102",
            description="Leaky entry",
            postings=bad_postings,
        )


def test_negative_or_zero_posting_rejected():
    with pytest.raises(DoubleEntryLedgerError, match="Posting amount must be strictly positive"):
        Posting(account_id="ACC-RIDER", amount_cents=-500, direction=PostingDirection.DEBIT)

    with pytest.raises(DoubleEntryLedgerError, match="Posting amount must be strictly positive"):
        Posting(account_id="ACC-RIDER", amount_cents=0, direction=PostingDirection.DEBIT)


def test_billing_service_end_to_end_settlement():
    repo = InMemoryLedgerRepository()
    billing = BillingService(repo)

    # Setup accounts:
    # Rider has $50.00 (5000 cents) initial balance in wallet
    rider_acc = Account("ACC-RIDER-ALICE", "ALICE", AccountType.ASSET, initial_balance_cents=5000)
    # Driver has $0.00
    driver_acc = Account("ACC-DRIVER-BOB", "BOB", AccountType.LIABILITY, initial_balance_cents=0)
    # Platform revenue account
    platform_acc = Account("ACC-UBER-REVENUE", "UBER", AccountType.REVENUE, initial_balance_cents=0)

    repo.create_account(rider_acc)
    repo.create_account(driver_acc)
    repo.create_account(platform_acc)

    # Settle trip fare of $25.00 (2500 cents) with 20% platform commission ($5.00 = 500 cents)
    entry = billing.settle_trip_fare(
        trip_id="trip-999",
        rider_account_id=rider_acc.account_id,
        driver_account_id=driver_acc.account_id,
        platform_account_id=platform_acc.account_id,
        fare_cents=2500,
        platform_fee_percent=0.20,
    )

    # Verify balances:
    # Rider wallet: 5000 - 2500 = 2500 cents ($25.00)
    assert repo.get_account("ACC-RIDER-ALICE").balance_cents == 2500
    # Driver payout: 0 + 2000 = 2000 cents ($20.00)
    assert repo.get_account("ACC-DRIVER-BOB").balance_cents == 2000
    # Platform revenue: 0 + 500 = 500 cents ($5.00)
    assert repo.get_account("ACC-UBER-REVENUE").balance_cents == 500

    # Invariant: Sum of all accounts remains balanced
    assert entry.total_debit_cents == 2500
    assert entry.total_credit_cents == 2500


def test_billing_insufficient_funds_rejected():
    repo = InMemoryLedgerRepository()
    billing = BillingService(repo)

    # Rider only has $5.00 (500 cents)
    rider_acc = Account("ACC-BROKE", "CHARLIE", AccountType.ASSET, initial_balance_cents=500)
    driver_acc = Account("ACC-DRIVER-2", "DAN", AccountType.LIABILITY, initial_balance_cents=0)
    platform_acc = Account("ACC-REV-2", "UBER", AccountType.REVENUE, initial_balance_cents=0)

    repo.create_account(rider_acc)
    repo.create_account(driver_acc)
    repo.create_account(platform_acc)

    # Attempt to charge $15.00 (1500 cents)
    with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
        billing.settle_trip_fare(
            trip_id="trip-fail",
            rider_account_id=rider_acc.account_id,
            driver_account_id=driver_acc.account_id,
            platform_account_id=platform_acc.account_id,
            fare_cents=1500,
        )

    # Balances must remain untouched
    assert repo.get_account("ACC-BROKE").balance_cents == 500
