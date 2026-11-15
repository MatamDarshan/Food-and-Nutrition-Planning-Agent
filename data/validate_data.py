"""
data/validate_data.py
---------------------
Standalone validation script for food_data.csv.
Run once after editing the dataset:
    python data/validate_data.py

Exit codes:
    0 — dataset is clean
    1 — validation errors found (details printed to stdout)
"""

import sys
import pandas as pd
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent
CSV_PATH = DATA_DIR / "food_data.csv"

# ── constants ─────────────────────────────────────────────────────────────────
REQUIRED_COLUMNS = {
    "food_id", "food_name", "calories", "protein",
    "carbohydrates", "fats", "fiber", "diet_type",
    "meal_type", "food_category", "ingredients", "allergens",
}

NUMERIC_COLS = ["calories", "protein", "carbohydrates", "fats", "fiber"]
POSITIVE_COLS = ["calories"]                # must be strictly > 0
NON_NEGATIVE_COLS = ["protein", "carbohydrates", "fats", "fiber"]  # >= 0
VALID_DIET_TYPES = {"veg", "non-veg"}
VALID_MEAL_TYPES = {"breakfast", "lunch", "snack", "dinner"}
VALID_CATEGORIES = {
    "Grain", "Dairy", "Legume", "Meat",
    "Vegetable", "Fruit", "Snack", "Beverage",
}


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[ERROR] CSV not found: {path}")
        sys.exit(1)
    return pd.read_csv(path)


def check_required_columns(df: pd.DataFrame) -> list[str]:
    errors = []
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {missing}")
    return errors


def check_missing_values(df: pd.DataFrame) -> list[str]:
    errors = []
    # glycemic_index is nullable — exclude from mandatory check
    mandatory = [c for c in REQUIRED_COLUMNS if c in df.columns]
    for col in mandatory:
        n_missing = df[col].isna().sum()
        if n_missing:
            errors.append(f"Column '{col}' has {n_missing} missing value(s).")
    return errors


def check_duplicates(df: pd.DataFrame) -> list[str]:
    errors = []
    dup_ids = df[df.duplicated("food_id", keep=False)]["food_id"].unique()
    if len(dup_ids):
        errors.append(f"Duplicate food_id values: {list(dup_ids)}")
    dup_names = df[df.duplicated("food_name", keep=False)]["food_name"].unique()
    if len(dup_names):
        errors.append(f"Duplicate food_name values: {list(dup_names)}")
    return errors


def check_numeric_values(df: pd.DataFrame) -> list[str]:
    errors = []
    for col in NUMERIC_COLS:
        if col not in df.columns:
            continue
        non_numeric = pd.to_numeric(df[col], errors="coerce").isna()
        if non_numeric.any():
            bad = df.loc[non_numeric, "food_name"].tolist()
            errors.append(f"Non-numeric values in '{col}': {bad}")
            continue
        df[col] = pd.to_numeric(df[col])
        if col in POSITIVE_COLS:
            bad = df.loc[df[col] <= 0, "food_name"].tolist()
            if bad:
                errors.append(f"'{col}' must be > 0 for: {bad}")
        if col in NON_NEGATIVE_COLS:
            bad = df.loc[df[col] < 0, "food_name"].tolist()
            if bad:
                errors.append(f"'{col}' must be >= 0 for: {bad}")
    return errors


def check_categorical_values(df: pd.DataFrame) -> list[str]:
    errors = []

    # diet_type
    if "diet_type" in df.columns:
        invalid = df[~df["diet_type"].isin(VALID_DIET_TYPES)]
        if not invalid.empty:
            errors.append(
                f"Invalid diet_type in rows: "
                f"{invalid[['food_name','diet_type']].to_dict('records')}"
            )

    # meal_type (pipe-separated, each token must be valid)
    if "meal_type" in df.columns:
        for _, row in df.iterrows():
            tokens = {t.strip() for t in str(row["meal_type"]).split("|")}
            invalid_tokens = tokens - VALID_MEAL_TYPES
            if invalid_tokens:
                errors.append(
                    f"'{row['food_name']}' has invalid meal_type tokens: {invalid_tokens}"
                )

    # food_category
    if "food_category" in df.columns:
        invalid = df[~df["food_category"].isin(VALID_CATEGORIES)]
        if not invalid.empty:
            errors.append(
                f"Invalid food_category in rows: "
                f"{invalid[['food_name','food_category']].to_dict('records')}"
            )

    return errors


def check_glycemic_index(df: pd.DataFrame) -> list[str]:
    """glycemic_index is nullable but must be numeric when present."""
    errors = []
    if "glycemic_index" not in df.columns:
        return errors
    non_null = df["glycemic_index"].dropna()
    coerced = pd.to_numeric(non_null, errors="coerce")
    bad_idx = coerced[coerced.isna()].index
    if not bad_idx.empty:
        bad = df.loc[bad_idx, "food_name"].tolist()
        errors.append(f"Non-numeric glycemic_index values for: {bad}")
    invalid_range = df.loc[
        pd.to_numeric(df["glycemic_index"], errors="coerce").notna()
        & (pd.to_numeric(df["glycemic_index"], errors="coerce") <= 0),
        "food_name",
    ].tolist()
    if invalid_range:
        errors.append(f"glycemic_index must be > 0 for: {invalid_range}")
    return errors


def print_summary(df: pd.DataFrame) -> None:
    print(f"\n{'='*55}")
    print(f"  Dataset Summary")
    print(f"{'='*55}")
    print(f"  Total food items    : {len(df)}")
    print(f"  Vegetarian          : {(df['diet_type']=='veg').sum()}")
    print(f"  Non-vegetarian      : {(df['diet_type']=='non-veg').sum()}")
    print(f"  Categories          : {df['food_category'].nunique()}")
    print(f"  Avg calories/100g   : {df['calories'].mean():.1f} kcal")
    print(f"  Calorie range       : {df['calories'].min():.0f}–{df['calories'].max():.0f} kcal")
    print(f"  Items with GI       : {df['glycemic_index'].notna().sum()}")
    print(f"{'='*55}\n")


def main() -> None:
    print(f"Validating: {CSV_PATH}\n")
    df = load_csv(CSV_PATH)

    all_errors: list[str] = []
    all_errors += check_required_columns(df)
    if all_errors:
        # Can't proceed without all columns
        for e in all_errors:
            print(f"[ERROR] {e}")
        sys.exit(1)

    all_errors += check_missing_values(df)
    all_errors += check_duplicates(df)
    all_errors += check_numeric_values(df)
    all_errors += check_categorical_values(df)
    all_errors += check_glycemic_index(df)

    if all_errors:
        print(f"[FAILED] {len(all_errors)} error(s) found:\n")
        for i, e in enumerate(all_errors, 1):
            print(f"  {i}. {e}")
        print()
        sys.exit(1)
    else:
        print("[PASSED] All validation checks passed.")
        print_summary(df)
        sys.exit(0)


if __name__ == "__main__":
    main()
