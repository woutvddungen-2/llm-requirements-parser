import pytest

from src.page_finding import (
    _contains_actionable_access_sentence,
    _extract_relevant_excerpt,
    _find_from_scores,
    _find_hybrid_pages,
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
        find_relevant_pages(pdf_path=pdf_path, strategy="bogus")


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


def test_extract_relevant_excerpt_skips_inventory_and_keeps_actionable_blocks():
    text = """
Algemene voorzieningen
- Videofoon-/intercom installatie
- Toegangscontrole parkeergarage
- Toegangscontrolesysteem fietsenstalling

Toegangscontrolesysteem
De deuren tussen de algemene verkeersruimten en de parkeergarage zijn in basis gesloten (elektrisch slot).
Aan de zijde van de parkeergarage wordt er naast de deur een groene melder geplaatst zodat bewoners bij nood kunnen ontgrendelen.
"""

    excerpt = _extract_relevant_excerpt(text)

    assert "Algemene voorzieningen" not in excerpt
    assert "groene melder" in excerpt
    assert "elektrisch slot" in excerpt


def test_extract_relevant_excerpt_drops_abstract_gate_block_when_concrete_door_blocks_exist():
    text = """
Toegangscontrolesysteem
De toegangscontrole installatie omvat niet meer dan de open/dichtsturing van de speedgate met eigen afstandsbediening (handzender) door de bewoners zelf.

De deuren tussen de algemene verkeersruimten en de parkeergarage zijn in basis gesloten (elektrisch slot).
Aan de zijde van de parkeergarage wordt er naast de deur een groene melder geplaatst zodat bewoners bij nood kunnen ontgrendelen.
"""

    excerpt = _extract_relevant_excerpt(text)

    assert "speedgate" not in excerpt
    assert "handzender" not in excerpt
    assert "elektrisch slot" in excerpt
    assert "groene melder" in excerpt


def test_find_hybrid_pages_prefers_dominant_overlap_cluster():
    relevant, primary, neighbors = _find_hybrid_pages(
        kw_relevant=[68, 69, 85, 86, 87],
        kw_primary=[69, 86],
        rx_relevant=[68, 69, 81, 82, 83, 86, 87],
        rx_primary=[69, 81, 86],
        combined_scores={
            68: 22,
            69: 71,
            81: 54,
            82: 40,
            83: 30,
            85: 2,
            86: 211,
            87: 22,
        },
    )

    assert relevant == [86, 87]
    assert primary == [69, 86]
    assert neighbors == [87]


def test_contains_actionable_access_sentence_rejects_inventory_but_keeps_requirements():
    inventory = "Videofoon-/intercom installatie\nToegangscontrole parkeergarage\nToegangscontrolesysteem fietsenstalling"
    requirement = (
        "De deuren tussen de algemene verkeersruimten en de parkeergarage zijn voorzien van een "
        "elektronisch sluitsysteem en naast de deur wordt een kaartlezer geplaatst."
    )

    assert _contains_actionable_access_sentence(inventory) is False
    assert _contains_actionable_access_sentence(requirement) is True


def test_find_from_scores_then_cluster_prune_prefers_dense_access_block():
    page_scores = {
        68: 19,
        69: 62,
        81: 40,
        82: 40,
        83: 19,
        86: 128,
        87: 10,
        88: 27,
    }

    relevant, _, _ = _find_from_scores(
        page_scores,
        score_threshold=40,
        neighbor_threshold=13,
        high_score_threshold=60,
    )

    from src.page_finding import _prune_to_dominant_clusters

    pruned = _prune_to_dominant_clusters(relevant, page_scores, keep_ratio=0.75)

    assert pruned == [86]
