import os
from typing import List, Optional, Self

from result_class import FlightDetailsModel, FlightsResponseModel, FlightSearchParams

from mcp.server.fastmcp import FastMCP # Assuming this path is correct
from serpapi import GoogleSearch
import json
import logging
import dotenv 
dotenv.load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

# 将我们定义的 参数对象转换为对应格式的 JSON
def create_search_params(params: FlightSearchParams) -> dict:
    res = params.model_dump(exclude_none=True)
    res["api_key"] = GOOGLE_FLIGHTS_API_KEY
    res["engine"] = "google_flights"
    logger.info(f"Flight search params: {res}")

    return res

# 调用Serpapi API，并将返回的JSON转换为 对应格式的 Dataclass
def call_search_api(params: FlightSearchParams) -> FlightsResponseModel | str:
    try:
        search = GoogleSearch(create_search_params(params))
        results_dict = search.get_dict()
    except Exception as e:
        logger.error(f"Error calling Google Flights API: {e}")
        return f"Error calling Google Flights API: {e}"

    print_debug_info(results_dict)

    if "other_flights" not in results_dict:
        return f"API Error: result: {results_dict}"


    try:
        response_model = FlightsResponseModel.model_validate(results_dict)
    except Exception as e: # Handles PydanticValidationError, etc.
        logger.error(f"Error parsing outbound API response: {e}. Raw results snippet: {str(results_dict)[:500]}")
        return f"Error parsing API response: {e}. Raw results snippet: {str(results_dict)[:500]}"

    return response_model


# Initialize FastMCP server
mcp = FastMCP("google_flights")

GOOGLE_FLIGHTS_API_KEY = os.getenv("SERPAPI_API_KEY")

def print_debug_info(results_dict: dict):
    if "search_parameters" in results_dict:
        search_parameters = results_dict["search_parameters"]
        logger.info(f"returned flight search parameters: {search_parameters}")

    if "search_metadata" in results_dict:
        json_endpoint = results_dict["search_metadata"].get("json_endpoint", None)
        logger.info(f"Flight search JSON endpoint: {json_endpoint}")

def get_return_flights(flight_details: FlightDetailsModel, search_params: FlightSearchParams, max_results: int) -> List[FlightDetailsModel]:
    if not flight_details.departure_token:
        return []

    logger.info(f"Getting return flights for {flight_details.departure_token}")
    search_params.departure_token = flight_details.departure_token
    response = call_search_api(search_params)
    if isinstance(response, str):
        return []

    if response.best_flights:
        return response.best_flights[:max_results]
    elif response.other_flights:
        return response.other_flights[:max_results]
    else:
        return []

# mcp工具
@mcp.tool()
async def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,  # Format: YYYY-MM-DD
    type: int,  # 1 for Round trip, 2 for One way
    return_date: Optional[str] = None,  # Format: YYYY-MM-DD, required if type is 1,
    max_results: Optional[int] = 10
) -> str:
    """
    Searches for flight information using the Google Flights API via SerpApi.

    This tool queries the Google Flights engine to find the best and other available
    flight options based on the provided departure and arrival locations, dates,
    and trip type. 

    Args:
        departure_id: The departure airport code (e.g., "SFO", "JFK") or a
                      Google KG Midtown ID (e.g., "/m/0vzm" for Austin, TX).
                      This specifies the origin of the flight.
        arrival_id: The arrival airport code (e.g., "LAX", "CDG") or a
                    Google KG Midtown ID (e.g., "/m/04jpl" for London).
                    This specifies the destination of the flight.
        outbound_date: The date of the outbound flight, formatted as YYYY-MM-DD.
                       (e.g., "2024-12-25").
        type: An integer indicating the type of trip.
              - 1: Round trip. If selected, `return_date` is also required.
                   The function will attempt to fetch return flights.
              - 2: One-way trip.
        return_date: The date of the return flight for round trips, formatted as
                     YYYY-MM-DD (e.g., "2025-01-05"). This parameter is
                     required if `type` is 1, and ignored otherwise.
        max_results: The maximum number of search flight results to return for each
                     category (e.g., best outbound, other outbound, best return, etc.). Default is 10.

    Returns:
        A list of flight objects. Each flight object is the departure flight, 
        and if the trip is a round trip, its return_flights field will also include the return flights of the departure flight.
        note the return size is controlled by the max_results parameter.
        if the type is round trip, and if max_results is 2, in the returned results there are 2 departure flights, and each of them has 2 return flights,
        So there are totally 4 round trip flights.
        if the type is one way, the returned results will only include the departure flights.
    """
    if type == 1 and not return_date:
        return "Error: Return date is required for round trip flights (type=1)."

    params_outbound = FlightSearchParams(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        type=type,
    )

    if type == 1 and return_date:
        params_outbound.return_date = return_date

    response_model_outbound = call_search_api(params_outbound)
    if isinstance(response_model_outbound, str):
        return response_model_outbound

    total_flights = (response_model_outbound.best_flights or []) + (response_model_outbound.other_flights or [])
    departure_flights: List[FlightDetailsModel] = total_flights[:max_results]

    if not departure_flights:
        return "No flight data (best_flights or other_flights) found in the API response for the outbound journey."

    if type == 1:
        for flight_detail in departure_flights:
            return_flights = get_return_flights(flight_detail, params_outbound, max_results)
            flight_detail.return_flights = return_flights

    output_data = [flight.model_dump(exclude_none=True) for flight in departure_flights]

    try:
        json_output = json.dumps(output_data)
        return json_output
    except Exception as e:
        logger.error(f"Error formatting output data to JSON: {e}")
        return f"Error formatting output data to JSON: {e}"

if __name__ == "__main__":
    # This allows running the MCP server directly for this tool
    # Ensure that mcp.server.fastmcp is accessible in your PYTHONPATH
    # Example command to run: python server/google_flights.py
    mcp.run(transport='stdio')
