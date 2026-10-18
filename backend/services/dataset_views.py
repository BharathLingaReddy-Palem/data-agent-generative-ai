"""One active analytical view, with a leakage-safe source for model fitting."""
from backend.services.cleaner import clean_dataset, clean_column_names


def active_dataframe(session):
    if session.get("explicit_cleaning"):
        return session["df_cleaned"]
    converted = session.get("analysis", {}).get("df_clean")
    if converted is not None:
        return converted
    return session["df_cleaned"] if session.get("df_cleaned") is not None else session["df"]


def model_dataframe(session, requested_target=None):
    """Replay structural cleanup; learned transformations belong inside CV."""
    if session.get("explicit_cleaning"):
        return session["df_cleaned"].copy(), requested_target, False
    raw = session["df"]
    options = session.get("cleaning_options")
    if not options:
        return raw.copy(), requested_target, False
    target = requested_target
    if options["standardize_names"]:
        _, mapping = clean_column_names(raw)
        inverse = {new: old for old, new in mapping.items()}
        target = inverse.get(target, target)
    structural, audit = clean_dataset(raw, handle_missing=False, handle_outliers=False,
        remove_duplicates=options["remove_duplicates"], standardize_names=options["standardize_names"],
        target_column=target)
    mapped = audit["renamed_columns"].get(target, target)
    return structural, mapped, options["handle_outliers"]
