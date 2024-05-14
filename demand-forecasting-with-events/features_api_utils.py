import pandas as pd
from datetime import datetime, timedelta


DATE_FORMAT = "%Y-%m-%d"


def get_date_groups(start, end):
    """
    Features API allows a range of up to 91 days, so we have to do several requests.
    """
    start_date = datetime.strptime(start, DATE_FORMAT).date()
    end_date = datetime.strptime(end, DATE_FORMAT).date()
    # The interval is set to be the number of days of whole weeks.
    interval = timedelta(days=91)

    current_date = start_date
    while current_date < end_date:
        next_date = min(current_date + interval, end_date)
        yield current_date.strftime(DATE_FORMAT), (
            next_date - timedelta(days=1 if next_date < end_date else 0)
        ).strftime(DATE_FORMAT)
        current_date = next_date


def get_preferred_stat(feature):
    """
    Get the preferred statistic for a feature.
    """
    if "attendance" in feature or "spend" in feature:
        return "sum"
    elif "impact" in feature or "viewership" in feature:
        return "max"
    return "sum"


def construct_record(feature):
    """
    Construct a record from feature data based on the feature type.
    """
    record = {"date": feature.get("date").strftime(DATE_FORMAT)}
    for k, v in feature.items():
        if any(
            keyword in k for keyword in ["attendance", "spend", "impact", "viewership"]
        ):
            record[k] = v.get("stats", {}).get(get_preferred_stat(k))
        elif "rank" in k:
            record[k] = sum(
                int(rank) * int(count)
                for rank, count in v.get("rank_levels", {}).items()
            )
    return record


def get_features(info, features, phq_client):
    """
    Fetch features from Features API based on the config and list of features.
    """
    result = []

    # features list
    if not isinstance(features, list) or not features:
        raise ValueError("Missing or invalid features list provided.")

    for gte, lte in get_date_groups(info["start"], info["end"]):
        query = {
            "active__gte": gte,
            "active__lte": lte,
        }

        if info["interval"] == "week":
            query["interval"] = "week"
            query["week_start_day"] = info["week_start_day"]

        # location information
        if all(k in info for k in ["lat", "lon", "radius", "radius_unit"]):
            query["location__geo"] = {
                "lat": info["lat"],
                "lon": info["lon"],
                "radius": f"{info['radius']}{info['radius_unit']}",
            }
        elif "place_id" in info:
            query["location__place_id"] = info["place_id"]
        else:
            raise ValueError("Missing location information in config.")

        # add features to query and get data
        for feature in features:
            if "rank" in feature:
                query[f"{feature}"] = True
            else:
                query[f"{feature}__stats"] = [get_preferred_stat(feature)]
                query[f"{feature}__phq_rank"] = {"gte": info["min_phq_rank"]}

        try:
            features_data = phq_client.features.obtain_features(**query)
            for feature in features_data:
                record = construct_record(
                    feature.model_dump(exclude_unset=True, exclude_none=True)
                )
                result.append(record)
        except Exception as e:
            raise Exception("Failed to fetch or process features data.") from e

    return pd.DataFrame(result)
