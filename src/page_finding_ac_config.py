from __future__ import annotations
import re

AC_KEYWORDS: dict[str, int] = {
    "toegangscontrole": 10,
    "kaartlezer": 10,
    "kaartlezers": 10,
    "speedgate": 10,
    "handzender": 8,
    "elleboogschakelaar": 8,
    "sluitsysteem": 7,
    "toegangspas": 8,
    "paslezer": 8,
    "badge": 7,
    "elektrisch slot": 5,
    "groene handmelder": 5,
    "groene melder": 5,
    "groene knop": 5,
    "toegangsdeur": 4,
    "deurstandmelder": 8,
    "deurstandmelders": 8,
    "intercom": 9,
    "noodknop": 8,
    "nooddrukknop": 8,
    "tag": 3,
    "lezer": 3,
    "reader": 3,
    "beveiliging": 1,
    "beveiligingsinstallatie": 2,
    "deur": 1,
    "slot": 2,
}

AC_REGEX_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\btoegangscontrole(?:systeem|centrale|centrales)?\b", re.IGNORECASE), 12),
    (re.compile(r"\btoegangs?-systeem\b", re.IGNORECASE), 10),
    (re.compile(r"\bkaartlezers?\b|\bpaslezers?\b|\bbadge\b", re.IGNORECASE), 10),
    (re.compile(r"\bintercom\b|\bspreek(?:unit|verbinding)\b", re.IGNORECASE), 10),
    (re.compile(r"\bdeurcontact(?:en)?\b|\bdeurstandmelders?\b", re.IGNORECASE), 9),
    (re.compile(r"\bnood(?:druk)?knop\b|\bontgrendeldrukknop\b|\bgroene handmelder\b|\bgroene melder\b", re.IGNORECASE), 9),
    (re.compile(r"\bmiva-openingsysteem\b|\belleboogschakelaar\b|\bradar\b", re.IGNORECASE), 8),
    (re.compile(r"\bspeedgate\b|\bslagboom\b|\bin- en uitrijlussen\b", re.IGNORECASE), 8),
    (re.compile(r"\b(elektrisch|elektronisch)e? slot(?:en)?\b|\bsluitsysteem\b", re.IGNORECASE), 8),
    (re.compile(r"\bdatabus\b|\bdeurcontrole-eenheden?\b|\btoegangscontrolecentrales?\b", re.IGNORECASE), 8),
    (re.compile(r"\bsluit-.*alarmeringmechanisme\b", re.IGNORECASE), 9),
    (re.compile(r"^\s*(?:4\.)?12\.(?:2[1-9]|3[0-9]|4[0-9])\b", re.IGNORECASE | re.MULTILINE), 11),
    (re.compile(r"^\s*\d+(?:\.\d+){0,3}\s+(?:toegang|toegangscontrole|beveiliging|inbraakdetectie|automatische toegangsdeuren)\b", re.IGNORECASE | re.MULTILINE), 12),
)

HIGH_SCORE_THRESHOLD = 20
SCORE_THRESHOLD = 25
NEIGHBOR_THRESHOLD = 2
REGEX_SCORE_THRESHOLD = 20
REGEX_NEIGHBOR_THRESHOLD = 2
REGEX_HIGH_SCORE_THRESHOLD = 12

PAGE_FINDER_SYSTEM_PROMPT = """You identify which pages in a document summary contain access control requirements.
Return only valid JSON with a single key named page_numbers.
The value must be a list of integers.
"""

PAGE_FINDER_PROMPT = """You are analyzing a specification document for a building access control installation.
Below is a summary of each page (first 500 characters).
Identify which pages contain access control requirements such as secured areas, door access rules, reader types, lock types, or controller requirements.
Return ONLY valid JSON in the form {{"page_numbers": [1, 4, 5]}}.

{page_summary}
"""
