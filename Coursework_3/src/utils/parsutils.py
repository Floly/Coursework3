import os
import geopandas as gpd
import pandas as pd
import numpy as np
import json
import h3
import folium
import osmnx as ox
from shapely import wkt
from folium.plugins import HeatMap
from shapely.geometry import Polygon
import seaborn as sns
from tqdm import tqdm
import time
import Utils_hexes as uh
from typing import List, Union, Tuple
# для загрузки файла тэгов с github
import requests
import io

# Ссылка на raw версию файла
url = "https://raw.githubusercontent.com/Floly/Coursework3/main/Coursework_3/data/raw/project_unique_tags.csv"

download = requests.get(url).content

def tags_to_dict(appropriate: list) -> list:
    '''
    :param appropriate: key tags, which considered to be used in parsing
    :return: list of dicts length(1)
    '''
    # прочитаем исходник и выберем нужные нам тэги
    tags_csv = pd.read_csv(io.StringIO(download.decode('utf-8')))
    tags_df = tags_csv[tags_csv.key.isin(appropriate)].iloc[:,:2].dropna()

    #Запишем исходный датафрейм в в список словарей
    tags = []
    for i in range(len(tags_df)):
        a = {}
        a[tags_df.iloc[i,0]] = tags_df.iloc[i,1]
        tags.append(a)

    return tags


def parse_cities(cities: list,
                 tags: list,
                 save_interim = True,
                 interim_output = 'interim_best.csv',
                 res_output = 'parsing_result.csv') -> 'DataFrame':
    '''
    :param cities: list of cities/territories from OSM
    :param tags: list of tags (recommended to use tags_to_dict function)
    :param save_interim: if you want to save interim result (default = True)
    :param interim_output: file for interim result (default = 'interim_reult.csv')
    :param res_output: name of csv file for interim result (default = 'parsing_result.csv')
    :return: dataframe with columns: city, object, type, geometry, lat, lon
    '''
    # список датафреймов - результатов запросов в OSM
    gdfs = []
    for city in tqdm(cities):
        for tag in tags:
            # иногда в OSM данные хранятся неправильно, игнорируем ошибки
            try:
                gdfs.append(uh.osm_query(tag, city))
            except KeyError:
                continue

        # условие на случай, если мы хотим сохранять промежуточный результат
        if save_interim == True:
            pd.DataFrame(gdfs).to_csv(interim_output)

    # объединим датафреймы из списка
    data_poi = pd.concat(gdfs)
    data_poi.groupby(['city','object','type'], as_index = False).agg({'geometry':'count'})

    # добавим координаты/центроиды для всех объектов
    lat, lon = uh.get_lat_lon(data_poi['geometry'])
    data_poi['lat'] = lat
    data_poi['lon'] = lon

    data_poi.to_csv(res_output)

    return data_poi
