from pydantic import BaseModel

from typing import List, Optional, Self

class AirportInfo(BaseModel):
    name: str
    id: str
    time: str


class FlightModel(BaseModel):
    departure_airport: AirportInfo
    arrival_airport: AirportInfo
    duration: int
    airplane: str
    airline: str
    airline_logo: str
    travel_class: str
    flight_number: str
    extensions: List[str]
    ticket_also_sold_by: Optional[List[str]] = None
    legroom: Optional[str] = None
    overnight: Optional[bool] = None
    often_delayed_by_over_30_min: Optional[bool] = None
    plane_and_crew_by: Optional[str] = None


class LayoverModel(BaseModel):
    duration: int
    name: str
    id: str
    overnight: Optional[bool] = None


class FlightDetailsModel(BaseModel):
    flights: List[FlightModel]
    layovers: Optional[List[LayoverModel]] = None
    total_duration: int
    price: Optional[int] = None
    type: str
    airline_logo: Optional[str] = None # This can be present if multiple airlines
    extensions: Optional[List[str]] = None
    departure_token: Optional[str] = None
    booking_token: Optional[str] = None
    return_flights: Optional[List[Self]] = None


class PriceInsightsModel(BaseModel):
    lowest_price: Optional[int] = None
    price_level: Optional[str] = None
    typical_price_range: Optional[List[int]] = None
    price_history: Optional[List[List[int]]] = None


class FlightsResponseModel(BaseModel):
    best_flights: Optional[List[FlightDetailsModel]] = None
    other_flights: Optional[List[FlightDetailsModel]] = None
    price_insights: Optional[PriceInsightsModel] = None


