from __future__ import annotations
import re
from dataclasses import dataclass

# Category-based section scoring for precise page classification
SECTION_CATEGORIES = {
    "ACCESS": {
        "keywords": {
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
        },
        "regex": [
            (r"\btoegangscontrole(?:systeem|centrale|centrales)?\b", 12),
            (r"\btoegangs?-systeem\b", 10),
            (r"\bkaartlezers?\b|\bpaslezers?\b|\bbadge\b", 10),
            (r"\bintercom\b|\bspreek(?:unit|verbinding)\b", 10),
            (r"\bdeurcontact(?:en)?\b|\bdeurstandmelders?\b", 9),
            (r"\bnood(?:druk)?knop\b|\bontgrendeldrukknop\b|\bgroene handmelder\b", 9),
            (r"\bmiva-openingsysteem\b|\belleboogschakelaar\b|\bradar\b", 8),
            (r"\bspeedgate\b|\bslagboom\b|\bin- en uitrijlussen\b", 8),
            (r"\b(elektrisch|elektronisch)e? slot(?:en)?\b|\bsluitsysteem\b", 8),
            (r"\bdatabus\b|\bdeurcontrole-eenheden?\b|\btoegangscontrolecentrales?\b", 8),
            (r"\bsluit-.*alarmeringmechanisme\b", 9),
            (r"^\s*(?:4\.)?12\.(?:2[1-9]|3[0-9]|4[0-9])\b", 11),
        ]
    },
    "CAMERA": {
        "keywords": {
            "camera": 10,
            "camerasysteem": 10,
            "camerasystemen": 10,
            "cctv": 10,
            "beeldopslag": 8,
            "beeldscherm": 5,
            "monitor": 3,
        },
        "regex": [
            (r"\bcamera(?:-installatie|-systeem)?s?\b", 10),
            (r"\bcctv\b|\bcamera-installaties\b", 10),
        ]
    },
    "FIRE": {
        "keywords": {
            "vluchtdeur": 10,
            "nooddeur": 10,
            "nooduitgang": 10,
            "ontsnapping": 8,
            "branddeuren": 8,
            "brandblusser": 7,
            "vluchtrouteverlichting": 8,
            "antipaniekverlichting": 8,
            "brandweer": 5,
        },
        "regex": [
            (r"\bvluchtdeuren?\b|\bnooddeuren?\b|\bnooduitgang\b", 10),
            (r"\bontsnappingsroute\b|\bvluchtrouteverlichting\b", 9),
            (r"\bpaniekslot\b|\bontgrendeling\b", 8),
            (r"\bbrandslanghaspels?\b|\bbrandblussers?\b", 7),
        ]
    },
    "HVAC": {
        "keywords": {
            "klimaat": 10,
            "verwarming": 8,
            "koeling": 8,
            "ventilatie": 8,
            "temperatuur": 7,
            "luchtkwaliteit": 7,
            "afzuiging": 8,
            "ventilatierooster": 7,
        },
        "regex": [
            (r"\bklimaat(?:installatie)?s?\b", 10),
            (r"\bverwarming\b|\bkoeling\b|\bventilatie\b", 8),
            (r"\btemperatuur\b|\bluchtkwaliteit\b", 7),
        ]
    },
    "ELECTRICAL": {
        "keywords": {
            "elektra": 8,
            "groepenkast": 8,
            "stroomvoorziening": 7,
            "voeding": 5,
            "contactdoos": 5,
            "elektragroepenkast": 8,
        },
        "regex": [
            (r"\belektragroepenkast\b|\bgroepenkast\b", 8),
            (r"\bstroomvoorziening\b|\bvoeding\b", 7),
        ]
    },
    "INTRUSION": {
        "keywords": {
            "inbraak": 10,
            "inbraakdetectie": 10,
            "alarm": 8,
            "alarmsysteem": 8,
            "alarmeringmechanisme": 7,
            "inbraakalarm": 9,
        },
        "regex": [
            (r"\binbraak(?:detectie|alarm)?\b", 10),
            (r"\balarmsysteem\b|\balarm\b", 8),
            (r"\balarmeringmechanisme\b", 7),
        ]
    }
}

@dataclass
class PageCategoryScores:
    """Scores for a single page across all categories."""
    page_num: int
    scores: dict[str, int]  # category -> score

    @property
    def primary_category(self) -> str | None:
        """Get the category with the highest score."""
        if not self.scores:
            return None
        return max(self.scores, key=self.scores.get)

    @property
    def is_access_heavy(self) -> bool:
        """True if ACCESS is primary category and score is significant."""
        return (self.primary_category == "ACCESS" and
                self.scores.get("ACCESS", 0) >= 15)

    @property
    def is_hvac_heavy(self) -> bool:
        """True if HVAC is primary category and dominates."""
        hvac_score = self.scores.get("HVAC", 0)
        access_score = self.scores.get("ACCESS", 0)
        return hvac_score > 0 and hvac_score >= access_score * 1.5

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
