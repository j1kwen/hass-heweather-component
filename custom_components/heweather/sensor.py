import logging
import re
from datetime import timedelta

# 此处引入了几个异步处理的库
import aiohttp

import voluptuous as vol

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_FRIENDLY_NAME,
    TEMP_CELSIUS,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    PRECIPITATION_MILLIMETERS_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    PRESSURE_HPA,
    LENGTH_KILOMETERS
)
from homeassistant.helpers.entity import Entity, DeviceInfo
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

TIME_BETWEEN_UPDATES = timedelta(seconds=600)

CONF_OPTIONS = "options"
CONF_LOCATION = "location"
CONF_KEY = "key"
CONF_DISASTERLEVEL = "disasterlevel"
CONF_DISASTERMSG = "disastermsg"
CONF_NAME = "name"
CONF_ID = "id"

# 定义三个可选项：温度、湿度、PM2.5
OPTIONS = {
    "temprature": ["temperature", "室外温度", "mdi:thermometer", TEMP_CELSIUS],
    "humidity": ["humidity", "室外湿度", "mdi:water-percent", PERCENTAGE],
    "feelsLike": ["feelsLike", "体感温度", "mdi:home-thermometer", TEMP_CELSIUS],
    "text": ["text", "天气描述", "mdi:weather-sunny", ' '],
    "precip": ["precip", "小时降水量", "mdi:weather-rainy", PRECIPITATION_MILLIMETERS_PER_HOUR],
    "windDir": ["windDir", "风向", "mdi:windsock", ' '],
    "windScale": ["windScale", "风力等级", "mdi:weather-windy", ' '],
    "windSpeed": ["windSpeed", "风速", "mdi:weather-windy", SPEED_KILOMETERS_PER_HOUR],

    
    "dew": ["dew", "露点温度", "mdi:thermometer-water", TEMP_CELSIUS],
    "pressure": ["pressure", "大气压强", "mdi:car-brake-low-pressure", PRESSURE_HPA],
    "vis": ["vis", "能见度", "mdi:eye", LENGTH_KILOMETERS],
    "cloud": ["cloud", "云量", "mdi:weather-cloudy", PERCENTAGE],
    
    
    
    "primary": ["primary", "空气质量的主要污染物", "mdi:face-mask", " "],
    "category": ["category", "空气质量指数级别", "mdi:quality-high", " "],
    "level": ["level", "空气质量指数等级", "mdi:quality-high", " "],
    "pm25": ["pm25", "PM2.5", "mdi:grain", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER],
    "pm10": ["pm10", "PM10", "mdi:grain", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER],
    
    
    "no2": ["no2", "二氧化氮", "mdi:emoticon-dead", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER],
    "so2": ["so2", "二氧化硫", "mdi:emoticon-dead", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER],
    "co": ["co", "一氧化碳", "mdi:molecule-co", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER],
    "o3": ["o3", "臭氧", "mdi:weather-cloudy", CONCENTRATION_MICROGRAMS_PER_CUBIC_METER],
    "qlty": ["qlty", "综合空气质量", "mdi:quality-high", " "],
    "disaster_warn": ["disaster_warn", "灾害预警", "mdi:alert", " "],

}
DISASTER_LEVEL = {
    "Missing": 0,
    "Cancel":0,
    "None":0,
    "Unknown":0,
    "Standard":1,
    "Minor":2,
    "Moderate":3,
    "Major":4,
    "Severe":5,
    "Extreme":6
}
ATTR_UPDATE_TIME = "更新时间"
ATTRIBUTION = "来自和风天气的天气数据"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    _LOGGER.info(f"setup platform Heweather, location {config_entry.data.get('location_name')}...")

    location = config_entry.data.get(CONF_LOCATION)
    name = config_entry.data.get(CONF_NAME)
    id = config_entry.data.get(CONF_ID)
    key = config_entry.data.get(CONF_KEY)
    disastermsg = config_entry.data.get(CONF_DISASTERMSG)
    disasterlevel = config_entry.data.get(CONF_DISASTERLEVEL)
    data = WeatherData(hass, location, key, disastermsg, disasterlevel)  
    await data.async_update(dt_util.now()) 
    async_track_time_interval(hass, data.async_update, TIME_BETWEEN_UPDATES)

    dev = []
    for option in config_entry.data[CONF_OPTIONS]:
        dev.append(HeweatherWeatherSensor(data, option, location, name, id))
    async_add_entities(dev, True)


