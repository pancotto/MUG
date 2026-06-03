from dataclasses import dataclass

import pandas as pd


FIRST_RECORD_OF_DAY = "__FIRST_RECORD_OF_DAY__"
LAST_RECORD_OF_DAY = "__LAST_RECORD_OF_DAY__"
FIRST_RECORD_LABEL = "PRIMEIRO REGISTRO DO DIA"
LAST_RECORD_LABEL = "ÚLTIMO REGISTRO DO DIA"


@dataclass(frozen=True)
class TimeFilter:
    start_datetime: pd.Timestamp | None
    end_datetime: pd.Timestamp | None
    label: str

    @property
    def is_full_measurement(self) -> bool:
        return self.start_datetime is None and self.end_datetime is None


@dataclass(frozen=True)
class DetectedDay:
    date: pd.Timestamp
    start_datetime: pd.Timestamp
    end_datetime: pd.Timestamp
    status: str

    @property
    def label(self) -> str:
        return self.date.strftime("%d/%m/%Y")


def normalize_datetime_series(dataframe: pd.DataFrame) -> pd.Series:
    if "Datetime" not in dataframe.columns:
        raise ValueError("A coluna 'Datetime' não foi encontrada.")

    return pd.to_datetime(dataframe["Datetime"], errors="coerce")


def get_measurement_bounds(dataframe: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    datetimes = normalize_datetime_series(dataframe).dropna()

    if datetimes.empty:
        raise ValueError("Não há registros válidos de data/hora na medição.")

    return pd.Timestamp(datetimes.min()), pd.Timestamp(datetimes.max())


def full_measurement_filter(dataframe: pd.DataFrame) -> TimeFilter:
    get_measurement_bounds(dataframe)
    return TimeFilter(
        start_datetime=None,
        end_datetime=None,
        label="Medição Completa",
    )


def detect_measurement_days(
    dataframe: pd.DataFrame,
    integration_time: int | float | None,
) -> tuple[DetectedDay, ...]:
    datetimes = normalize_datetime_series(dataframe).dropna().sort_values()

    if datetimes.empty:
        return tuple()

    tolerance_seconds = max(float(integration_time or 0), 60.0)
    days: list[DetectedDay] = []

    for day_value, day_datetimes in datetimes.groupby(datetimes.dt.normalize()):
        day_start = pd.Timestamp(day_datetimes.min())
        day_end = pd.Timestamp(day_datetimes.max())
        expected_start = pd.Timestamp(day_value).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        expected_end = pd.Timestamp(day_value).replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=0,
        )

        start_delta = abs((day_start - expected_start).total_seconds())
        end_delta = abs((expected_end - day_end).total_seconds())
        status = (
            "Complete"
            if start_delta <= tolerance_seconds and end_delta <= tolerance_seconds
            else "Incomplete"
        )

        days.append(
            DetectedDay(
                date=pd.Timestamp(day_value),
                start_datetime=day_start,
                end_datetime=day_end,
                status=status,
            )
        )

    return tuple(days)


def day_filter(day: DetectedDay) -> TimeFilter:
    start = day.date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = day.date.replace(hour=23, minute=59, second=59, microsecond=0)

    return TimeFilter(
        start_datetime=pd.Timestamp(start),
        end_datetime=pd.Timestamp(end),
        label=day.label,
    )


def custom_time_filter(start_datetime, end_datetime, label: str = "Seleção personalizada") -> TimeFilter:
    start = pd.Timestamp(start_datetime)
    end = pd.Timestamp(end_datetime)

    if end < start:
        raise ValueError("A data/hora final deve ser maior ou igual à inicial.")

    return TimeFilter(start_datetime=start, end_datetime=end, label=label)


def same_time_filter(left: TimeFilter | None, right: TimeFilter | None) -> bool:
    if left is None or right is None:
        return left is right

    if left.is_full_measurement or right.is_full_measurement:
        return left.is_full_measurement and right.is_full_measurement

    return (
        pd.Timestamp(left.start_datetime) == pd.Timestamp(right.start_datetime)
        and pd.Timestamp(left.end_datetime) == pd.Timestamp(right.end_datetime)
    )


