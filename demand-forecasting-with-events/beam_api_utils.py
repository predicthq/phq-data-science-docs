import pandas as pd
import requests

BEAM_API_URL = "https://api.predicthq.com/v1/beam"


def _get_start_end_dates(demand_df):
    """
    Extract start and end dates for each location from the demand DataFrame.
    """
    start_dates = demand_df.groupby("location")["date"].min().to_dict()
    end_dates = demand_df.groupby("location")["date"].max().to_dict()
    return start_dates, end_dates


def _get_suggested_radius(info, phq_client):
    """
    Fetch suggested radius.
    """
    search_params = {
        "location__origin": f"{info['lat']},{info['lon']}",
        "radius_unit": "mi",
    }
    if info["industry"] != "other":
        search_params["industry"] = info["industry"]

    try:
        suggested_radius = phq_client.radius.search(**search_params)
        return suggested_radius.radius, suggested_radius.radius_unit
    except Exception as e:
        print(f"Error retrieving radius for {info['lat']},{info['lon']}: {str(e)}")
        return None, None


def supplement_config(config, demand_df, phq_client):
    """
    Supplement locations with additional information.
    """
    start_dates, end_dates = _get_start_end_dates(demand_df)

    for location, info in config.items():

        # industry
        if "industry" in info:
            info["industry"] = (
                info["industry"].lower().replace("food_and_beverage", "restaurants")
            )
        else:
            info["industry"] = "other"

        # min_phq_rank
        if "min_phq_rank" not in info:
            industry_min_phq_ranks = {
                "accommodation": 35,
                "parking": 35,
                "restaurants": 30,
                "retail": 50,
            }
            info["min_phq_rank"] = industry_min_phq_ranks.get(info.get("industry"), 30)

        # start and end dates of demand data
        info["start"] = start_dates.get(location, None)
        info["end"] = end_dates.get(location, None)

        # suggested radius
        radius, radius_unit = _get_suggested_radius(info, phq_client)
        if radius is not None and radius_unit is not None:
            info["radius"] = radius
            info["radius_unit"] = radius_unit
        else:
            print(f"Failed to get suggested radius for {location}")

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
            "radius": location["radius"],
            "unit": location["radius_unit"],
        },
        "rank": {"type": "phq", "levels": {"phq": {"min": location["min_phq_rank"]}}},
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
        return print("--- the request has been accepted for processing.")
    else:
        return print(response.content)


def readiness_status(analysis_id, access_token, beam_api_url=BEAM_API_URL):
    """
    Get the readiness status of an analysis.
    """
    response = requests.get(
        url=f"{beam_api_url}/analyses/{analysis_id}",
        headers={
            "Authorization": "Bearer " + access_token,
            "Accept": "application/json",
        },
    )

    return response.json()["readiness_status"]


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
        return print("--- the request has been accepted for processing.")
    else:
        return print(response.content)


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
