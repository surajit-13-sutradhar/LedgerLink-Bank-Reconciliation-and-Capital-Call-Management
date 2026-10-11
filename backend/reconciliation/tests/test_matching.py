from datetime import date
from decimal import Decimal
from unittest import TestCase

from reconciliation.services.matching import (
    NEEDS_REVIEW, SUGGESTED, Candidate, match_credit,
    name_found, normalize_name, normalize_reference,
)

D = Decimal
CALL = date(2026, 3, 25)
TXN = date(2026, 4, 3)


def item(id, name, ref, remaining, call_date=CALL):
    return Candidate(id, name, ref, D(remaining), call_date)


POOL = [
    item(1, "Haller Capital LLC", "CC-1001", "27500.00"),
    item(2, "Rahul Shah Trust", "CC-1002", "25000.00"),
    item(3, "Patel Family Trust", "CC-1003", "12500.00"),
    item(4, "Meridian Partners LP", "CC-1004", "15000.00"),
    item(5, "Oakridge Holdings LLC", "CC-1005", "15000.00"),
    item(6, "Oakridge Holdings LLC", "CC-1006", "15000.00", date(2026, 4, 1)),
]


def run(description, amount, bank_reference="FT1", pool=POOL, when=TXN):
    return match_credit(
        txn_date=when, amount=D(amount), description=description,
        bank_reference=bank_reference, candidates=pool,
    )


def ids(result):
    return [m.line_item_id for m in result.matches]


class NormalisationTests(TestCase):
    def test_reference(self):
        self.assertEqual(normalize_reference("cc-1003"), "CC1003")
        self.assertEqual(normalize_reference("CC 1003"), "CC1003")
        self.assertEqual(normalize_reference("cc1001"), "CC1001")
        self.assertEqual(normalize_reference("CC–1001é"), "CC1001")  # non-ASCII dropped

    def test_name_drops_one_trailing_suffix_keeps_trust(self):
        self.assertEqual(normalize_name("Haller Capital LLC"), "HALLER CAPITAL")
        self.assertEqual(normalize_name("Meridian Partners, L.P."), "MERIDIAN PARTNERS L P")
        self.assertEqual(normalize_name("Acme Inc."), "ACME")
        self.assertEqual(normalize_name("Patel Family Trust"), "PATEL FAMILY TRUST")

    def test_whole_word_only(self):
        self.assertTrue(name_found("Oakridge Holdings LLC", "WIRE OAKRIDGE HOLDINGS"))
        self.assertFalse(name_found("Oak LLC", "WIRE OAKRIDGE HOLDINGS"))
        self.assertFalse(name_found("LLC", "ANY LLC WIRE"))   # empty name never matches


class ReferenceTests(TestCase):
    def test_spec_example_reference(self):
        r = run("WIRE INCOMING RAHUL SHAH TRUST REF CC-1002", "25000.00")
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [2]))
        self.assertIn("CC-1002", r.matches[0].reason)

    def test_lowercase_no_dash(self):
        r = run("payment cc1001", "27500.00")
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [1]))

    def test_reference_in_bank_reference(self):
        r = run("WIRE", "1000.00", bank_reference="CC-1002-X")
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [2]))

    def test_partial_payment(self):
        r = run("REF CC-1001", "20000.00")
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [1]))
        self.assertIn("partial", r.matches[0].reason)

    def test_overpayment_has_no_match(self):
        r = run("REF CC-1003", "13000.00")
        self.assertEqual((r.status, ids(r)), (NEEDS_REVIEW, []))
        self.assertIn("overpayment", r.review_reason)

    def test_multiple_references_all_proposed(self):
        r = run("CC-1001 CC-1002", "100.00")
        self.assertEqual((r.status, ids(r)), (NEEDS_REVIEW, [1, 2]))
        self.assertTrue(r.review_reason)

    def test_reference_found_skips_name_step(self):
        # reference points at CC-1002 with an overpayment; Patel name+amount would
        # match CC-1003, but step 2 must not run
        r = run("PATEL FAMILY TRUST CC-1002", "12500.00")
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [2]))

    def test_call_date_after_transaction_date_not_eligible(self):
        r = run("REF CC-1006", "100.00", when=date(2026, 3, 30))
        self.assertEqual((r.status, ids(r)), (NEEDS_REVIEW, []))

    def test_funded_line_item_not_eligible(self):
        pool = [item(1, "Haller Capital LLC", "CC-1001", "0.00")]
        r = run("REF CC-1001", "100.00", pool=pool)
        self.assertEqual((r.status, ids(r)), (NEEDS_REVIEW, []))


class NameTests(TestCase):
    def test_spec_example_name_and_amount(self):
        r = run("WIRE INCOMING PATEL FAMILY TRUST", "12500.00")
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [3]))

    def test_suffix_and_case_ignored(self):
        r = run("  wire incoming meridian partners  ", "15000.00")
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [4]))

    def test_amount_must_equal_remaining(self):
        r = run("PATEL FAMILY TRUST", "12499.99")
        self.assertEqual((r.status, ids(r)), (NEEDS_REVIEW, []))

    def test_same_investor_in_two_calls_gives_two_candidates(self):
        r = run("OAKRIDGE HOLDINGS", "15000.00", when=date(2026, 4, 11))
        self.assertEqual((r.status, ids(r)), (NEEDS_REVIEW, [5, 6]))
        self.assertTrue(r.review_reason)

    def test_later_call_not_yet_eligible_leaves_one_candidate(self):
        r = run("OAKRIDGE HOLDINGS", "15000.00", when=date(2026, 3, 30))
        self.assertEqual((r.status, ids(r)), (SUGGESTED, [5]))

    def test_no_match(self):
        r = run("UNKNOWN INCOMING WIRE", "9999.99")
        self.assertEqual((r.status, ids(r)), (NEEDS_REVIEW, []))
        self.assertTrue(r.review_reason)