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
import shutil
from shapely import wkt

import Utils_hexes as uh
from typing import List, Union, Tuple

tags_filename = '/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/data/raw/project_unique_tags.csv'

def tags_to_dict(appropriate: list) -> list:
    '''
    :param appropriate: key tags, which considered to be used in parsing
    :return: list of dicts length(1)
    '''
    # прочитаем исходник и выберем нужные нам тэги
    tags_csv = pd.read_csv(tags_filename)
    tags_df = tags_csv[tags_csv.key.isin(appropriate)].iloc[:,:2].dropna()

    #Запишем исходный датафрейм в в список словарей
    tags = []
    for i in range(len(tags_df)):
        a = {}
        a[tags_df.iloc[i,0]] = tags_df.iloc[i,1]
        tags.append(a)
    return tags

def parse_cities(cities: list,
                 tags: list) -> 'DataFrame':
    '''
    :params
    cities: list of cities/territories from OSM
    tags: list of tags (recommended to use tags_to_dict function)
    :return: dataframe with columns: city, object, type, geometry, lat, lon
    '''

    # перейдем в рабочую директорию
    data_raw = '/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/data/raw'
    os.chdir(data_raw)
    errors = [] # лог для ошибок
    for city in tqdm(cities):
      
        # создаем директорию для города и переходим в неё (перезаписываем папку, если такая уже существует)
        os.makedirs(city, exist_ok = True)
        os.chdir(city)
        
        for tag in tags:
            s_tag = str(tag).replace("': '", "_").replace('{', '').replace('}','').replace("'","") # string tag для записи в файлы
            try:
                gdf = uh.osm_query(tag, city)
                gdf.to_csv(city + '_' + s_tag + '.csv')
            # иногда в OSM данные хранятся неправильно, игнорируем ошибки и записываем их в errors
            except:
                errors.append(city + s_tag)
                continue
        # возвращаемся в исходную директорию
        os.chdir('..')
    
    return errors


def concat_cities(cities: list):
    '''
    Concatenates city-level tags dataframes and writes resulting city csv to finals directory
    :param cities:
    :return: 'ok'
    '''

    # создаем директорию finals в data/raw
    data_raw = '/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/data/raw'
    os.chdir(data_raw)
    os.makedirs('finals', exist_ok = True)

    for city in cities:
        os.chdir(city)      # переходим в директорию города
        city_tags = []      # список датафреймов по городу
        for f in os.listdir():
            # читаем файлы и вытаскиваем из них датафреймы
            if os.path.isfile(f) == True and f != '.DS_Store':  # .DS_Store и папки игнорируем
                df = pd.read_csv(f)
                df['geometry'] = gpd.GeoSeries.from_wkt(df['geometry'])
                gdf = gpd.GeoDataFrame(df, geometry= 'geometry')
                city_tags.append(gdf)

        data_poi = pd.concat(city_tags)
        data_poi.groupby(['city','object','type'], as_index = False).agg({'geometry':'count'})

        # добавим координаты/центроиды для всех объектов
        lat, lon = uh.get_lat_lon(data_poi['geometry'])
        data_poi['lat'] = lat
        data_poi['lon'] = lon

        # возвращаемся в директорию с файлами, удаляем папку (city-tags), переносим файл с городом в finals
        os.chdir('..')
        shutil.rmtree(city, ignore_errors=True)
        os.chdir('finals')
        data_poi.to_csv(city + '_final.csv')
        os.chdir('..')
        
    print('ok')
