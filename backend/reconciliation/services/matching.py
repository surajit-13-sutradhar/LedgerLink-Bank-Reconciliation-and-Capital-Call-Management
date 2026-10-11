import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

SUGGESTED = "suggested"
NEEDS_REVIEW = "needs_review"

LEGAL_SUFFIXES = {"LLC", "LP", "LTD", "INC"}


@dataclass(frozen=True)
class Candidate:
    id: int
    investor_name: str
    expected_reference: str
    amount_remaining: Decimal
    call_date: date


@dataclass(frozen=True)
class ProposedMatch:
    line_item_id: int
    reason: str


@dataclass(frozen=True)
class MatchResult:
    status: str                      
    matches: tuple                   
    review_reason: str = ""          # to be set when status is NEEDS_REVIEW


def normalize_reference(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())

def normalize_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()


def normalize_name(value: str) -> str:
    tokens = normalize_text(value).split()
    if tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens = tokens[:-1]
    return " ".join(tokens)


def name_found(name: str, description: str) -> bool:
    wanted = normalize_name(name)
    if not wanted:                    # a name that is only 'LLC' must never match
        return False
    return f" {wanted} " in f" {normalize_text(description)} "

def is_eligible(item: Candidate, txn_date: date) -> bool:
    return item.amount_remaining > 0 and item.call_date <= txn_date

def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def match_credit(
    *,
    txn_date: date,
    amount: Decimal,
    description: str,
    bank_reference: str,
    candidates,
) -> MatchResult:
    eligible = sorted(
        (c for c in candidates if is_eligible(c, txn_date)), key=lambda c: c.id
    )

    haystacks = (normalize_reference(description), normalize_reference(bank_reference))
    by_reference = [
        c for c in eligible
        if normalize_reference(c.expected_reference)
        and any(normalize_reference(c.expected_reference) in h for h in haystacks)
    ]

    if len(by_reference) == 1:
        item = by_reference[0]
        ref = item.expected_reference
        if amount > item.amount_remaining:
            return MatchResult(
                NEEDS_REVIEW, (),
                f"Reference {ref} found, but amount {_money(amount)} exceeds "
                f"remaining {_money(item.amount_remaining)} (overpayment).",
            )
        if amount == item.amount_remaining:
            reason = f"Reference {ref} found; amount equals remaining {_money(item.amount_remaining)}"
        else:
            reason = (
                f"Reference {ref} found; partial payment of {_money(amount)} "
                f"against remaining {_money(item.amount_remaining)}"
            )
        return MatchResult(SUGGESTED, (ProposedMatch(item.id, reason),))

    if len(by_reference) > 1:
        refs = ", ".join(c.expected_reference for c in by_reference)
        matches = tuple(
            ProposedMatch(
                c.id,
                f"Reference {c.expected_reference} found, but {len(by_reference)} "
                f"references matched; manual review required",
            )
            for c in by_reference
        )
        return MatchResult(
            NEEDS_REVIEW, matches,
            f"Multiple references found ({refs}); choose the correct line item.",
        )

    by_name = [
        c for c in eligible
        if c.amount_remaining == amount and name_found(c.investor_name, description)
    ]

    if len(by_name) == 1:
        item = by_name[0]
        reason = (
            f"investor name '{item.investor_name}' found; amount equals "
            f"remaining {_money(item.amount_remaining)}"
        )
        return MatchResult(SUGGESTED, (ProposedMatch(item.id, reason),))

    if len(by_name) > 1:
        names = ", ".join(f"{c.investor_name} ({c.expected_reference})" for c in by_name)
        matches = tuple(
            ProposedMatch(
                c.id,
                f"investor name '{c.investor_name}' found and amount equals remaining "
                f"{_money(c.amount_remaining)}, but {len(by_name)} line items fit; "
                f"manual selection required",
            )
            for c in by_name
        )
        return MatchResult(
            NEEDS_REVIEW, matches,
            f"several line items fit by name and amount: {names}.",
        )

    return MatchResult(
        NEEDS_REVIEW, (),
        "no eligible reference found, and no investor name with an exactly "
        "matching remaining amount.",
    )