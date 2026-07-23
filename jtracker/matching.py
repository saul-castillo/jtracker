"""Positive Summer 2027 and hardware-relevance matching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    score: int
    reasons: tuple[str, ...]
    rejection: str = ""


SEASON_PATTERN = re.compile(
    r"\b(?:(summer|fall|autumn|spring|winter)\s*(?:of\s*)?(20\d{2})"
    r"|(20\d{2})\s*(summer|fall|autumn|spring|winter))\b",
    re.IGNORECASE,
)
TITLE_SEASON_PATTERN = re.compile(
    r"\b(?:(summer|fall|autumn|spring|winter)\b.{0,35}?\b(20\d{2})"
    r"|(20\d{2})\b.{0,35}?\b(summer|fall|autumn|spring|winter))\b",
    re.IGNORECASE,
)
SHARED_YEAR_SUMMER_PATTERN = re.compile(
    r"(?:\bsummer\b(?:\s*(?:/|,|&|\band\b|\bor\b)\s*"
    r"(?:fall|autumn|spring|winter))*\s*(?:of\s*)?\b2027\b"
    r"|\b2027\b\s*(?:(?:fall|autumn|spring|winter)\s*"
    r"(?:/|,|&|\band\b|\bor\b)\s*)*\bsummer\b)",
    re.IGNORECASE,
)
INTERNSHIP_PATTERN = re.compile(r"\b(?:intern(?:ship)?|co[\s-]?op)\b", re.IGNORECASE)
TITLE_STUDENT_PATTERN = re.compile(r"\b(?:student|university|campus)\b", re.IGNORECASE)

TITLE_SIGNALS: dict[str, int] = {
    "analog": 14,
    "mixed-signal": 14,
    "mixed signal": 14,
    "electrical": 13,
    "hardware": 13,
    "asic": 13,
    "fpga": 13,
    "rtl": 13,
    "digital design": 13,
    "silicon": 12,
    "circuit": 12,
    "verification": 11,
    "validation": 11,
    "physical design": 12,
    "embedded": 11,
    "firmware": 11,
    "computer architecture": 11,
    "signal integrity": 11,
    "power integrity": 11,
    "radio frequency": 11,
    " rf ": 11,
    "pcb": 10,
    "board design": 11,
    "semiconductor": 10,
    "device engineer": 9,
    "process engineer": 9,
    "test engineer": 8,
    "product engineer": 8,
    "applications engineer": 8,
    "packaging": 9,
    "manufacturing engineer": 7,
    "controls": 8,
    "robotics": 7,
    "mechatronics": 8,
    "photonics": 9,
    "optical engineer": 8,
}

BODY_SIGNALS: dict[str, int] = {
    "systemverilog": 7,
    "verilog": 7,
    "vhdl": 7,
    "fpga": 6,
    "asic": 6,
    "register transfer level": 7,
    " rtl ": 6,
    "mixed-signal": 6,
    "mixed signal": 6,
    "analog circuit": 6,
    "digital circuit": 6,
    "circuit design": 6,
    "pcb": 6,
    "board bring-up": 7,
    "board bringup": 7,
    "schematic capture": 6,
    "signal integrity": 6,
    "power integrity": 6,
    "embedded system": 6,
    "embedded software": 6,
    "firmware": 6,
    "device driver": 6,
    "kernel": 5,
    "microcontroller": 6,
    "oscilloscope": 5,
    "logic analyzer": 5,
    "semiconductor device": 6,
    "wafer": 5,
    "physical design": 6,
    "static timing": 6,
    "design verification": 6,
    "hardware validation": 6,
    "silicon validation": 6,
    "post-silicon": 6,
    "pre-silicon": 6,
    "eda": 5,
    "electronic design automation": 6,
    "synopsys": 4,
    "cadence": 4,
    "spice": 5,
    "tapeout": 6,
    "radio frequency": 6,
    "rf circuit": 6,
    "power electronics": 6,
    "computer architecture": 6,
    "hardware architecture": 6,
    "packaging technology": 5,
    "materials characterization": 5,
    "electrical test": 5,
    "lab equipment": 4,
}

LOW_LEVEL_SIGNALS = {
    "firmware",
    "device driver",
    "kernel",
    "fpga",
    "asic",
    "rtl",
    "verilog",
    "vhdl",
    "silicon",
    "eda",
    "electronic design automation",
}
SOFTWARE_BODY_SIGNALS = {
    "firmware",
    "embedded system",
    "embedded software",
    "device driver",
    "kernel",
    "fpga",
    "asic",
    "rtl",
    "verilog",
    "vhdl",
    "silicon validation",
    "hardware validation",
    "eda",
    "electronic design automation",
}

SOFTWARE_TITLE_PATTERN = re.compile(
    r"\b(?:software|machine learning|data science|data engineer|front[\s-]?end|"
    r"back[\s-]?end|full[\s-]?stack|web|cloud|devops|site reliability|mobile)\b",
    re.IGNORECASE,
)
GENERIC_ENGINEERING_TITLE = re.compile(
    r"\b(?:engineer(?:ing)?|technical|technology|design|systems?)\b", re.IGNORECASE
)
SENIOR_TITLE_PATTERN = re.compile(
    r"\b(?:senior|staff|principal|manager|director|lead|full[\s-]?time)\b",
    re.IGNORECASE,
)
GRADUATE_ONLY_TITLE = re.compile(
    r"\b(?:ph\.?\s*d|doctoral|postdoc(?:toral)?|mba|master'?s?\s+only)\b",
    re.IGNORECASE,
)

METROS = (
    "san francisco",
    "bay area",
    "san jose",
    "santa clara",
    "sunnyvale",
    "mountain view",
    "austin",
    "boston",
    "cambridge",
    "new york",
    "seattle",
    "los angeles",
    "san diego",
    "denver",
    "phoenix",
    "chicago",
    "dallas",
    "raleigh",
    "durham",
    "washington",
    "arlington",
    "irvine",
    "baltimore",
    "philadelphia",
    "pittsburgh",
    "portland",
    "minneapolis",
)

STATE_NAMES = (
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
)
STATE_CODES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|"
    "MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|"
    "UT|VT|VA|WA|WV|WI|WY|DC"
)


def _season_pairs(text: str) -> set[tuple[str, str]]:
    pairs = set()
    for season, year, reverse_year, reverse_season in SEASON_PATTERN.findall(text):
        pairs.add(((season or reverse_season).lower(), year or reverse_year))
    return pairs


def _title_season_pairs(title: str) -> set[tuple[str, str]]:
    pairs = set()
    for season, year, reverse_year, reverse_season in TITLE_SEASON_PATTERN.findall(
        title
    ):
        pairs.add(((season or reverse_season).lower(), year or reverse_year))
    return pairs


def _generic_2027_internship(text: str) -> bool:
    for match in re.finditer(
        r"(?:\b2027\b.{0,55}\b(?:intern(?:ship)?|co[\s-]?op)\b"
        r"|\b(?:intern(?:ship)?|co[\s-]?op)\b.{0,55}\b2027\b)",
        text,
        re.IGNORECASE,
    ):
        context = text[max(0, match.start() - 25) : match.end() + 25].lower()
        if any(
            phrase in context
            for phrase in (
                "graduating",
                "graduation",
                "graduate between",
                "class of 2027",
                "degree in 2027",
            )
        ):
            continue
        return True
    return False


def target_term(title: str, description: str) -> tuple[bool, str]:
    text = f"{title} {description}"
    pairs = _season_pairs(text) | _title_season_pairs(title)
    if ("summer", "2027") in pairs or SHARED_YEAR_SUMMER_PATTERN.search(text):
        return True, "Summer 2027"
    if any(year == "2027" for _, year in pairs):
        return False, "other 2027 term only"
    if _generic_2027_internship(title) or _generic_2027_internship(description):
        return True, "2027 internship"
    return False, "no Summer 2027 term"


def is_us(job: dict[str, Any]) -> bool:
    country_code = str(job.get("country_code") or "").upper()
    if country_code:
        return country_code in {"US", "USA"}
    location = str(job.get("location") or "")
    lower = location.lower()
    if any(
        marker in lower
        for marker in (
            "united states",
            "u.s.",
            "usa",
            "us remote",
            "remote - us",
            "remote, us",
        )
    ):
        return True
    if re.search(rf"(?:,\s*|\bUS[- /])(?:{STATE_CODES})\b", location, re.IGNORECASE):
        return True
    return any(re.search(rf"\b{re.escape(state)}\b", lower) for state in STATE_NAMES)


def _contains(text: str, term: str) -> bool:
    padded = f" {text.lower()} "
    if term.startswith(" ") or term.endswith(" "):
        return term.lower() in padded
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])",
            padded,
        )
    )


def _hits(text: str, signals: dict[str, int]) -> list[tuple[str, int]]:
    return [
        (term.strip(), value)
        for term, value in signals.items()
        if _contains(text, term)
    ]


def _hardware_relevance(title: str, description: str) -> tuple[bool, int, list[str]]:
    title_hits = _hits(title, TITLE_SIGNALS)
    body_hits = _hits(description, BODY_SIGNALS)
    title_lower = title.lower()
    body_lower = description.lower()
    software_title = bool(SOFTWARE_TITLE_PATTERN.search(title))

    low_level = {
        signal
        for signal in LOW_LEVEL_SIGNALS
        if _contains(title_lower, signal) or _contains(body_lower, signal)
    }
    if software_title:
        relevant = any(_contains(title_lower, signal) for signal in LOW_LEVEL_SIGNALS)
        relevant = relevant or any(
            _contains(body_lower, signal) for signal in SOFTWARE_BODY_SIGNALS
        )
    elif title_hits:
        relevant = True
    elif GENERIC_ENGINEERING_TITLE.search(title):
        relevant = len(body_hits) >= 2
    else:
        relevant = len(body_hits) >= 3

    score = sum(value for _, value in title_hits)
    score += min(24, sum(value for _, value in body_hits))
    reasons = [term for term, _ in title_hits]
    reasons.extend(term for term, _ in body_hits)
    return relevant, score, list(dict.fromkeys(reasons))


def evaluate(job: dict[str, Any]) -> MatchResult:
    title = str(job.get("title") or "")
    description = str(job.get("description") or "")

    if SENIOR_TITLE_PATTERN.search(title):
        return MatchResult(False, 0, (), "senior/full-time title")
    if GRADUATE_ONLY_TITLE.search(title):
        return MatchResult(False, 0, (), "graduate-only title")

    internship_title = bool(INTERNSHIP_PATTERN.search(title))
    student_role = bool(TITLE_STUDENT_PATTERN.search(title)) and bool(
        INTERNSHIP_PATTERN.search(description)
    )
    if not internship_title and not student_role:
        return MatchResult(False, 0, (), "not an internship title")

    term_ok, term_reason = target_term(title, description)
    if not term_ok:
        return MatchResult(False, 0, (), term_reason)
    if not is_us(job):
        return MatchResult(False, 0, (), "not a US location")

    hardware_ok, hardware_score, hardware_reasons = _hardware_relevance(
        title, description
    )
    if not hardware_ok:
        return MatchResult(False, 0, (), "not hardware-related")

    reasons = [term_reason]
    reasons.extend(hardware_reasons[:5])
    score = 55 + hardware_score
    location = str(job.get("location") or "").lower()
    if any(metro in location for metro in METROS):
        score += 6
        reasons.append("major metro")
    return MatchResult(True, score, tuple(list(dict.fromkeys(reasons))[:6]))
