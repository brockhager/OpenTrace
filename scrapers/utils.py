def normalize_status(status: str) -> str:
    """Normalize various status strings into canonical statuses used by the DB.

    Canonical set: 'missing', 'unidentified', 'found'
    Map common synonyms for deceased (died, passed, deceased) to 'found' to
    avoid DB check constraint failures and preserve meaning.
    """
    if not status:
        return status
    s = status.strip().lower()
    map_to_died = {'died', 'deceased', 'dead', 'passed', 'passed away'}
    if s in {'missing', 'unidentified', 'found', 'died', 'other'}:
        return s
    if s in map_to_died:
        return 'died'
    # Any unknown/ambiguous status => 'other' so the DB accepts it
    return 'other'