def filter_matches_measurement_bounds(dataframe: pd.DataFrame, time_filter: TimeFilter) -> bool:
    if time_filter.is_full_measurement:
        return True

    if time_filter.start_datetime is None or time_filter.end_datetime is None:
        return False

    start, end = get_measurement_bounds(dataframe)
    return (
        pd.Timestamp(time_filter.start_datetime) == start
        and pd.Timestamp(time_filter.end_datetime) == end
    )


def apply_time_filter(dataframe: pd.DataFrame, time_filter: TimeFilter) -> pd.DataFrame:
    if time_filter.is_full_measurement:
        return dataframe.copy()

    datetimes = normalize_datetime_series(dataframe)
    mask = pd.Series(True, index=dataframe.index)

    if time_filter.start_datetime is not None:
        mask &= datetimes >= pd.Timestamp(time_filter.start_datetime)

    if time_filter.end_datetime is not None:
        mask &= datetimes <= pd.Timestamp(time_filter.end_datetime)

    return dataframe.loc[mask].copy()


def measurement_date_options(dataframe: pd.DataFrame) -> tuple[pd.Timestamp, ...]:
    datetimes = normalize_datetime_series(dataframe).dropna().sort_values()
    if datetimes.empty:
        return tuple()

    return tuple(pd.Timestamp(value) for value in datetimes.dt.normalize().drop_duplicates())


def time_options_for_integration(integration_time: int | float | None) -> tuple[str, ...]:
    try:
        step_seconds = int(float(integration_time or 0))
    except Exception:
        step_seconds = 0

    if step_seconds <= 0 or step_seconds > 3600:
        step_seconds = 60

    values: list[str] = []
    seconds = 0
    while seconds < 86400:
        hour = seconds // 3600
        minute = (seconds % 3600) // 60
        second = seconds % 60
        values.append(f"{hour:02d}:{minute:02d}:{second:02d}")
        seconds += step_seconds

    if values[-1] != "23:59:59":
        values.append("23:59:59")

    return tuple(dict.fromkeys(values))


def day_bounds_for_date(
    detected_days: tuple[DetectedDay, ...],
    date_value: str | pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    target = pd.Timestamp(date_value).normalize()

    for day in detected_days:
        if pd.Timestamp(day.date).normalize() == target:
            return day.start_datetime, day.end_datetime

    raise ValueError("Data selecionada não encontrada na medição.")


def resolve_time_option(
    detected_days: tuple[DetectedDay, ...],
    date_value: str | pd.Timestamp,
    time_value: str,
) -> pd.Timestamp:
    day_start, day_end = day_bounds_for_date(detected_days, date_value)

    if time_value == FIRST_RECORD_OF_DAY:
        return pd.Timestamp(day_start)

    if time_value == LAST_RECORD_OF_DAY:
        return pd.Timestamp(day_end)

    return pd.Timestamp(f"{pd.Timestamp(date_value).strftime('%Y-%m-%d')} {time_value}")


def format_datetime(value: pd.Timestamp | None) -> str:
    if value is None:
        return ""
    return pd.Timestamp(value).strftime("%d/%m/%Y %H:%M:%S")


def format_time(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%H:%M")


def format_duration(start_datetime: pd.Timestamp, end_datetime: pd.Timestamp) -> str:
    seconds = max(0, int((end_datetime - start_datetime).total_seconds()))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days and not hours and not minutes and not seconds:
        return f"{days} dia" if days == 1 else f"{days} dias"

    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}min")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


def bounds_from_filter(
    dataframe: pd.DataFrame,
    time_filter: TimeFilter,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if time_filter.is_full_measurement:
        return get_measurement_bounds(dataframe)

    if time_filter.start_datetime is None or time_filter.end_datetime is None:
        raise ValueError("Filtro de tempo incompleto.")

    return pd.Timestamp(time_filter.start_datetime), pd.Timestamp(time_filter.end_datetime)
