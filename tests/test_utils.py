from scrapers.utils import normalize_status


def test_normalize_status_known():
    assert normalize_status('missing') == 'missing'
    assert normalize_status('MiSsInG') == 'missing'


def test_normalize_status_died_synonyms():
    for s in ['died', 'deceased', 'dead', 'passed', 'passed away']:
        assert normalize_status(s) == 'died'


def test_normalize_status_unknown_map_to_other():
    assert normalize_status('something-unknown') == 'other'
    assert normalize_status('') == '' or normalize_status(None) == None  # defensive (function allows falsy)
