import os
import pandas as pd
from rapidfuzz import process, fuzz

# Path to the H1B sponsor CSV — same directory as this file
_CSV_PATH = os.path.join(os.path.dirname(__file__), "h1bsponsor.csv")

# Load once at module import and cache as a module-level set
def _load_sponsors() -> list[str]:
    try:
        df = pd.read_csv(_CSV_PATH)
        return df["Employer (Petitioner) Name"].dropna().str.upper().str.strip().tolist()
    except Exception:
        return []

_SPONSORS: list[str] = _load_sponsors()


def is_h1b_sponsor(company: str, threshold: int = 75) -> bool:
    """Return True if company fuzzy-matches an H1B sponsor at >= threshold%."""
    if not company or not _SPONSORS:
        return False
    match = process.extractOne(
        company.upper().strip(),
        _SPONSORS,
        scorer=fuzz.token_set_ratio,
    )
    return match is not None and match[1] >= threshold


def flag_h1b(df: pd.DataFrame, company_col: str = "company", threshold: int = 75) -> pd.DataFrame:
    """
    Add an 'h1b_sponsor' boolean column to the DataFrame.
    Operates on a copy — does not mutate the input.
    """
    df = df.copy()
    df["h1b_sponsor"] = df[company_col].apply(lambda c: is_h1b_sponsor(c, threshold))
    return df
