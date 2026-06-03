import pandas as pd

from core.time_filter import (
    FIRST_RECORD_OF_DAY,
    LAST_RECORD_OF_DAY,
    apply_time_filter,
    custom_time_filter,
    day_filter,
    detect_measurement_days,
    filter_matches_measurement_bounds,
    full_measurement_filter,
    measurement_date_options,
    resolve_time_option,
    same_time_filter,
    selected_day_indexes_for_range,
    time_options_for_integration,
)


def _dataframe(datetimes: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Datetime": pd.to_datetime(datetimes),
            "value": list(range(len(datetimes))),
        }
    )


def test_detect_measurement_days_classifies_complete_and_incomplete_days():
    dataframe = _dataframe(
        [
            "2026-06-01 00:00:00",
            "2026-06-01 12:00:00",
            "2026-06-01 23:59:50",
            "2026-06-02 08:15:00",
            "2026-06-02 23:59:50",
        ]
    )

    days = detect_measurement_days(dataframe, integration_time=10)

    assert len(days) == 2
    assert days[0].label == "01/06/2026"
    assert days[0].status == "Complete"
    assert days[1].label == "02/06/2026"
    assert days[1].status == "Incomplete"


def test_day_filter_selects_only_the_requested_day():
    dataframe = _dataframe(
        [
            "2026-06-01 23:59:50",
            "2026-06-02 00:00:00",
            "2026-06-02 12:00:00",
            "2026-06-02 23:59:50",
            "2026-06-03 00:00:00",
        ]
    )
    days = detect_measurement_days(dataframe, integration_time=10)

    filtered = apply_time_filter(dataframe, day_filter(days[1]))

    assert filtered["Datetime"].min() == pd.Timestamp("2026-06-02 00:00:00")
    assert filtered["Datetime"].max() == pd.Timestamp("2026-06-02 23:59:50")
    assert len(filtered) == 3


def test_custom_time_filter_filters_dataframe_without_mutating_source():
    dataframe = _dataframe(
        [
            "2026-06-02 07:59:50",
            "2026-06-02 08:00:00",
            "2026-06-02 12:00:00",
            "2026-06-02 18:00:00",
            "2026-06-02 18:00:10",
        ]
    )
    original = dataframe.copy(deep=True)

    time_filter = custom_time_filter(
        "2026-06-02 08:00:00",
        "2026-06-02 18:00:00",
    )
    filtered = apply_time_filter(dataframe, time_filter)

    assert len(filtered) == 3
    pd.testing.assert_frame_equal(dataframe, original)


def test_full_measurement_filter_restores_all_rows():
    dataframe = _dataframe(
        [
            "2026-06-01 00:00:00",
            "2026-06-02 12:00:00",
            "2026-06-03 23:59:50",
        ]
    )

    time_filter = full_measurement_filter(dataframe)
    restored = apply_time_filter(dataframe, time_filter)

    assert time_filter.is_full_measurement
    assert len(restored) == len(dataframe)
    pd.testing.assert_frame_equal(restored, dataframe)


def test_measurement_date_options_uses_only_dates_present_in_measurement():
    dataframe = _dataframe(
        [
            "2026-04-27 16:30:07",
            "2026-04-29 09:00:00",
            "2026-05-01 23:59:59",
        ]
    )

    dates = measurement_date_options(dataframe)

    assert [date.strftime("%d/%m/%Y") for date in dates] == [
        "27/04/2026",
        "29/04/2026",
        "01/05/2026",
    ]


def test_time_options_follow_integration_interval_and_include_end_of_day():
    options = time_options_for_integration(15)

    assert options[:5] == (
        "00:00:00",
        "00:00:15",
        "00:00:30",
        "00:00:45",
        "00:01:00",
    )
    assert options[-1] == "23:59:59"


def test_quick_time_options_resolve_to_exact_detected_day_bounds():
    dataframe = _dataframe(
        [
            "2026-05-01 08:15:07",
            "2026-05-01 12:00:00",
            "2026-05-01 18:45:13",
            "2026-05-02 00:00:00",
            "2026-05-02 23:59:59",
        ]
    )
    days = detect_measurement_days(dataframe, integration_time=10)

    assert resolve_time_option(days, "2026-05-01", FIRST_RECORD_OF_DAY) == pd.Timestamp(
        "2026-05-01 08:15:07"
    )
    assert resolve_time_option(days, "2026-05-01", LAST_RECORD_OF_DAY) == pd.Timestamp(
        "2026-05-01 18:45:13"
    )
    assert resolve_time_option(days, "2026-05-02", FIRST_RECORD_OF_DAY) == pd.Timestamp(
        "2026-05-02 00:00:00"
    )
    assert resolve_time_option(days, "2026-05-02", LAST_RECORD_OF_DAY) == pd.Timestamp(
        "2026-05-02 23:59:59"
    )


def test_filter_matches_measurement_bounds_detects_prepared_full_interval():
    dataframe = _dataframe(
        [
            "2026-04-27 16:30:07",
            "2026-05-01 12:00:00",
            "2026-06-01 09:13:13",
        ]
    )
    full_bounds_filter = custom_time_filter(
        "2026-04-27 16:30:07",
        "2026-06-01 09:13:13",
    )
    partial_filter = custom_time_filter(
        "2026-04-27 16:30:07",
        "2026-05-01 12:00:00",
    )

    assert filter_matches_measurement_bounds(dataframe, full_bounds_filter)
    assert not filter_matches_measurement_bounds(dataframe, partial_filter)


def test_selected_day_indexes_for_range_includes_start_and_end_dates():
    dataframe = _dataframe(
        [
            "2026-04-29 00:00:00",
            "2026-04-30 00:00:00",
            "2026-05-01 00:00:00",
            "2026-05-02 00:00:00",
        ]
    )
    days = detect_measurement_days(dataframe, integration_time=60)

    assert selected_day_indexes_for_range(
        days,
        "2026-04-30",
        "2026-05-01",
    ) == (1, 2)


def test_selected_day_indexes_for_full_measurement_range_selects_all_days():
    dataframe = _dataframe(
        [
            "2026-04-29 08:00:00",
            "2026-04-30 00:00:00",
            "2026-05-01 18:00:00",
        ]
    )
    days = detect_measurement_days(dataframe, integration_time=60)

    assert selected_day_indexes_for_range(
        days,
        "2026-04-29",
        "2026-05-01",
    ) == (0, 1, 2)


def test_selected_day_indexes_for_invalid_range_returns_empty_selection():
    dataframe = _dataframe(
        [
            "2026-04-29 00:00:00",
            "2026-04-30 00:00:00",
        ]
    )
    days = detect_measurement_days(dataframe, integration_time=60)

    assert selected_day_indexes_for_range(
        days,
        "2026-04-30",
        "2026-04-29",
    ) == tuple()


def test_same_time_filter_detects_redundant_full_and_custom_filters():
    dataframe = _dataframe(
        [
            "2026-06-01 00:00:00",
            "2026-06-01 23:59:59",
        ]
    )
    full_a = full_measurement_filter(dataframe)
    full_b = full_measurement_filter(dataframe)
    custom_a = custom_time_filter("2026-06-01 08:00:00", "2026-06-01 18:00:00")
    custom_b = custom_time_filter("2026-06-01 08:00:00", "2026-06-01 18:00:00")
    custom_c = custom_time_filter("2026-06-01 09:00:00", "2026-06-01 18:00:00")

    assert same_time_filter(full_a, full_b)
    assert same_time_filter(custom_a, custom_b)
    assert not same_time_filter(custom_a, custom_c)