class HeweatherWeatherSensor(Entity):
    """定义一个温度传感器的类，继承自HomeAssistant的Entity类."""

    def __init__(self, data, option, location, name, id):
        """初始化."""
        self._data = data
        self._id = id
        self._type_name = OPTIONS[option][0]
        self._friendly_name = OPTIONS[option][1]
        self._icon = OPTIONS[option][2]
        self._unit_of_measurement = OPTIONS[option][3]
        self._name = name if name else location
        self._location = location

        self._type = option
        self._state = None
        self._updatetime = None
        self._attr_unique_id = self._type_name + location
        self._attr_has_entity_name = True

        self.entity_id = DOMAIN + "." + id + "_" + self._type_name

    @property
    def device_info(self) -> DeviceInfo:
        """Device info"""
        return DeviceInfo(
            identifiers={(DOMAIN, self._location)},
            name=self._name,
            manufacturer="和风天气",
            model=self._id,
            sw_version="Web API v7免费版",
        )

    @property
    def name(self):
        """返回实体的名字."""
        return self._friendly_name

    @property
    def state(self):
        """返回当前的状态."""
        return self._state

    @property
    def icon(self):
        """返回icon属性."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """返回unit_of_measuremeng属性."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """设置其它一些属性值."""
        if self._state is not None:
            return {
                ATTR_ATTRIBUTION: ATTRIBUTION,
                ATTR_UPDATE_TIME: self._updatetime
            }

    async def async_update(self):
        """update函数变成了async_update."""
        self._updatetime = self._data.updatetime
        self._state = {
            "temprature": self._data.temprature,
            "humidity": self._data.humidity,
            "feelsLike": self._data.feelsLike,
            "text": self._data.text,
            "windDir": self._data.windDir,
            "windScale": self._data.windScale,
            "windSpeed": self._data.windSpeed,
            "precip": self._data.precip,
            "pressure": self._data.pressure,
            "vis": self._data.vis,
            "dew": self._data.dew,
            "cloud": self._data.cloud,
            "category": self._data.category,
            "primary": self._data.primary,
            "level": self._data.level,
            "pm10": self._data.pm10,
            "pm25": self._data.pm25,
            "no2": self._data.no2,
            "so2": self._data.so2,
            "co": self._data.co,
            "o3": self._data.o3,
            "qlty": self._data.qlty,
            "disaster_warn": self._data.disaster_warn
        }.get(self._type, None)



class WeatherData(object):
    """天气相关的数据，存储在这个类中."""

    def __init__(self, hass, location, key, disastermsg, disasterlevel):
        """初始化函数."""
        self._hass = hass
        self._disastermsg = disastermsg
        self._disasterlevel = disasterlevel
        #disastermsg, disasterlevel

       # self._url = "https://free-api.heweather.com/s6/weather/now"
        self._weather_now_url = f"https://devapi.qweather.com/v7/weather/now?location={location}&key={key}"
        self._air_now_url = f"https://devapi.qweather.com/v7/air/now?location={location}&key={key}"
        self._disaster_warn_url = f"https://devapi.qweather.com/v7/warning/now?location={location}&key={key}"
        self._params = {
            "location": location, 
            "key": key
        }
        self._temprature = None
        self._humidity = None
        
        self._feelsLike = None
        self._text = None
        self._windDir = None
        self._windScale = None
        self._windSpeed = None
        self._precip = None
        self._pressure = None
        self._vis = None
        self._cloud = None
        self._dew = None
        self._updatetime = None

        self._category = None 
        self._pm10 = None
        self._primary = None
        self._level = None

        self._pm25 = None
        self._no2 = None
        self._so2 = None
        self._co = None
        self._o3 = None
        self._qlty = None
        self._disaster_warn = None
        self._updatetime = None

    @property
    def temprature(self):
        """温度."""
        return self._temprature

    @property
    def humidity(self):
        """湿度."""
        return self._humidity

    @property
    def feelsLike(self):
        """体感温度"""
        return self._feelsLike

    @property
    def text(self):
        """天气状况的文字描述，包括阴晴雨雪等天气状态的描述"""
        return self._text
    
    @property
    def windDir(self):
        """风向"""
        return self._windDir
    
    @property
    def category(self):
        """空气质量指数级别"""
        return self._category
    
    @property
    def level(self):
        """空气质量指数等级"""
        return self._level

    @property
    def primary(self):
        """空气质量的主要污染物，空气质量为优时，返回值为NA"""
        return self._primary
    
    @property
    def windScale(self):
        """风力等级"""
        return self._windScale

    @property
    def windSpeed(self):
        """风速，公里/小时"""
        return self._windSpeed

    @property
    def precip(self):
        """当前小时累计降水量，默认单位：毫米"""
        return self._precip

    @property
    def pressure(self):
        """大气压强，默认单位：百帕"""
        return self._pressure
    
    @property
    def vis(self):
        """能见度，默认单位：公里"""
        return self._vis
   
    @property
    def cloud(self):
        """云量，百分比数值。可能为空"""
        return self._cloud

    @property
    def dew(self):
        """露点温度。可能为空"""
        return self._dew

    @property
    def pm25(self):
        """pm2.5"""
        return self._pm25

    @property
    def pm10(self):
        """pm10"""
        return self._pm10
    
    @property
    def qlty(self):
        """(aqi)空气质量指数"""
        return self._qlty
    
    @property
    def no2(self):
        """no2"""
        return self._no2

    @property
    def co(self):
        """co"""
        return self._co
    
    @property
    def so2(self):
        """so2"""
        return self._so2
    
    @property
    def o3(self):
        """o3"""
        return self._o3
    
    @property
    def disaster_warn(self):
        """灾害预警"""
        return self._disaster_warn
    
    
    @property
    def updatetime(self):
        """更新时间."""
        return self._updatetime

    async def async_update(self, now=""):
        """从远程更新信息."""
        _LOGGER.info(f"Update for location {self._params['location']} from HeFeng API...")

        # 通过HTTP访问，获取需要的信息
        # 此处使用了基于aiohttp库的async_get_clientsession
        try:
            timeout = aiohttp.ClientTimeout(total=20)  
            connector = aiohttp.TCPConnector(limit=10)  
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(self._weather_now_url) as response:
                    if (json_data := await response.json())["code"] == "401":
                        raise PermissionError()
                    weather = json_data["now"]
                async with session.get(self._air_now_url) as response:
                    air = (await response.json())["now"]
                async with session.get(self._disaster_warn_url) as response:
                    disaster_warn = (await response.json())["warning"]
        except(aiohttp.ClientError) as e:
            _LOGGER.error("Error while accessing: %s", self._weather_now_url)
            raise ConnectionError()

        # 根据http返回的结果，更新数据
        self._temprature = weather["temp"]
        self._humidity = weather["humidity"]
        
        self._feelsLike = weather["feelsLike"]
        self._text = weather["text"]
        self._windDir = weather["windDir"]
        self._windScale = weather["windScale"]
        self._windSpeed = weather["windSpeed"]
        self._precip = weather["precip"]
        self._pressure = weather["pressure"]
        self._vis = weather["vis"]
        self._cloud = weather["cloud"]
        self._dew = weather["dew"]
        self._updatetime = weather["obsTime"]

        self._category = air["category"]
        self._pm25 = air["pm2p5"]
        self._pm10 = air["pm10"]
        self._primary = air["primary"]
        self._level = air["level"]

        self._no2 = air["no2"]
        self._so2 = air["so2"]
        self._co = air["co"]
        self._o3 = air["o3"]
        self._qlty = air["aqi"]
        
        allmsg = []
        titlemsg = []
        for i in disaster_warn:
            #if DISASTER_LEVEL[i["severity"]] >= 订阅等级:
            if DISASTER_LEVEL.get(i["severity"], 0) >= int(self._disasterlevel):
                titlemsg.append(simple_title := re.search(r"发布(.*?)$", i["title"]).group(1)) 
                allmsg.append(f'{simple_title}-{i["text"]}')

        if len(titlemsg) == 0:
            self._disaster_warn = f'近日无{self._disasterlevel}级及以上灾害'  
        #if(订阅标题)
        elif self._disastermsg == 'title':
            self._disaster_warn = "#".join(titlemsg)[:255]
        else:
            self._disaster_warn = "#".join(allmsg)[:255]