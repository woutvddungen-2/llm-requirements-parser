from __future__ import annotations

AC_KEYWORDS: dict[str, int] = {
    "toegangscontrole": 10,
    "kaartlezer": 10,
    "speedgate": 10,
    "handzender": 8,
    "elleboogschakelaar": 8,
    "sluitsysteem": 7,
    "toegangspas": 8,
    "paslezer": 8,
    "badge": 7,
    "elektrisch slot": 5,
    "groene handmelder": 5,
    "groene knop": 5,
    "toegangsdeur": 4,
    "tag": 3,
    "lezer": 3,
    "reader": 3,
    "beveiliging": 1,
    "beveiligingsinstallatie": 2,
    "deur": 1,
    "slot": 2,
}

HIGH_SCORE_THRESHOLD = 15
SCORE_THRESHOLD = 15
NEIGHBOR_THRESHOLD = 3

PAGE_FINDER_SYSTEM_PROMPT = """You identify which pages in a document summary contain access control requirements.
Return only valid JSON with a single key named page_numbers.
The value must be a list of integers.
"""

PAGE_FINDER_PROMPT = """You are analyzing a specification document for a building access control installation.
Below is a summary of each page (first 500 characters).
Identify which pages contain access control requirements such as secured areas, door access rules, reader types, lock types, or controller requirements.
Return ONLY valid JSON in the form {"page_numbers": [1, 4, 5]}.

{page_summary}
"""
