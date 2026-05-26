import pytest

from src.page_finding import (
    _find_from_scores,
    _find_from_text_toc,
    _looks_like_toc_page,
    _score_pages_by_regex,
    find_relevant_pages,
)
from src.page_finding_ac_config import AC_REGEX_PATTERNS


def test_score_pages_by_regex_finds_access_control_language():
    page_texts = {
        0: "Algemene bouwkundige eisen zonder beveiliging.",
        1: (
            "De toegangsdeuren dienen te worden voorzien van kaartlezers en "
            "ontgrendeldrukknop. De toegangscontrolecentrales worden middels een databus gekoppeld."
        ),
    }

    scores = _score_pages_by_regex(page_texts, AC_REGEX_PATTERNS)

    assert scores[1] > scores[0]
    assert scores[1] > 0


def test_find_from_scores_keeps_neighbor_pages_for_context():
    page_scores = {
        10: 20,
        11: 4,
        12: 0,
    }

    relevant, primary, neighbors = _find_from_scores(
        page_scores,
        score_threshold=15,
        neighbor_threshold=3,
        high_score_threshold=15,
    )

    assert relevant == [10, 11]
    assert primary == [10]
    assert neighbors == [11]


def test_find_relevant_pages_rejects_unknown_strategy(tmp_path):
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_text("not a real pdf", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown page-finder strategy"):
        find_relevant_pages(pdf_path=pdf_path, strategy="hybrid")


def test_looks_like_toc_page_detects_textual_contents():
    text = """INHOUD
31.1 Automatische toegangsdeuren 44
32.9 Beveiligingsvoorzieningen 51
64.4 Data 195
65.4 Inbraakdetectie 203
65.5 Toegangscontrole installatie 203
"""
    assert _looks_like_toc_page(text) is True


def test_find_from_text_toc_selects_access_control_pages():
    page_texts = {
        0: "Titelpagina",
        1: """INHOUD
31.1 Automatische toegangsdeuren 44
32.9 Beveiligingsvoorzieningen 51
64.4 Data 195
65.4 Inbraakdetectie 203
65.5 Toegangscontrole installatie 203
74. Sanitair 210
""",
        43: "Automatische toegangsdeuren",
        50: "Beveiligingsvoorzieningen",
        194: "Data",
        202: "Inbraakdetectie en toegangscontrole",
        209: "Sanitair",
    }

    method, pages = _find_from_text_toc(
        page_texts,
        {
            "toegangscontrole": 10,
            "beveiliging": 1,
            "automatische toegangsdeuren": 10,
            "inbraakdetectie": 10,
        },
        {
            43: 8,
            50: 5,
            194: 0,
            202: 12,
            209: 0,
        },
    )

    assert method == "Text TOC"
    assert pages == [43, 50, 202]
