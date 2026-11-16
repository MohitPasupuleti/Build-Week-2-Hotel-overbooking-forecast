"""Training, validation, frozen proof and artifact export. Owner: Model Lead.

Calculations and grids are preserved from the supplied notebook.
A repeated proof run is a reproducibility replay, not new held-out evidence.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))
import contract
import data


import argparse
import json
import joblib
import matplotlib.pyplot as plt
import features
# Imports for models and metrics
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score, RocCurveDisplay
from sklearn.calibration import calibration_curve

# Scores used everywhere: accuracy (threshold 0.5), Brier score, ROC-AUC
def score(y, p):
    return {'accuracy': ((p >= .5) == y).mean(), 'brier': brier_score_loss(y, p), 'roc_auc': roc_auc_score(y, p)}

# Lookup probability for any bookings table
def lookup_prob(f):
    p = pd.Series(lookup.reindex(pd.MultiIndex.from_frame(keys(f))).to_numpy(), index=f.index)
    return p.fillna(f['hotel'].map(train_rate)).clip(0, 1).to_numpy()

# One function for all three rules
def k_of(n, kind, v):
    if kind == 'flat':
        k = n['book'] * n.index.get_level_values('hotel').map(train_rate).to_numpy() - v
    elif kind == 'z':
        k = n['expected'] - v * n['spread']
    else:
        k = n['expected'] - v
    return pd.Series(np.floor(k), index=n.index).clip(lower=0).clip(upper=n['book']).astype(int)


def _show(value):
    if value is not None:
        print(value.to_string() if isinstance(value, (pd.DataFrame, pd.Series)) else value)


def run_validation(state=None):
    """Fit and select with the same training and validation calculations."""
    global categorical_features, numerical_features, binary_features
    global train_rate, bins, keys, lookup
    state = features.prepare_state() if state is None else state
    train_bookings = state['train_bookings']
    validation_bookings = state['validation_bookings']
    test_bookings = state['test_bookings']
    X_train = state['X_train']
    X_validation = state['X_validation']
    X_test = state['X_test']
    y_train = state['y_train']
    y_validation = state['y_validation']
    y_test = state['y_test']
    selected_features = state['selected_features']
    categorical_features = state['categorical_features']
    numerical_features = state['numerical_features']
    binary_features = state['binary_features']
    # Source notebook cell 131
    # Features still to be confirmed as booking-time fields (edit after the team decision)
    to_confirm = ['market_segment', 'distribution_channel', 'customer_type', 'reserved_room_type',
                  'stays_in_week_nights', 'stays_in_weekend_nights']
    confirmed = [f for f in selected_features if f not in to_confirm]
    USE_UNCONFIRMED = True    # False = use confirmed features only

    # Source notebook cell 132
    # Preprocessing for any feature list (fit on training only)
    def make_prep(cols):
        cat = [c for c in categorical_features if c in cols]
        num = [c for c in numerical_features if c in cols]
        bina = [c for c in binary_features if c in cols]
        return ColumnTransformer([
            ('cat', Pipeline([('imp', SimpleImputer(strategy='constant', fill_value='Unknown')),
                              ('enc', OneHotEncoder(handle_unknown='ignore', sparse_output=False))]), cat),
            ('num', Pipeline([('imp', SimpleImputer(strategy='median')), ('sc', StandardScaler())]), num),
            ('bin', 'passthrough', bina)])

    # Source notebook cell 134
    # Sensitivity check: all selected features vs confirmed features only
    for name, cols in {'All selected': selected_features, 'Confirmed only': confirmed}.items():
        m = Pipeline([('prep', make_prep(cols)), ('clf', LogisticRegression(max_iter=1000))]).fit(X_train[cols], y_train)
        p = m.predict_proba(X_validation[cols])[:, 1]
        print(name, '| Brier:', round(brier_score_loss(y_validation, p), 4), '| ROC-AUC:', round(roc_auc_score(y_validation, p), 4))

    # Source notebook cell 135
    # Final feature list used by all models
    final_features = selected_features if USE_UNCONFIRMED else confirmed
    print(len(final_features), 'features:', final_features)

    # Source notebook cell 136
    # New booking-time features built from existing columns
    def add_features(X, frame):
        X = X.copy()
        X['arrival_dow'] = frame['arrival_date'].dt.dayofweek.astype(str)
        X['lead_time_log'] = np.log1p(frame['lead_time'])
        X['has_weekend_stay'] = (frame['stays_in_weekend_nights'] > 0).astype(int)
        return X

    if 'arrival_dow' not in final_features:      # safe to re-run
        X_train = add_features(X_train, train_bookings)
        X_validation = add_features(X_validation, validation_bookings)
        X_test = add_features(X_test, test_bookings)
        categorical_features.append('arrival_dow')
        numerical_features.append('lead_time_log')
        binary_features.append('has_weekend_stay')
        final_features = final_features + ['arrival_dow', 'lead_time_log', 'has_weekend_stay']

    for X, frame in [(X_train, train_bookings), (X_validation, validation_bookings), (X_test, test_bookings)]:
        X['deposit_type'] = frame['deposit_type']
    categorical_features.append('deposit_type')
    final_features = final_features + ['deposit_type']

    print(final_features)

    # Source notebook cell 139
    # Lookup table: cancellation rate by hotel, market segment and lead-time group
    bins = [-1, 30, 90, 180, 10**6]
    keys = lambda f: f[['hotel', 'market_segment']].assign(lt=pd.cut(f['lead_time'], bins, labels=False))
    train_rate = train_bookings.groupby('hotel')['is_canceled'].mean()
    grp = train_bookings.groupby(pd.MultiIndex.from_frame(keys(train_bookings)))['is_canceled'].agg(['mean', 'count'])
    lookup = grp['mean'].where(grp['count'] >= 30)      # small groups fall back to the hotel rate

    # Source notebook cell 141
    # Tune Logistic Regression: try several regularisation strengths C
    lr_models, rows = {}, []
    for C_ in [0.003, 0.01, 0.03, 0.1, 1, 10]:
        lr_models[C_] = Pipeline([('prep', make_prep(final_features)), ('clf', LogisticRegression(C=C_, max_iter=1000))]).fit(X_train[final_features], y_train)
        rows.append({'C': C_, **score(y_validation, lr_models[C_].predict_proba(X_validation[final_features])[:, 1])})
    lr_tuning = pd.DataFrame(rows).set_index('C')
    _show(lr_tuning.round(4))

    # Source notebook cell 142
    # Tune Gradient Boosting: learning rate, tree depth and regularisation
    gb_models, rows = {}, []
    for lr_ in [0.03, 0.05, 0.1]:
        for depth in [3, 5, 7]:
            for l2 in [0, 1]:
                gb = HistGradientBoostingClassifier(learning_rate=lr_, max_depth=depth, l2_regularization=l2,
                                                    max_iter=200, early_stopping=False, random_state=42)
                gb_models[(lr_, depth, l2)] = Pipeline([('prep', make_prep(final_features)),
                                                        ('clf', gb)]).fit(X_train[final_features], y_train)
                rows.append({'learning_rate': lr_, 'max_depth': depth, 'l2': l2,
                             **score(y_validation, gb_models[(lr_, depth, l2)].predict_proba(X_validation[final_features])[:, 1])})
    gb_tuning = pd.DataFrame(rows).set_index(['learning_rate', 'max_depth', 'l2'])
    _show(gb_tuning.sort_values('brier').round(4))

    # Source notebook cell 143
    # Keep the best setting of each model (lowest validation Brier score)
    models = {'Logistic Regression': lr_models[lr_tuning['brier'].idxmin()],
              'Gradient Boosting': gb_models[gb_tuning['brier'].idxmin()]}
    print('Best C:', lr_tuning['brier'].idxmin(), '| Best GB setting:', gb_tuning['brier'].idxmin())

    # Source notebook cell 145
    # Probabilities for every model on train and validation
    P_train = {'Lookup table': lookup_prob(train_bookings)}
    P_val = {'Lookup table': lookup_prob(validation_bookings)}
    for name, m in models.items():
        P_train[name] = m.predict_proba(X_train[final_features])[:, 1]
        P_val[name] = m.predict_proba(X_validation[final_features])[:, 1]

    # Source notebook cell 146
    # Accuracy, Brier score and ROC-AUC: train vs validation
    _show(pd.DataFrame([{'model': n, 'set': s, **score(y, P[n])}
                  for n in P_val for s, P, y in (('train', P_train, y_train), ('validation', P_val, y_validation))]).round(4))

    # Source notebook cell 147
    # ROC curves (validation)
    ax = plt.subplots(figsize=(6, 5))[1]
    for name, p in P_val.items():
        RocCurveDisplay.from_predictions(y_validation, p, name=name, ax=ax)
    ax.plot([0, 1], [0, 1], '--', color='grey'); plt.title('ROC Curves (validation)'); plt.show()

    # Source notebook cell 148
    # Calibration curves (validation)
    for name, p in P_val.items():
        a, b = calibration_curve(y_validation, p, n_bins=10)
        plt.plot(b, a, marker='o', label=name)
    plt.plot([0, 1], [0, 1], '--', color='grey', label='Perfect')
    plt.xlabel('Predicted probability'); plt.ylabel('Actual rate'); plt.title('Calibration (validation)'); plt.legend(); plt.show()

    # Source notebook cell 150
    # One row per hotel-night for every model: book, expected (mu), spread (sigma), stay_value
    N_val = {name: contract.nightly_table(validation_bookings, p) for name, p in P_val.items()}
    _show(N_val['Logistic Regression'].head())

    # Source notebook cell 151
    # Check: total expected vs actual cancellations per model
    _show(pd.DataFrame({n: {'expected': t['expected'].sum(), 'actual': t['cancelled'].sum()} for n, t in N_val.items()}).T.round(0))

    # Source notebook cell 154
    # Settings to try
    grids = {'flat': range(0, 41), 'z': np.arange(0, 4.01, .25), 'b': range(0, 31)}
    FLAT = 'Client flat rule'

    # Source notebook cell 155
    # Score every model, rule and setting on the validation period with the contract
    rows = []
    for name, n in N_val.items():
        for kind in ('z', 'b'):
            rows += [{'model': name, 'rule': kind, 'value': v, **contract.night_cost(n, k_of(n, kind, v))} for v in grids[kind]]
    rows += [{'model': FLAT, 'rule': 'flat', 'value': v, **contract.night_cost(N_val['Lookup table'], k_of(N_val['Lookup table'], 'flat', v))} for v in grids['flat']]
    search = pd.DataFrame(rows)

    # Source notebook cell 156
    # Cheapest setting that meets the walk ceiling, for each model and rule
    safe = search[search['ceiling_met']]
    best = safe.sort_values('cost_eur').groupby(['model', 'rule']).head(1).reset_index(drop=True)
    _show(best[['model', 'rule', 'value', 'cost_eur', 'empty_rooms', 'walked_guests', 'walks_per_1000']])

    # Source notebook cell 157
    # Select ONE policy: the cheapest safe one on validation, then freeze it
    assert len(best) > 0, 'No safe setting found'
    selected = best.iloc[0]
    print('Selected policy:', selected['model'], '| rule:', selected['rule'], '| setting:', selected['value'])
    result = locals().copy()
    result.update(train_rate=train_rate, bins=bins, keys=keys, lookup=lookup)
    return result


def run_proof(state):
    """Replay the supplied frozen proof without changing validation choices."""
    test_bookings = state['test_bookings']
    X_test = state['X_test']
    y_test = state['y_test']
    models = state['models']
    final_features = state['final_features']
    best = state['best']
    selected = state['selected']
    P_val = state['P_val']
    # Source notebook cell 159
    # Test probabilities and nightly tables for every model
    P_test = {'Lookup table': lookup_prob(test_bookings)}
    P_test.update({n: np.clip(m.predict_proba(X_test[final_features])[:, 1], 0, 1) for n, m in models.items()})
    N_test = {n: contract.nightly_table(test_bookings, p) for n, p in P_test.items()}

    # Source notebook cell 160
    # Score every frozen policy on 2017 with the contract
    rows = []
    for r in best.itertuples():
        n = N_test.get(r.model, N_test['Lookup table'])
        rows.append({'model': r.model, 'rule': r.rule, 'value': r.value, **contract.night_cost(n, k_of(n, r.rule, r.value))})
    n0 = N_test['Lookup table']
    rows.append({'model': 'No oversell', 'rule': 'k=0', 'value': 0, **contract.night_cost(n0, pd.Series(0, index=n0.index))})
    proof = pd.DataFrame(rows)
    _show(proof[['model', 'rule', 'value', 'cost_eur', 'empty_rooms', 'walked_guests', 'walks_per_1000', 'ceiling_met']])

    # Source notebook cell 161
    # Result of the selected policy against the client flat rule
    sel = proof[(proof['model'] == selected['model']) & (proof['rule'] == selected['rule'])].iloc[0]
    flat = proof[proof['rule'] == 'flat'].iloc[0]
    saving = flat['cost_eur'] - sel['cost_eur']
    print('Selected:', sel['model'], sel['rule'], sel['value'], '| cost:', sel['cost_eur'], '| walks per 1,000:', sel['walks_per_1000'])
    print('Savings vs flat rule (EUR):', round(saving, 2), '|', round(100 * saving / flat['cost_eur'], 2), '% | per month:', round(saving / 8, 2))

    # Source notebook cell 162
    # Final decision wording follows the selected policy
    if sel['ceiling_met']:
        print('Recommendation: use', sel['model'], '/', sel['rule'], '(safe on 2017 data)')
    else:
        print('Warning: the selected policy breaks the walk ceiling on 2017 data. Do not call it safe.')
    result = state.copy()
    result.update(locals())
    return result


def save_results(state, proof_run):
    """Save tables and the selected method for the nightly command."""
    evidence = ROOT / 'evidence'
    models_dir = ROOT / 'models'
    evidence.mkdir(exist_ok=True)
    models_dir.mkdir(exist_ok=True)
    for key, filename in [('lr_tuning','lr_tuning.csv'), ('gb_tuning','gb_tuning.csv'),
                          ('search','validation_policy_grid.csv'), ('best','validation_policies.csv')]:
        state[key].to_csv(evidence / filename, index=True)
    metrics = pd.DataFrame([
        {'model': name, 'set': period, **score(y, probabilities[name])}
        for name in state['P_val']
        for period, probabilities, y in [('train', state['P_train'], state['y_train']),
                                          ('validation', state['P_val'], state['y_validation'])]
    ])
    metrics.to_csv(evidence / 'validation_metrics.csv', index=False)
    if proof_run:
        state['proof'].to_csv(evidence / 'proof_table.csv', index=False)
    chosen = state['selected']
    artifact = {
        'model_name': chosen['model'], 'rule': chosen['rule'], 'value': float(chosen['value']),
        'pipeline': state['models'].get(chosen['model']),
        'models': state['models'], 'best': state['best'], 'selected': chosen,
        'final_features': list(state['final_features']),
        'train_rate': state['train_rate'], 'lookup': state['lookup'], 'bins': list(state['bins']),
        'use_unconfirmed': bool(state['USE_UNCONFIRMED']),
        'source_notebook_sha256': SOURCE_NOTEBOOK_SHA256,
        'note': 'Preserves supplied notebook; includes deposit_type and other timing assumptions.'
    }
    joblib.dump(artifact, models_dir / 'selected_policy.joblib')
    summary = {k:artifact[k] for k in ['model_name','rule','value','final_features','use_unconfirmed','source_notebook_sha256','note']}
    summary['proof_replayed'] = proof_run
    (evidence / 'run_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return artifact


SOURCE_NOTEBOOK_SHA256 = '6aeb53cb8bd370be6910425c3b1a0ad7b36bc70118bdd458b43f1d96a17c07f9'


def load_frozen_state(model_path=None):
    """Load validation-frozen choices for the separate final-proof notebook."""
    global train_rate, bins, keys, lookup
    artifact = joblib.load(model_path or ROOT / 'models' / 'selected_policy.joblib')
    state = features.prepare_state()
    train_rate = artifact['train_rate']
    bins = artifact['bins']
    lookup = artifact['lookup']
    keys = lambda f: f[['hotel', 'market_segment']].assign(lt=pd.cut(f['lead_time'], bins, labels=False))
    state.update(models=artifact['models'], best=artifact['best'], selected=artifact['selected'],
                 final_features=artifact['final_features'], P_val={})
    state['X_test'] = features.prediction_inputs(state['test_bookings'], artifact['final_features'])
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proof', action='store_true', help='Explicitly run the final 2017 proof; otherwise validation only')
    args = parser.parse_args()
    # Save the existing notebook plots as evidence without changing their contents.
    plot_number = 0
    def save_plot(*unused_args, **unused_kwargs):
        nonlocal plot_number
        (ROOT / 'evidence').mkdir(exist_ok=True)
        for number in plt.get_fignums():
            plot_number += 1
            plt.figure(number).savefig(ROOT / 'evidence' / f'model_plot_{plot_number:02d}.png', bbox_inches='tight')
            plt.close(number)
    plt.show = save_plot
    state = run_validation()
    if args.proof:
        state = run_proof(state)
    save_results(state, args.proof)


if __name__ == '__main__':
    main()