class FlightSearchParams(BaseModel):
    departure_id: Optional[str] = None
    """Parameter defines the departure airport code or location kgmid.
    An airport code is an uppercase 3-letter code. You can search for it on Google Flights or IATA.
    For example, CDG is Paris Charles de Gaulle Airport and AUS is Austin-Bergstrom International Airport.
    A location kgmid is a string that starts with /m/. You can search for a location on Wikidata and use its "Freebase ID" as the location kgmid. For example, /m/0vzm is the location kgmid for Austin, TX.
    You can specify multiple departure airports by separating them with a comma. For example, CDG,ORY,/m/04jpl."""

    arrival_id: Optional[str] = None
    """Parameter defines the arrival airport code or location kgmid.
    An airport code is an uppercase 3-letter code. You can search for it on Google Flights or IATA.
    For example, CDG is Paris Charles de Gaulle Airport and AUS is Austin-Bergstrom International Airport.
    A location kgmid is a string that starts with /m/. You can search for a location on Wikidata and use its "Freebase ID" as the location kgmid. For example, /m/0vzm is the location kgmid for Austin, TX.
    You can specify multiple arrival airports by separating them with a comma. For example, CDG,ORY,/m/04jpl"""

    gl: Optional[str] = "us"
    """Parameter defines the country to use for the Google Flights search. It's a two-letter country code. (e.g., us for the United States, uk for United Kingdom, or fr for France) Head to the Google countries page for a full list of supported Google countries."""

    hl: Optional[str] = "en"
    """Parameter defines the language to use for the Google Flights search. It's a two-letter language code. (e.g., en for English, es for Spanish, or fr for French). Head to the Google languages page for a full list of supported Google languages."""

    currency: Optional[str] = "USD"
    """Parameter defines the currency of the returned prices. Default to USD. Head to the Google Travel Currencies page for a full list of supported currency codes."""

    type: Optional[int] = None
    """Parameter defines the type of the flights.
    Available options:
    1 - Round trip (default)
    2 - One way
    3 - Multi-city
    When this parameter is set to 3, use multi_city_json to set the flight information.
    To obtain the returning flight information for Round Trip (1), you need to make another request using a departure_token."""

    outbound_date: Optional[str] = None
    """Parameter defines the outbound date. The format is YYYY-MM-DD. e.g. 2025-05-23"""

    return_date: Optional[str] = None
    """Parameter defines the return date. The format is YYYY-MM-DD. e.g. 2025-05-29
    Parameter is required if type parameter is set to: 1 (Round trip)"""

    travel_class: Optional[int] = None
    """Parameter defines the travel class.
    Available options:
    1 - Economy (default)
    2 - Premium economy
    3 - Business
    4 - First"""

    adults: Optional[int] = None
    """Parameter defines the number of adults. Default to 1."""

    sort_by: Optional[int] = None
    """Parameter defines the sorting order of the results.
    Available options:
    1 - Top flights (default)
    2 - Price
    3 - Departure time
    4 - Arrival time
    5 - Duration
    6 - Emissions"""

    stops: Optional[int] = None
    """Parameter defines the number of stops during the flight.
    Available options:
    0 - Any number of stops (default)
    1 - Nonstop only
    2 - 1 stop or fewer
    3 - 2 stops or fewer"""

    exclude_airlines: Optional[str] = None
    """Parameter defines the airline codes to be excluded. Split multiple airlines with comma.
    It can't be used together with include_airlines.
    Each airline code should be a 2-character IATA code consisting of either two uppercase letters or one uppercase letter and one digit. You can search for airline codes on IATA.
    For example, UA is United Airlines.
    Additionally, alliances can be also included here:
    STAR_ALLIANCE - Star Alliance
    SKYTEAM - SkyTeam
    ONEWORLD - Oneworld
    exclude_airlines and include_airlines parameters can't be used together."""

    include_airlines: Optional[str] = None
    """Parameter defines the airline codes to be included. Split multiple airlines with comma.
    It can't be used together with exclude_airlines.
    Each airline code should be a 2-character IATA code consisting of either two uppercase letters or one uppercase letter and one digit. You can search for airline codes on IATA.
    For example, UA is United Airlines.
    Additionally, alliances can be also included here:
    STAR_ALLIANCE - Star Alliance
    SKYTEAM - SkyTeam
    ONEWORLD - Oneworld
    exclude_airlines and include_airlines parameters can't be used together."""

    bags: Optional[int] = None
    """Parameter defines the number of carry-on bags. Default to 0."""

    outbound_times: Optional[str] = None
    """Parameter defines the outbound times range. It's a string containing two (for departure only) or four (for departure and arrival) comma-separated numbers. Each number represents the beginning of an hour. For example:
    4,18: 4:00 AM - 7:00 PM departure
    0,18: 12:00 AM - 7:00 PM departure
    19,23: 7:00 PM - 12:00 AM departure
    4,18,3,19: 4:00 AM - 7:00 PM departure, 3:00 AM - 8:00 PM arrival
    0,23,3,19: unrestricted departure, 3:00 AM - 8:00 PM arrival"""

    return_times: Optional[str] = None
    """Parameter defines the return times range. It's a string containing two (for departure only) or four (for departure and arrival) comma-separated numbers. Each number represents the beginning of an hour. For example:
    4,18: 4:00 AM - 7:00 PM departure
    0,18: 12:00 AM - 7:00 PM departure
    19,23: 7:00 PM - 12:00 AM departure
    4,18,3,19: 4:00 AM - 7:00 PM departure, 3:00 AM - 8:00 PM arrival
    0,23,3,19: unrestricted departure, 3:00 AM - 8:00 PM arrival
    Parameter should only be used when type parameter is set to: 1 (Round trip)"""

    layover_duration: Optional[str] = None
    """Parameter defines the layover duration, in minutes. It's a string containing two comma-separated numbers. For example, specify 90,330 for 1 hr 30 min - 5 hr 30 min."""

    exclude_conns: Optional[str] = None
    """Parameter defines the connecting airport codes to be excluded.
    An airport ID is an uppercase 3-letter code. You can search for it on Google Flights or IATA.
    For example, CDG is Paris Charles de Gaulle Airport and AUS is Austin-Bergstrom International Airport.
    You can also combine multiple Airports by joining them with a comma (value + , + value; eg: CDG,AUS)."""

    max_duration: Optional[int] = None
    """Parameter defines the maximum flight duration, in minutes. For example, specify 1500 for 25 hours."""

    departure_token: Optional[str] = None