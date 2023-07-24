from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

DOMAIN = "heweather"

CONFIG_OPTIONS = {
    "disaster_warn": "灾害预警信息",
    "temprature": "温度",
    "humidity": "湿度",
    "category": "空气质量",
    "feelsLike": "体感温度",
    "text": "天气情况",
    "windDir": "风向",
    "windScale": "风力",
    "windSpeed": "风速",
    "pressure": "大气压强",
    "vis": "能见度",
    "cloud": "云量",
    "dew": "露点温度",
    "precip": "当前小时累计降水量",
    "qlty": "AQI空气质量",
    "level": "空气质量级别",
    "primary": "主要污染物",
    "pm25": "PM2.5",
    "pm10": "PM10",
    "co": "一氧化碳",
    "so2": "二氧化硫",
    "no2": "二氧化氮",
    "o3": "臭氧"
}

CONFIG_DISASTER_LEVEL = {
    "1": "标准-Standard",
    "2": "次要-Minor",
    "3": "中等-Moderate",
    "4": "主要-Major",
    "5": "严重-Severe",
    "6": "极端-Extreme"
}

CONFIG_DISASTER_MSG = {
    "allmsg": "标题+明细信息",
    "title": "仅标题"
}

PLATFORMS: list[Platform] = [
    Platform.SENSOR
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Triggered by config entry options updates."""
    await hass.config_entries.async_reload(entry.entry_id)
