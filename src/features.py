"""Data preparation extracted from the supplied notebook. Owner: Data Lead.

This preserves the supplied feature choices, including deposit_type in modelling.
It does not certify their booking-time availability; see docs/COLUMNS.md.
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

# Source notebook cell 95
# Select the inputs for the model
selected_features = [
    'hotel',
    'lead_time',
    'arrival_month',
    'market_segment',
    'distribution_channel',
    'customer_type',
    'reserved_room_type',
    'is_repeated_guest',
    'previous_cancellations',
    'previous_bookings_not_canceled',
    'stays_in_week_nights',
    'stays_in_weekend_nights'
]

selected_features

# Source notebook cell 104
# Encode these inputs as separate categories
categorical_features = [
    'hotel',
    'arrival_month',
    'market_segment',
    'distribution_channel',
    'customer_type',
    'reserved_room_type'
]

# Source notebook cell 105
# Scale these numerical inputs using training values only
numerical_features = [
    'lead_time',
    'previous_cancellations',
    'previous_bookings_not_canceled',
    'stays_in_week_nights',
    'stays_in_weekend_nights'
]

# This is a zero or one indicator
binary_features = ['is_repeated_guest']

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

def add_features(X, frame):
    X = X.copy()
    X['arrival_dow'] = frame['arrival_date'].dt.dayofweek.astype(str)
    X['lead_time_log'] = np.log1p(frame['lead_time'])
    X['has_weekend_stay'] = (frame['stays_in_weekend_nights'] > 0).astype(int)
    return X


def prepare_bookings(bookings):
    """Create the same date and stay fields without changing source records."""
    df = bookings.copy()
    # Source notebook cell 8
    year = df["arrival_date_year"].astype(str)
    month = df["arrival_date_month"]
    day = df["arrival_date_day_of_month"].astype(str)

    arrival_date_text = year + "-" + month + "-" + day

    df["arrival_date"] = pd.to_datetime(
        arrival_date_text,
        format="%Y-%B-%d"
    )

    print(df["arrival_date"].min())
    print(df['arrival_date'].max())

    # Source notebook cell 17
    # Total number of nights booked
    df['nights'] = (
        df['stays_in_weekend_nights']
        + df['stays_in_week_nights']
    )

    # Source notebook cell 18
    # Month number for seasonal analysis
    df['arrival_month'] = df['arrival_date'].dt.month
    return df


def prepare_state(data_path=None):
    """Return the notebook's prepared tables; fit preprocessing on train only."""
    global selected_features, categorical_features, numerical_features, binary_features
    df = data.read_raw(data_path or ROOT / 'data' / 'hotels.csv')
    raw = df.copy()
    df = prepare_bookings(df)
    # Source notebook cell 23
    # Split by arrival date using the contract: train, validation (choose), test (proof)
    train_bookings, validation_bookings, test_bookings = (x.copy() for x in contract.split_periods(df))

    # Source notebook cell 63
    # Get the original records for the training period
    training_source = raw.loc[train_bookings.index].copy()
    training_source.shape

    # Source notebook cell 70
    # Filling the children column with the median value from the training period
    children_median = training_source['children'].median()
    print('Training median for children:', children_median)

    # Source notebook cell 82
    # Reusing the same missing value rules for all three splits
    for split in [train_bookings, validation_bookings, test_bookings]:
        split['children'] = split['children'].fillna(children_median)
        split['country'] = split['country'].fillna('Unknown')

    # Source notebook cell 83
    # Calculate total guests after handling missing children
    for split in [train_bookings, validation_bookings, test_bookings]:
        split['total_guests'] = split['adults'] + split['children'] + split['babies']

    split['total_guests'].sum()

    # Source notebook cell 95
    # Select the inputs for the model
    selected_features = [
        'hotel',
        'lead_time',
        'arrival_month',
        'market_segment',
        'distribution_channel',
        'customer_type',
        'reserved_room_type',
        'is_repeated_guest',
        'previous_cancellations',
        'previous_bookings_not_canceled',
        'stays_in_week_nights',
        'stays_in_weekend_nights'
    ]

    selected_features

    # Source notebook cell 104
    # Encode these inputs as separate categories
    categorical_features = [
        'hotel',
        'arrival_month',
        'market_segment',
        'distribution_channel',
        'customer_type',
        'reserved_room_type'
    ]

    # Source notebook cell 105
    # Scale these numerical inputs using training values only
    numerical_features = [
        'lead_time',
        'previous_cancellations',
        'previous_bookings_not_canceled',
        'stays_in_week_nights',
        'stays_in_weekend_nights'
    ]

    # This is a zero or one indicator
    binary_features = ['is_repeated_guest']

    # Source notebook cell 98
    # Select the inputs without changing the booking tables
    X_train = train_bookings[selected_features].copy()
    X_validation = validation_bookings[selected_features].copy()
    X_test = test_bookings[selected_features].copy()

    # Source notebook cell 99
    # Treat month as a category rather than a continuous number
    for inputs in [X_train, X_validation, X_test]:
        inputs['arrival_month'] = inputs['arrival_month'].astype(str)

    # Source notebook cell 100
    # Keep the labels separate from the model inputs
    y_train = train_bookings['is_canceled'].copy()
    y_validation = validation_bookings['is_canceled'].copy()
    y_test = test_bookings['is_canceled'].copy()

    # Source notebook cell 101
    # Keep the original booking values for hotel-night scoring
    scoring_columns = ['hotel', 'arrival_date', 'adr', 'nights', 'is_canceled']
    train_scoring = train_bookings[scoring_columns].copy()
    validation_scoring = validation_bookings[scoring_columns].copy()
    test_scoring = test_bookings[scoring_columns].copy()

    # Source notebook cell 109
    # Fill missing categories and create one column per category
    categorical_pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='constant', fill_value='Unknown')),
        ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
    ])

    # Source notebook cell 110
    # Learn numerical fill values and scaling from training only
    numerical_pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    # Source notebook cell 111
    # Apply the right preparation to each type of input
    preprocessor = ColumnTransformer([
        ('categorical', categorical_pipeline, categorical_features),
        ('numerical', numerical_pipeline, numerical_features),
        ('binary', 'passthrough', binary_features)
    ], remainder='drop')

    # Source notebook cell 112
    # Fit preprocessing on training, then reuse it for later periods
    X_train_prepared = preprocessor.fit_transform(X_train)
    X_validation_prepared = preprocessor.transform(X_validation)
    X_test_prepared = preprocessor.transform(X_test)
    state = locals().copy()
    state['ROOT'] = ROOT
    state.update(selected_features=selected_features, categorical_features=categorical_features,
                 numerical_features=numerical_features, binary_features=binary_features)
    return state


def prediction_inputs(bookings, final_features):
    """Build the original model inputs without needing outcome labels."""
    X = bookings[selected_features].copy()
    X['arrival_month'] = X['arrival_month'].astype(str)
    X = add_features(X, bookings)
    X['deposit_type'] = bookings['deposit_type']
    return X[final_features]
