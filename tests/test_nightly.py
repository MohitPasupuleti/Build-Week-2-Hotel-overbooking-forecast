"""Check saved-policy inference on validation dates without retraining."""
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import nightly


@pytest.fixture(scope='module')
def inputs():
    artifact_path = ROOT / 'models' / 'selected_policy.joblib'
    if not artifact_path.exists():
        pytest.skip('Run python src/backtest.py to create the validation-selected artifact')
    bookings = pd.read_csv(ROOT / 'data' / 'hotels.csv')
    dates = pd.to_datetime(
        bookings['arrival_date_year'].astype(str) + '-'
        + bookings['arrival_date_month'] + '-'
        + bookings['arrival_date_day_of_month'].astype(str),
        format='%Y-%B-%d',
    )
    bookings = bookings[(dates >= '2016-12-18') & (dates < '2017-01-01')].copy()
    return bookings, joblib.load(artifact_path)


def test_inference_does_not_need_or_use_outcome_labels(inputs):
    bookings, artifact = inputs
    expected = nightly.recommendation_table(bookings, artifact, '2016-12-18')
    without_labels = bookings.drop(columns=['is_canceled', 'reservation_status', 'reservation_status_date'])
    actual = nightly.recommendation_table(without_labels, artifact, '2016-12-18')
    pd.testing.assert_frame_equal(actual, expected)


def test_fourteen_nights_have_complete_valid_recommendations(inputs):
    bookings, artifact = inputs
    table = nightly.recommendation_table(bookings, artifact, '2016-12-18')
    assert len(table) == 28
    assert not table.duplicated(['hotel', 'night']).any()
    assert table['night'].nunique() == 14
    assert table['hotel'].nunique() == 2
    assert np.isfinite(table['recommended_k']).all()
    assert (table['recommended_k'] >= 0).all()
    assert (table['recommended_k'] <= table['bookings']).all()
    assert (table['recommended_k'] == np.floor(table['recommended_k'])).all()
