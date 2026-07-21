"""
Unit tests for the compliance guardrails.

These are the highest-value tests in the project: the guardrails are what keep a
SEBI-adjacent assistant from giving investment advice, echoing PII, or citing a
source it never retrieved. They run offline -- no ChromaDB, no Groq, no network.
"""
import pytest

from src.guardrails.pre_retrieval import PreRetrievalGuard
from src.guardrails.post_retrieval import PostRetrievalGuard
from src.guardrails.refusals import RefusalFormatter


# ---------------------------------------------------------------- PII detection

@pytest.mark.parametrize("query", [
    "My PAN is ABCDE1234F",
    "pan abcde1234f please",                 # case-insensitive
    "My aadhaar number is 123456789012",     # bare 12 digits + keyword
    "aadhar 1234-5678-9012",                 # hyphenated grouping
    "Here is my Aadhaar: 1234 5678 9012",    # spaced grouping
    "mail me at investor@example.com",
    "call me on 9876543210",
    "what is the OTP for my redemption",
    "share the one-time-password",
])
def test_detect_pii_flags_sensitive_input(query):
    assert PreRetrievalGuard.detect_pii(query) is True


@pytest.mark.parametrize("query", [
    "What is the exit load for HDFC Mid-Cap Opportunities Fund?",
    "What is the expense ratio?",
    "Who are the fund managers?",
    # Regression: a bare 12-digit run with no identity keyword is a figure,
    # not an Aadhaar number. This previously produced a false positive.
    "What is the fund size in crores 123456789012",
    "AUM is 97,350.48 Cr as of today",
    "NAV is 225.63",
])
def test_detect_pii_allows_ordinary_fund_questions(query):
    assert PreRetrievalGuard.detect_pii(query) is False


# ------------------------------------------------------------ Intent classification

@pytest.mark.parametrize("query", [
    "Should I invest in HDFC Small Cap Fund?",
    "should i buy this fund",
    "Which is better, mid cap or small cap?",
    "where to invest my money",
    "can you recommend a fund",
    "I need investment advice",
    "is it safe to invest in gold funds",
    # --- Regression: these all bypassed the guard and were answered as factual.
    # Each is a request for unlicensed investment advice.
    "Is HDFC Small Cap a good investment for me?",
    "Which fund gives the best returns?",
    "suggest a fund for retirement",
    "what is the best fund",
    "what is the top performing scheme",
    "is this worth investing",
    "help me choose a fund",
    "how much should i invest",
    "which fund is safer",
    "what should i do with my money",
    "which scheme should I pick",
    "is this a good bet",
    "what is the ideal plan for my portfolio",
    "is this fund suitable for me",
    "could you suggest something",
    "what is the right fund for my goals",
    "is it wise to invest now",
])
def test_classify_intent_blocks_advisory(query):
    assert PreRetrievalGuard.classify_intent(query) == "advisory"


@pytest.mark.parametrize("query", [
    "What is the NAV of HDFC Large Cap Fund?",
    "What is the minimum SIP amount?",
    "Who manages HDFC Multi Cap Fund?",
    # Comparison/performance queries are intentionally routed to 'factual'
    # and constrained by the generation prompt instead of being refused here.
    "compare HDFC vs SBI small cap",
    "what were the returns of HDFC Gold ETF",
    # The broadened advisory patterns must not swallow ordinary lookups.
    "What is the exit load?",
    "What is the expense ratio of SBI Pharma Fund?",
    "What is the AUM?",
    "What is the benchmark index?",
    "What is the riskometer rating?",
    "Who are the fund managers?",
    "What is the investment objective?",
    "When was the fund launched?",
    "What is the lock-in period?",
    "Is there an exit load after one year?",
    "What is the portfolio turnover ratio?",
    "How is the expense ratio calculated?",
    "What does AUM stand for?",
    "List the top holdings",
])
def test_classify_intent_allows_factual(query):
    assert PreRetrievalGuard.classify_intent(query) == "factual"


def test_classify_intent_returns_only_known_labels():
    """Guards against reintroducing an intent the API does not handle."""
    labels = {
        PreRetrievalGuard.classify_intent(q)
        for q in ["should i buy", "what is the nav", "compare a vs b", ""]
    }
    assert labels <= {"advisory", "factual"}


# -------------------------------------------------------------- Sentence counting

@pytest.mark.parametrize("text,expected", [
    ("The exit load is 1%.", 1),
    ("The NAV is 225.63. The AUM is 97,350.48 Cr.", 2),        # decimals not split
    ("One. Two. Three.", 3),
    ("The fee is 1.5% p.a. and applies monthly.", 1),          # abbreviation kept whole
    ("Managed by SIP. desk.", 1),
    ("What is the NAV? It is 225.63!", 2),                     # ? and ! terminate
])
def test_count_sentences(text, expected):
    assert PostRetrievalGuard.count_sentences(text) == expected


def test_count_sentences_ignores_source_line_and_url():
    answer = "The exit load is 1%.\nSource: https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    assert PostRetrievalGuard.count_sentences(answer) == 1


# ------------------------------------------------------------- Output validation

CONTEXT_URLS = [
    "https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth",
    "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
]


def test_validate_output_accepts_well_formed_answer():
    answer = (
        "The exit load is 1% if redeemed within one year.\n"
        "Source: https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    )
    assert PostRetrievalGuard.validate_output("q", answer, CONTEXT_URLS) is True


def test_validate_output_tolerates_url_normalisation():
    """A trailing slash or www. prefix must not fail an otherwise valid citation."""
    answer = (
        "The exit load is 1%.\n"
        "Source: https://www.groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth/"
    )
    assert PostRetrievalGuard.validate_output("q", answer, CONTEXT_URLS) is True


def test_validate_output_rejects_hallucinated_source():
    """The core anti-hallucination check: cited URL must come from retrieved context."""
    answer = "The exit load is 1%.\nSource: https://evil.example.com/made-up"
    assert PostRetrievalGuard.validate_output("q", answer, CONTEXT_URLS) is False


def test_validate_output_rejects_missing_source():
    assert PostRetrievalGuard.validate_output("q", "The exit load is 1%.", CONTEXT_URLS) is False


def test_validate_output_rejects_multiple_sources():
    answer = (
        "The exit load is 1%.\n"
        "Source: https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth "
        "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth"
    )
    assert PostRetrievalGuard.validate_output("q", answer, CONTEXT_URLS) is False


def test_validate_output_rejects_over_three_sentences():
    answer = (
        "One thing. Two things. Three things. Four things.\n"
        "Source: https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth"
    )
    assert PostRetrievalGuard.validate_output("q", answer, CONTEXT_URLS) is False


def test_validate_output_rejects_empty_answer():
    assert PostRetrievalGuard.validate_output("q", "", CONTEXT_URLS) is False


# --------------------------------------------------------------------- Refusals

def test_refusals_are_non_empty_and_distinct():
    messages = [
        RefusalFormatter.get_advisory_refusal(),
        RefusalFormatter.get_pii_refusal(),
        RefusalFormatter.get_out_of_context_refusal(),
    ]
    assert all(m.strip() for m in messages)
    assert len(set(messages)) == 3


def test_advisory_refusal_does_not_itself_trip_the_advisory_guard():
    """A refusal that looks like advice would be an embarrassing loop."""
    refusal = RefusalFormatter.get_advisory_refusal()
    assert "cannot provide investment advice" in refusal.lower()
