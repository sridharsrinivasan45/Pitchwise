"""
Team display aliasing — DOES NOT TOUCH ENGINE DATA.

Cricsheet stores authentic franchise names per era (e.g. "Royal Challengers
Bangalore" pre-2024, then "Royal Challengers Bengaluru"). The WPA engine
groups by these raw team names for opposition adjustment, and that must be
preserved. This module provides a display-only layer used by the adapter
when rendering matches/players to the UI.
"""

# Canonical modern name + 3-letter short code, keyed by Cricsheet raw name
TEAM_DISPLAY: dict[str, dict[str, str]] = {
    "Chennai Super Kings":              {"name": "Chennai Super Kings",         "short": "CSK"},
    "Mumbai Indians":                   {"name": "Mumbai Indians",              "short": "MI"},
    "Kolkata Knight Riders":            {"name": "Kolkata Knight Riders",       "short": "KKR"},
    "Royal Challengers Bangalore":      {"name": "Royal Challengers Bengaluru", "short": "RCB"},
    "Royal Challengers Bengaluru":      {"name": "Royal Challengers Bengaluru", "short": "RCB"},
    "Sunrisers Hyderabad":              {"name": "Sunrisers Hyderabad",         "short": "SRH"},
    "Delhi Daredevils":                 {"name": "Delhi Capitals",              "short": "DC"},
    "Delhi Capitals":                   {"name": "Delhi Capitals",              "short": "DC"},
    "Kings XI Punjab":                  {"name": "Punjab Kings",                "short": "PBKS"},
    "Punjab Kings":                     {"name": "Punjab Kings",                "short": "PBKS"},
    "Rajasthan Royals":                 {"name": "Rajasthan Royals",            "short": "RR"},
    "Gujarat Titans":                   {"name": "Gujarat Titans",              "short": "GT"},
    "Lucknow Super Giants":             {"name": "Lucknow Super Giants",        "short": "LSG"},
    # Defunct / historical
    "Deccan Chargers":                  {"name": "Deccan Chargers",             "short": "DCG"},
    "Pune Warriors India":              {"name": "Pune Warriors India",         "short": "PWI"},
    "Kochi Tuskers Kerala":             {"name": "Kochi Tuskers Kerala",        "short": "KTK"},
    "Rising Pune Supergiants":          {"name": "Rising Pune Supergiants",     "short": "RPS"},
    "Rising Pune Supergiant":           {"name": "Rising Pune Supergiants",     "short": "RPS"},
    "Gujarat Lions":                    {"name": "Gujarat Lions",               "short": "GL"},
}


def resolve_team(raw_name: str) -> dict:
    """Return {'name','short'} for a Cricsheet raw team name."""
    if not raw_name:
        return {"name": raw_name or "", "short": ""}
    return TEAM_DISPLAY.get(raw_name, {"name": raw_name, "short": raw_name[:3].upper()})


def short(raw_name: str) -> str:
    return resolve_team(raw_name)["short"]


def display_name(raw_name: str) -> str:
    return resolve_team(raw_name)["name"]
