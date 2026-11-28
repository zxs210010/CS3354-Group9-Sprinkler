"""
location.py: validate a user's location, confirm it exists, and store it in D1.

Finds the existing location table itself (it needs user_id, city, country columns)
and only writes columns that table has
Works with the location.html form (fields: country, state, city).
Other modules read the saved location with get_location(user_id).
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from backend.create_account import AccountError, TOKEN, URL
from backend.sprinkler.sprinkler_service import add_sprinkler, remove_sprinkler   # adjust the path if yours differs

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
# Placeholder sprinklers (serial number / sprinkler_id -> display name) until real ones exist
PLACEHOLDER_SPRINKLERS = {
    "SprinklerA": "Sprinkler A",
    "SprinklerB": "Sprinkler B",
    "SprinklerC": "Sprinkler C",
}
SPRINKLER_TABLE = "sprinkler_settings"
NAME_RE = re.compile(r"^[A-Za-z\u00C0-\u024F .'\-]{1,80}$")   # letters, spaces, . ' -


class LocationError(AccountError):
    """User-facing location problem. Subclasses AccountError so existing handlers catch it."""


# --------------------------------------------------------------------------
# Lookup tables
# --------------------------------------------------------------------------

# Names the form's datalist offers, plus common aliases -> ISO code.
# Any other country name is still accepted: it is matched by name at lookup time.
COUNTRY_CODES = {
    "united states": "US", "usa": "US", "us": "US", "america": "US",
    "canada": "CA", "mexico": "MX",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "ireland": "IE",
    "australia": "AU", "new zealand": "NZ",
    "germany": "DE", "france": "FR", "spain": "ES", "italy": "IT",
    "japan": "JP", "india": "IN", "brazil": "BR", "south africa": "ZA",
    "china": "CN",
}

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate_location(city, state, country):
    """Check the raw form input. Returns (city, state, country_name, country_code_or_None)."""
    city = (city or "").strip()
    state = (state or "").strip()
    country = (country or "").strip()

    if not NAME_RE.match(city):
        raise LocationError("Enter a valid city name.")
    if state and not NAME_RE.match(state):
        raise LocationError("Enter a valid state or region.")
    if not NAME_RE.match(country):
        raise LocationError("Enter a valid country.")

    key = country.lower()
    if key in COUNTRY_CODES:
        code = COUNTRY_CODES[key]
    elif len(key) == 2:
        code = country.upper()
    else:
        code = None                       # unknown name: matched by name during lookup

    if code == "US" and state.upper() in US_STATES:      # "TX" -> "Texas"
        state = US_STATES[state.upper()]
    return city, state, country, code


# --------------------------------------------------------------------------
# Verification (does this place exist?)
# --------------------------------------------------------------------------

def geocode(city, state, country, code):
    """Confirm the place exists and return its details and coordinates."""
    params = {"name": city, "count": 20, "language": "en", "format": "json"}
    if code:
        params["countryCode"] = code
    url = GEOCODE_URL + "?" + urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            results = json.loads(resp.read()).get("results") or []
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise LocationError("Location lookup is unavailable. Try again in a moment.")

    for place in results:
        if code and (place.get("country_code") or "").upper() != code:
            continue
        if not code and (place.get("country") or "").lower() != country.lower():
            continue
        admin1 = place.get("admin1") or ""
        if state and not admin1.lower().startswith(state.lower()):
            continue
        return {
            "city": place["name"],
            "state": admin1 or state,
            "country": place.get("country") or country,
            "country_code": (place.get("country_code") or code or "").upper(),
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "timezone": place.get("timezone") or "",
        }
    raise LocationError("We couldn't find that place. Check the spelling and country.")


# --------------------------------------------------------------------------
# Database (same endpoint, token and request format as create_account.py)
# --------------------------------------------------------------------------

def _post(sql, params=None):
    """POST SQL to Cloudflare D1. Unlike urlopen's default, failures say why."""
    payload = json.dumps({"sql": sql, "params": params or []}).encode()
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print("D1 error", exc.code, "|", " ".join(sql.split())[:140], "|",
              exc.read().decode(errors="replace"))
        raise LocationError("Location database error. See the terminal for details.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LocationError("Couldn't reach the database. Try again in a moment.") from exc

    if not body.get("success"):
        print("D1 error", body.get("errors"))
        raise LocationError("Location database error. See the terminal for details.")
    return body["result"][0]


def _query(sql, params=None):
    return _post(sql, params).get("results", [])


def _execute(sql, params=None):
    return _post(sql, params).get("meta", {})


_schema_cache = None


def _schema():
    """Find the location table and its columns, so no names are guessed."""
    global _schema_cache
    if _schema_cache:
        return _schema_cache

    tables = [r["name"] for r in _query("SELECT name FROM sqlite_master WHERE type = 'table'")]
    for name in tables:
        if name.startswith(("sqlite_", "_cf_")):
            continue
        cols = {c["name"] for c in _query(f'PRAGMA table_info("{name}")')}
        if {"user_id", "city", "country"} <= cols:
            _schema_cache = (name, cols)
            return _schema_cache

    print("No location table found. Tables in this database:", tables)
    raise LocationError("Location table not found in the database.")


# --------------------------------------------------------------------------
# Sprinklers (one row per user in sprinkler_settings, managed with sprinkler_service)
# --------------------------------------------------------------------------

_sprinkler_cols_cache = None


def _sprinkler_cols():
    """Columns of sprinkler_settings. It must link a sprinkler to a user."""
    global _sprinkler_cols_cache
    if _sprinkler_cols_cache:
        return _sprinkler_cols_cache

    cols = {c["name"] for c in _query(f'PRAGMA table_info("{SPRINKLER_TABLE}")')}
    if not cols:
        raise LocationError(f"The {SPRINKLER_TABLE} table was not found in the database.")
    missing = {"user_id", "sprinkler_id"} - cols
    if missing:
        raise LocationError(f"{SPRINKLER_TABLE} needs these columns: {', '.join(sorted(missing))}.")
    _sprinkler_cols_cache = cols
    return cols


def load_sprinklers(user_id):
    """The user's sprinklers in the shape sprinkler_service expects: {serial: {"name": ...}}.
    sprinkler_settings has one row per user, so this holds at most one sprinkler."""
    _sprinkler_cols()
    rows = _query(f'SELECT sprinkler_id FROM "{SPRINKLER_TABLE}" WHERE user_id = ?', [user_id])
    return {
        r["sprinkler_id"]: {"name": PLACEHOLDER_SPRINKLERS.get(r["sprinkler_id"], r["sprinkler_id"])}
        for r in rows if r.get("sprinkler_id")
    }


def connect_sprinkler(user_id, sprinkler_id):
    """Point the user's sprinkler_settings row at this sprinkler (replacing any previous one)."""
    cols = _sprinkler_cols()
    sprinklers = load_sprinklers(user_id)

    if sprinkler_id in sprinklers:
        return "Sprinkler already connected"      # nothing to change

    for old in list(sprinklers):                  # one sprinkler per user: drop the old one
        remove_sprinkler(sprinklers, old)
    result = add_sprinkler(sprinklers, PLACEHOLDER_SPRINKLERS[sprinkler_id], sprinkler_id)

    # Keep the row's other settings (auto_mode, is_on, run_minutes); only the id changes
    if _query(f'SELECT user_id FROM "{SPRINKLER_TABLE}" WHERE user_id = ?', [user_id]):
        stamp = ", updated_at = datetime('now')" if "updated_at" in cols else ""
        _execute(f'UPDATE "{SPRINKLER_TABLE}" SET sprinkler_id = ?{stamp} WHERE user_id = ?',
                 [sprinkler_id, user_id])
    else:
        _execute(f'INSERT INTO "{SPRINKLER_TABLE}" (user_id, sprinkler_id) VALUES (?, ?)',
                 [user_id, sprinkler_id])
    return result


def get_sprinkler_id(user_id):
    """The sprinkler_id on the user's sprinkler_settings row, or None."""
    try:
        _sprinkler_cols()
        rows = _query(f'SELECT sprinkler_id FROM "{SPRINKLER_TABLE}" WHERE user_id = ?', [user_id])
    except LocationError:
        return None                               # the reason was already printed to the terminal
    return (rows[0]["sprinkler_id"] if rows else None) or None


# --------------------------------------------------------------------------
# Location
# --------------------------------------------------------------------------

def save_location(user_id, city, state, country, sprinkler_id=None):
    """Validate, verify and save the user's location (one row per user).
    If a sprinkler is chosen, it is connected to the user as well."""
    city, state, country, code = validate_location(city, state, country)
    if sprinkler_id is not None and sprinkler_id not in PLACEHOLDER_SPRINKLERS:
        raise LocationError("Choose a sprinkler from the list.")

    p = geocode(city, state, country, code)       # fails first on a bad place: nothing is written
    table, cols = _schema()

    if sprinkler_id is not None:
        connect_sprinkler(user_id, sprinkler_id)

    # Only write columns the table really has
    data = {
        "city": p["city"], "state": p["state"], "country": p["country"],
        "country_code": p["country_code"], "latitude": p["latitude"],
        "longitude": p["longitude"], "timezone": p["timezone"],
    }
    data = {k: v for k, v in data.items() if k in cols}

    if _query(f'SELECT user_id FROM "{table}" WHERE user_id = ?', [user_id]):
        sets = ", ".join(f"{k} = ?" for k in data)
        _execute(f'UPDATE "{table}" SET {sets} WHERE user_id = ?', [*data.values(), user_id])
    else:
        names = ", ".join(["user_id", *data])
        marks = ", ".join("?" * (len(data) + 1))
        _execute(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', [user_id, *data.values()])
    return p


def get_location(user_id):
    """What other modules call: the user's saved location (with sprinkler_id), or None."""
    try:
        table, _ = _schema()
        rows = _query(f'SELECT * FROM "{table}" WHERE user_id = ?', [user_id])
    except LocationError:
        return None          # the reason was already printed to the terminal
    if not rows:
        return None
    loc = dict(rows[0])
    loc["sprinkler_id"] = get_sprinkler_id(user_id) or ""
    return loc


def get_coordinates(user_id):
    """(latitude, longitude) for weather lookups, or None if missing or unverified (0, 0)."""
    loc = get_location(user_id)
    if not loc or (not loc.get("latitude") and not loc.get("longitude")):
        return None
    return loc["latitude"], loc["longitude"]
