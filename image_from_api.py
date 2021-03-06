import json
import requests
import os
from dataclasses import dataclass
from pprint import pprint
from datetime import datetime, timedelta
from collections import Counter
import numpy as np
import fire
import textwrap
from geopy import geocoders
from PIL import Image, ImageFont, ImageDraw


def _get_lon_lat_from_loc_str(loc, gn):
    ret = gn.geocode(loc)
    return ret.longitude, ret.latitude


@dataclass
class DailyWeather:
    min_temp_f: float
    max_temp_f: float
    weather_description: str
    weather_image: Image


@dataclass
class CurrentWeather:
    temp_f: float
    # feels_like_temp_f: float
    update_time_utc: float
    weather_description: str
    wind_speed: float
    weather_image: Image


def _construct_openweather_api(lon, lat, token):
    return f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&appid={token}&exclude=minutely,hourly"


def _get_current_weather_from_ret(current):
    # pprint(current)
    if len(current["weather"]) > 1:
        pprint(current["weather"])

    return CurrentWeather(
        temp_f=_k_to_f(current["temp"]),
        # feels_like_temp_f = _k_to_f(current['feels_like']),
        update_time_utc=current["dt"],
        wind_speed=current["wind_speed"],
        weather_description=current["weather"][0]["description"],
        weather_image=_load_icon(current["weather"][0]["icon"]),
    )


def get_daily_weather_from_ret(day):
    # pprint(day)
    if len(day["weather"]) > 1:
        pprint(day["weather"])
    return DailyWeather(
        min_temp_f=_k_to_f(day["temp"]["min"]),
        max_temp_f=_k_to_f(day["temp"]["max"]),
        weather_description=day["weather"][0]["description"],
        weather_image=_load_icon(day["weather"][0]["icon"]),
    )


def _k_to_f(k):
    return int((k - 273.15) * 9 / 5 + 32 + 0.5)


def _abspath(path):
    d = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(d, path)


def _load_icon(icon_name):
    icon_name = (icon_name + "_lg.png").replace("d_lg.png", "n_lg.png")
    # path =
    # im = Image.open(path)
    # print(Counter([x for x in np.array(im).flatten()]))
    # print(np.array(im).shape)
    return Image.open(_abspath(os.path.join("icons", icon_name)))


def _daily_image(day, dt):
    out = Image.new("RGBA", (100, 130), (255, 255, 255, 0))
    out.paste(day.weather_image, (0, 10))
    d = ImageDraw.Draw(out)
    # sml_fnt = ImageFont.truetype("/Users/MichaelMason/Downloads/Roboto_Mono/RobotoMono-VariableFont_wght.ttf", 20)
    sml_fnt = ImageFont.truetype(_abspath("fonts/current.ttf"), 20)
    s = f"{day.max_temp_f}°/{day.min_temp_f}°"
    (width, _) = d.multiline_textsize(s, font=sml_fnt)
    d.multiline_text(
        ((out.width - width - 1) // 2, 95), s, font=sml_fnt, fill=(0, 0, 0)
    )

    s = dt.strftime("%a")
    (width, _) = d.multiline_textsize(s, font=sml_fnt)
    d.multiline_text(
        ((out.width - width - 1) // 2, 10), s, font=sml_fnt, fill=(0, 0, 0)
    )

    return out


def _construct_image(place_name, time_offset, current, three_day):
    out = Image.new("RGBA", (300, 400), (255, 255, 255, 0))
    # load fonts
    big_fnt = ImageFont.truetype(_abspath("fonts/current.ttf"), 40)
    vbig_fnt = ImageFont.truetype(_abspath("fonts/current.ttf"), 60)
    sml_fnt = ImageFont.truetype(_abspath("fonts/current.ttf"), 25)
    # add 150x150 current weather image
    out.paste(current.weather_image.resize((150, 150), Image.LANCZOS), (10, 110))
    # Add current date
    d = ImageDraw.Draw(out)
    d.multiline_text((10, 30), place_name, font=big_fnt, fill=(0, 0, 0))
    dt = (
        current.update_time_utc
        // (60 * 5)
        * (60 * 5)  # round to last 5 minutes
        + time_offset # adjust for time offset
    )
    dt = datetime.fromtimestamp(dt)
    d.multiline_text((10, 70), dt.strftime("%A %I:%M %p"), font=sml_fnt, fill=(0, 0, 0))
    # add weather description
    d.multiline_text(
        (10, 95), current.weather_description, font=sml_fnt, fill=(0, 0, 0)
    )
    # add current temperature
    temp_str = f"{int(current.temp_f+.5)}°"
    (width, _) = d.multiline_textsize(temp_str, font=vbig_fnt)
    x = 140+(160-width)//2
    d.multiline_text((x, 145), temp_str, font=vbig_fnt, fill=(0, 0, 0))

    # add current day + 2 day forcase summaries
    out.paste(_daily_image(three_day[0], dt + timedelta(days=0)), (0, 250))
    out.paste(_daily_image(three_day[1], dt + timedelta(days=1)), (100, 250))
    out.paste(_daily_image(three_day[2], dt + timedelta(days=2)), (200, 250))

    return out


def debug_main():
    lat, lon = 39.5186, -104.76136
    with open("sample_return.json") as sr:
        r = json.load(sr)
    current = _get_current_weather_from_ret(r["current"])
    three_day = list(map(get_daily_weather_from_ret, r["daily"][:3]))
    im = _construct_image("Parker, CO", r["timezone_offset"], current, three_day)
    im.show()


def main(place_name, output_file):
    ## Get weather info
    # find location from place name
    gn = geocoders.GeoNames(os.environ["GEONAMES_USER"])
    lon, lat = _get_lon_lat_from_loc_str(place_name, gn)
    # request current and forecasted weather for that location
    r = _construct_openweather_api(lon, lat, os.environ["OPENWEATHER_TOKEN"])
    r = requests.get(r).json()
    # parse out relevant weather data
    current = _get_current_weather_from_ret(r["current"])
    three_day = list(map(get_daily_weather_from_ret, r["daily"][:3]))
    ## Construct image to display
    im = np.array(_construct_image(place_name, r["timezone_offset"], current, three_day))
    ## Output black and white image
    alpha = im[:,:,3]
    im = im[:,:,:3]
    im[alpha == 0] = 255
    im = Image.fromarray(im)
    pal_im = Image.new("P", (1, 1))
    pal_im.putpalette((255, 255, 255, 0, 0, 0) + (0, 0, 0) * 253)
    im = im.quantize(palette=pal_im)
    im.save(output_file)


if __name__ == "__main__":
    fire.Fire()
