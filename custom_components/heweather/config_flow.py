"""Config flow for AILiNK integration."""
from __future__ import annotations

import logging
from typing import Any
import requests
import csv

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

from . import DOMAIN
from . import CONFIG_OPTIONS, CONFIG_DISASTER_LEVEL, CONFIG_DISASTER_MSG
from .sensor import WeatherData

def _handle_node(dic: dict, *args) -> tuple[str | dict, str]:
    paths, names = args[:3], args[3:]
    p, n = dic, ""
    for i in range(l := len(paths)):
        if names:
            p.setdefault(paths[i], {
                "name": names[i],
                "c": {} if i < l - 1 else names[l]
            })
        p, n = p[paths[i]]["c"], p[paths[i]]["name"]
    return p, n

def _get_location_data() -> dict:
    dic = {}
    url = "https://raw.githubusercontent.com/qwd/LocationList/master/China-City-List-latest.csv"
    for row in csv.reader(requests.get(url).text.splitlines()):
        if not (province := row[6]) or province == 'Adm1_Name_EN':
            continue
        _handle_node(dic, province, row[8], row[1], row[7], row[9], row[2], row[0])
    return dic

def _get_dict_map(dic: dict, value="name") -> dict:
    return {
        k: v.get(value, "") 
        for k, v in dic.items() 
        if isinstance(v, dict)
    }

async def _check_api_key(hass, key) -> str:
    data = WeatherData(hass, "101010100", key, "allmsg", "1")
    try:
        await data.async_update()
    except PermissionError as e:
        return "api_key_error" 
    except ConnectionError as e:
        return "unknown_error" 
    return ""


class HeweatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1
    
    def __init__(self) -> None:
        super().__init__()
        self.__area_data = {}
        self._api_input = None
        self._city_input = None 
        self._district_input = None

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry):
        return HeweatherOptionsFlow(entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self.__area_data = await self.hass.async_add_executor_job(_get_location_data)
        return await self.async_step_api(user_input)

    async def async_step_api(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors = {}
        if user_input is None:
            user_input = {}
        if "province" in user_input and "api_key" in user_input:
            if not (err := await _check_api_key(self.hass, api_key := user_input["api_key"])):
                self._api_input = user_input
                _LOGGER.info(f'valid api key: {api_key}')
                return await self.async_step_city(user_input)
            errors["base"] = err
            _LOGGER.error(errors)
        data_schema = {
            vol.Required("api_key", default=user_input.get("api_key", vol.UNDEFINED)): str,
            vol.Required("options", default=user_input.get("options", vol.UNDEFINED)): cv.multi_select(CONFIG_OPTIONS),
            vol.Required("disasterlevel", default=user_input.get("disasterlevel", "3")): vol.In(CONFIG_DISASTER_LEVEL),
            vol.Required("disastermsg", default=user_input.get("disastermsg", "allmsg")): vol.In(CONFIG_DISASTER_MSG),
            vol.Required("province", default=user_input.get("province", vol.UNDEFINED)): vol.In(_get_dict_map(self.__area_data))
        }
        return self.async_show_form(
            step_id="api",
            data_schema=vol.Schema(data_schema),
            errors=errors
        )
    
    async def async_step_city(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            user_input = {}
        if "city" in user_input:
            self._city_input = user_input
            return await self.async_step_district(user_input)
        city_dic, province_name = _handle_node(self.__area_data, user_input["province"])
        data_schema = {
            vol.Required("city", default=user_input.get("city", vol.UNDEFINED)): vol.In(_get_dict_map(city_dic))
        }
        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "tip": province_name
            },
            errors={}
        )
    
    async def async_step_district(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            user_input = {}
        _, province_name = _handle_node(self.__area_data, province := self._api_input["province"])
        district_dic, city_name = _handle_node(self.__area_data, province, city := self._city_input["city"])
        if "district" in user_input:
            location, district_name = _handle_node(self.__area_data, province, city, district := user_input["district"])
            _LOGGER.info(f"Get location id: {location}, {province}-{city}-{district}")
            await self.async_set_unique_id(location)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{district}-{city}",
                data={
                    "location": location,
                    "name": f"{city_name}{district_name}",
                    "id": f"{district}_{city}".lower().replace(" ", "_").replace("'", "_"),
                    "key": self._api_input["api_key"],
                    "disasterlevel": self._api_input["disasterlevel"],
                    "disastermsg": self._api_input["disastermsg"],
                    "options": self._api_input["options"],
                    "location_name": f"{province_name}-{city_name}-{district_name}"
                },
            )
        data_schema = {
            vol.Required("district", default=user_input.get("district", vol.UNDEFINED)): vol.In(_get_dict_map(district_dic))
        }
        return self.async_show_form(
            step_id="district",
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "tip": f"{province_name}-{city_name}"
            },
            errors={}
        )


class HeweatherOptionsFlow(config_entries.OptionsFlow):

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_api(self.config_entry.data)

    async def async_step_api(self, user_input=None):
        errors = {}
        if user_input is None:
            user_input = {}
        if "api_key" in user_input:  # 已输入提交
            if not (err := await _check_api_key(self.hass, api_key := user_input["api_key"])):
                _LOGGER.info(f'valid api key: {api_key}, config update...')
                data = {
                    "location": self.config_entry.data["location"],
                    "name": self.config_entry.data["name"],
                    "id": self.config_entry.data["id"],
                    "key": api_key,
                    "disasterlevel": user_input["disasterlevel"],
                    "disastermsg": user_input["disastermsg"],
                    "options": user_input["options"],
                    "location_name": self.config_entry.data["location_name"]
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=data
                )
                return self.async_create_entry(
                    title=self.config_entry.title,
                    data=data,
                )
            # api key错误
            errors["base"] = err
            _LOGGER.error(errors)
            api_key = user_input.get("api_key", vol.UNDEFINED)
        else:  # 初始化
            api_key = self.config_entry.data.get("key", vol.UNDEFINED)
        data_schema = {
            vol.Required("api_key", default=api_key): str,
            vol.Required("options", default=user_input.get("options", vol.UNDEFINED)): cv.multi_select(CONFIG_OPTIONS),
            vol.Required("disasterlevel", default=user_input.get("disasterlevel", "3")): vol.In(CONFIG_DISASTER_LEVEL),
            vol.Required("disastermsg", default=user_input.get("disastermsg", "allmsg")): vol.In(CONFIG_DISASTER_MSG)
        }
        return self.async_show_form(
            step_id='api',
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "tip": self.config_entry.data["location_name"]
            },
            errors=errors,
        )