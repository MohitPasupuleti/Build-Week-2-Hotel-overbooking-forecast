"""Load the saved policy and generate a table. Owner: Build Lead.

Inference uses the source notebook's feature formulas and frozen policy.
It does not require is_canceled or retrain a model.
"""
from pathlib import Path
import argparse
import joblib
import numpy as np
import pandas as pd
import features
import backtest

ROOT = Path(__file__).resolve().parents[1]


def recommendation_table(bookings, artifact, start, nights=14):
    bookings = features.prepare_bookings(bookings)
    dates = pd.date_range(start, periods=nights)
    bookings = bookings[bookings['arrival_date'].isin(dates)].copy()
    if bookings.empty:
        raise ValueError('No bookings found for the requested dates')
    if artifact['pipeline'] is not None:
        inputs = features.prediction_inputs(bookings, artifact['final_features'])
        probability = np.clip(artifact['pipeline'].predict_proba(inputs)[:, 1], 0, 1)
    else:
        # The lookup fallback uses exactly the stored training groups and hotel rates.
        groups = bookings[['hotel', 'market_segment']].assign(
            lt=pd.cut(bookings['lead_time'], artifact['bins'], labels=False))
        probability = pd.Series(artifact['lookup'].reindex(pd.MultiIndex.from_frame(groups)).to_numpy(), index=bookings.index)
        probability = probability.fillna(bookings['hotel'].map(artifact['train_rate'])).clip(0, 1).to_numpy()
    # Same expected count and independent-booking spread as contract.nightly_table.
    scored = bookings.assign(_p=probability, _var=probability * (1 - probability))
    n14 = scored.groupby(['hotel', 'arrival_date']).agg(
        book=('_p', 'size'), expected=('_p', 'sum'),
        spread=('_var', lambda values: float(np.sqrt(values.sum()))))
    backtest.train_rate = artifact['train_rate']
    n14['k'] = backtest.k_of(n14, artifact['rule'], artifact['value'])
    table = n14[['book', 'expected', 'spread', 'k']].round(1).reset_index()
    table.columns = ['hotel', 'night', 'bookings', 'expected_cancellations', 'spread', 'recommended_k']
    value = str(artifact['value'])
    table.insert(2, 'policy', f"{artifact['model_name']} / {artifact['rule']} = {value}")
    table = table.sort_values(['night', 'hotel']).reset_index(drop=True)
    expected_rows = len(bookings['hotel'].unique()) * nights
    if len(table) != expected_rows:
        raise ValueError(f'Expected {expected_rows} observed hotel-nights, got {len(table)}; missing nights need a documented rule')
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='start', required=True)
    parser.add_argument('--nights', type=int, default=14)
    parser.add_argument('--bookings', type=Path, default=ROOT / 'data' / 'hotels.csv')
    parser.add_argument('--model', type=Path, default=ROOT / 'models' / 'selected_policy.joblib')
    parser.add_argument('--output', type=Path, default=ROOT / 'evidence' / 'nightly_k.csv')
    args = parser.parse_args()
    if args.nights < 1:
        parser.error('--nights must be positive')
    artifact = joblib.load(args.model)
    table = recommendation_table(pd.read_csv(args.bookings), artifact, args.start, args.nights)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)
    print(table.to_string(index=False))
    print(f'Saved {len(table)} rows to {args.output}')


if __name__ == '__main__':
    main()
