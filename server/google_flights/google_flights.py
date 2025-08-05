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
    """
    调用Google Flights API并返回格式化的航班搜索结果
    
    参数:
        params (FlightSearchParams): 包含航班搜索参数的数据类对象
        
    返回:
        FlightsResponseModel | str: 成功时返回格式化的航班响应数据，失败时返回错误信息字符串
    """
    # 调用Google Flights API获取搜索结果
    try:
        search = GoogleSearch(create_search_params(params))
        results_dict = search.get_dict()
    except Exception as e:
        logger.error(f"Error calling Google Flights API: {e}")
        return f"Error calling Google Flights API: {e}"

    print_debug_info(results_dict)

    # 检查API响应是否包含有效的航班数据
    if "other_flights" not in results_dict:
        return f"API Error: result: {results_dict}"

    # 将API响应数据解析为FlightsResponseModel数据类对象
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
    """
    打印调试信息函数
    
    该函数用于从结果字典中提取并记录航班搜索的调试信息，
    包括搜索参数和JSON端点信息。
    
    参数:
        results_dict (dict): 包含搜索结果的字典，可能包含搜索参数和元数据
        
    返回值:
        无返回值
    """
    # 检查并记录航班搜索参数
    if "search_parameters" in results_dict:
        search_parameters = results_dict["search_parameters"]
        logger.info(f"returned flight search parameters: {search_parameters}")

    # 检查并记录航班搜索的JSON端点信息
    if "search_metadata" in results_dict:
        json_endpoint = results_dict["search_metadata"].get("json_endpoint", None)
        logger.info(f"Flight search JSON endpoint: {json_endpoint}")

def get_return_flights(flight_details: FlightDetailsModel, search_params: FlightSearchParams, max_results: int) -> List[FlightDetailsModel]:
    """
    获取返回航班信息
    
    参数:
        flight_details (FlightDetailsModel): 航班详情模型，包含出发航班信息
        search_params (FlightSearchParams): 航班搜索参数
        max_results (int): 返回结果的最大数量
    
    返回:
        List[FlightDetailsModel]: 返回航班详情模型列表，按优先级排序
    """
    # 如果没有出发令牌，则无法获取返回航班
    if not flight_details.departure_token:
        return []

    logger.info(f"Getting return flights for {flight_details.departure_token}")
    # 设置搜索参数中的出发令牌
    search_params.departure_token = flight_details.departure_token
    response = call_search_api(search_params)
    # 如果API调用返回错误信息，则返回空列表
    if isinstance(response, str):
        return []

    # 优先返回最佳航班，如果没有则返回其他航班
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
              - 1: Round trip. If selected, [return_date](file:///Users/zhangzhihao/mcp/mcp-demo/server/google_flights/result_class.py#L96-L96) is also required.
                   The function will attempt to fetch return flights.
              - 2: One-way trip.
        return_date: The date of the return flight for round trips, formatted as
                     YYYY-MM-DD (e.g., "2025-01-05"). This parameter is
                     required if [type](file:///Users/zhangzhihao/mcp/mcp-demo/server/google_flights/result_class.py#L39-L39) is 1, and ignored otherwise.
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
    # 检查往返类型是否提供了返回日期
    if type == 1 and not return_date:
        return "Error: Return date is required for round trip flights (type=1)."

    # 构造出发出程航班搜索参数
    params_outbound = FlightSearchParams(
        departure_id=departure_id,
        arrival_id=arrival_id,
        outbound_date=outbound_date,
        type=type,
    )

    # 如果是往返类型且提供了返回日期，则设置返回日期
    if type == 1 and return_date:
        params_outbound.return_date = return_date

    # 调用API获取出发出程航班数据
    response_model_outbound = call_search_api(params_outbound)
    if isinstance(response_model_outbound, str):
        return response_model_outbound

    # 合并最佳航班和其他航班结果，并截取前max_results个作为出发出程航班
    total_flights = (response_model_outbound.best_flights or []) + (response_model_outbound.other_flights or [])
    departure_flights: List[FlightDetailsModel] = total_flights[:max_results]

    # 若没有找到任何出发出程航班信息，返回错误提示
    if not departure_flights:
        return "No flight data (best_flights or other_flights) found in the API response for the outbound journey."

    # 如果是往返类型，为每个出发出程航班获取对应的返程航班
    if type == 1:
        for flight_detail in departure_flights:
            return_flights = get_return_flights(flight_detail, params_outbound, max_results)
            flight_detail.return_flights = return_flights

    # 将航班对象转换为字典并排除空值字段
    output_data = [flight.model_dump(exclude_none=True) for flight in departure_flights]

    # 尝试将结果序列化为JSON字符串返回
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
