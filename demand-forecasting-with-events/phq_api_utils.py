import requests
import pandas as pd
from datetime import datetime, timedelta

BEAM_API_URL = "https://api.predicthq.com/v1/beam"
FEATURES_API_URL = "https://api.predicthq.com/v1/features/"


def _get_start_end_dates(demand_df):
    """
    Extract start and end dates for each location from the demand DataFrame.
    """
    if demand_df is not None:
        start_dates = demand_df.groupby("location")["date"].min().to_dict()
        end_dates = demand_df.groupby("location")["date"].max().to_dict()
        return start_dates, end_dates
    else:
        return {}, {}


def _get_default_start_end_dates():
    """
    Define default start and end dates.
    """
    today = datetime.now()
    default_start = (today - timedelta(days=365 * 2)).strftime("%Y-%m-%d")
    default_end = (today + timedelta(days=90)).strftime("%Y-%m-%d")
    return default_start, default_end


def supplement_config(config, demand_df=None):
    """
    Supplement locations with additional information.
    """
    start_dates, end_dates = _get_start_end_dates(demand_df)
    default_start, default_end = _get_default_start_end_dates()

    for location, info in config.items():

        # industry
        info["industry"] = (
            info.setdefault("industry", "other")
            .lower()
        )

        # start and end dates
        if demand_df is not None:
            info["start"] = start_dates.get(location, default_start)
            info["end"] = end_dates.get(location, default_end)
        else:
            info.setdefault("start", default_start)
            info.setdefault("end", default_end)

    return config


def create_analysis_id(
    location,
    access_token,
    beam_api_url=BEAM_API_URL,
):
    """
    Create an analysis ID for a location.
    """
    json = {
        "name": location["analysis_name"],
        "location": {
            "geopoint": {
                "lat": str(location["lat"]),
                "lon": str(location["lon"]),
            },
        },
        "demand_type":{
            "industry": location["industry"],
            },
    }

    response = requests.post(
        url=f"{beam_api_url}/analyses",
        headers={
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
        },
        json=json,
    )

    return response.json()["analysis_id"]


def upload_demand(demand_json, analysis_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Upload demand data for an analysis.
    """
    response = requests.post(
        url=f"{beam_api_url}/analyses/{analysis_id}/sink",
        headers={
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        },
        data=demand_json,
    )

    if response.status_code == 202:
        print("--- the request has been accepted for processing.")
    else:
        print(response.content)

    return response.status_code


def get_analysis_details(analysis_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Get the details of an analysis.
    """
    response = requests.get(
        url=f"{beam_api_url}/analyses/{analysis_id}",
        headers={
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
        },
    )
    data = response.json()
    return {
        "readiness_status": data.get("readiness_status"),
        "demand_type": data.get("demand_type"),
    }


def refresh_analysis(analysis_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Refresh an analysis.
    """
    response = requests.post(
        url=f"{beam_api_url}/analyses/{analysis_id}/refresh",
        headers={
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
        },
    )

    if response.status_code == 202:
        print("--- the request has been accepted for processing.")
    else:
        print(response.content)

    return response.status_code


def get_feature_importance(analysis_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Get feature importance for an analysis.
    """
    response = requests.get(
        url=f"{beam_api_url}/analyses/{analysis_id}/feature-importance",
        headers={
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
        },
    )

    return response.json()


def create_group(name, analysis_ids, access_token, beam_api_url=BEAM_API_URL):
    """
    Create an analysis group.
    """
    response = requests.post(
        url=f"{beam_api_url}/analysis-groups",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        json={"name": name, "analysis_ids": analysis_ids},
    )

    return response.json()


def group_status(group_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Get the status of an analysis group.
    """
    response = requests.get(
        url=f"{beam_api_url}/analysis-groups/{group_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    data = response.json()
    readiness_status = data.get("readiness_status")
    feature_importance = data.get("processing_completed", {}).get("feature_importance")

    return {
        "readiness_status": readiness_status,
        "feature_importance_processing_completed": feature_importance,
    }


def get_group_feature_importance(group_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Get feature importance for an analysis group.
    """
    response = requests.get(
        url=f"{beam_api_url}/analysis-groups/{group_id}/feature-importance",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    return response.json()


def get_group(group_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Get details for an analysis group.
    """
    response = requests.get(
        url=f"{beam_api_url}/analysis-groups/{group_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    data = response.json()
    name = data["name"]
    excluded_analysis_ids = {
        entry["analysis_id"]
        for entry in data.get("processing_completed", {}).get("excluded_analyses", [])
    }
    analysis_ids = [
        id for id in data.get("analysis_ids", []) if id not in excluded_analysis_ids
    ]

    return {"name": name, "analysis_ids": analysis_ids}


def get_features(
    location,
    access_token,
    group_id=None,
    features_api_url=FEATURES_API_URL,
):
    all_results = []
    url = features_api_url

    beam = {"analysis_id": location["analysis_id"]}
    if group_id:
        beam["group_id"] = group_id

    while url:
        response = requests.post(
            url=url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            json={
                "active": {"gte": location["start"], "lte": location["end"]},
                "beam": beam,
            },
        )

        if response.status_code != 200:
            print(
                f"--- the request failed with status code {response.status_code} {response.text}"
            )

        result = response.json()
        all_results.extend(result.get("results", []))
        url = result.get("next")

    df = pd.json_normalize(all_results, sep="_")
    return df