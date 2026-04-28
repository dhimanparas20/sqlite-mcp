"""Weather tool."""

from langchain_community.tools.openweathermap.tool import OpenWeatherMapQueryRun
from langchain_community.utilities import OpenWeatherMapAPIWrapper

weather_wrapper = OpenWeatherMapAPIWrapper()
weather_tool = OpenWeatherMapQueryRun(api_wrapper=weather_wrapper)
