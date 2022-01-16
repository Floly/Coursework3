import os
import geopandas as gpd
import pandas as pd
import numpy as np
import json
import osmnx as ox
from collections import Counter
from tqdm import tqdm
import shutil
import sys

sys.path.append('/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/src/utils')
import Utils_hexes as uh


tags_filename = '/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/data/raw/project_unique_tags.csv'


def tags_to_dict(appropriate: list) -> list:
    """
    :param appropriate: key tags, which considered to be used in parsing
    :return: list of dicts length(1)
    """
    # прочитаем исходник и выберем нужные нам тэги
    tags_csv = pd.read_csv(tags_filename)
    tags_df = tags_csv[tags_csv.key.isin(appropriate)].iloc[:, :2].dropna()

    # Запишем исходный датафрейм в в список словарей
    tags = []
    for i in range(len(tags_df)):
        a = {}
        a[tags_df.iloc[i, 0]] = tags_df.iloc[i, 1]
        tags.append(a)
    return tags


def parse_cities(cities: list, tags: list) -> 'DataFrame':
    """
    :type cities: object
    :params
    cities: list of cities/territories from OSM
    tags: list of tags (recommended to use tags_to_dict function)
    :return: dataframe with columns: city, object, type, geometry, lat, lon
    """

    # перейдем в рабочую директорию
    data_raw = '/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/data/raw'
    os.chdir(data_raw)
    errors = []  # лог для ошибок
    for city in tqdm(cities):

        # создаем директорию для города и переходим в неё (перезаписываем папку, если такая уже существует)
        os.makedirs(city, exist_ok=True)
        os.chdir(city)

        for tag in tags:
            s_tag = str(tag).replace("': '", "_").replace('{', '').replace('}', '').replace("'",
                                                                                            "")  # string tag для записи в файлы
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
    """
    Concatenates city-level tags dataframes and writes resulting city csv to finals directory
    :param cities:
    :return: 'ok'
    """

    # создаем директорию finals в data/raw
    data_raw = '/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/data/raw'
    os.chdir(data_raw)
    os.makedirs('finals', exist_ok=True)

    for city in cities:
        os.chdir(city)  # переходим в директорию города
        city_tags = []  # список датафреймов по городу
        for f in os.listdir():
            # читаем файлы и вытаскиваем из них датафреймы
            if os.path.isfile(f) == True and f != '.DS_Store':  # .DS_Store и папки игнорируем
                df = pd.read_csv(f)
                df['geometry'] = gpd.GeoSeries.from_wkt(df['geometry'])
                gdf = gpd.GeoDataFrame(df, geometry='geometry')
                city_tags.append(gdf)

        data_poi = pd.concat(city_tags)
        data_poi.groupby(['city', 'object', 'type'], as_index=False).agg({'geometry': 'count'})

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


def split_multipolygons(cities: list):
    """
    Downloads cities shape and in case it has multipolygon shape splits it in simple polygons.
    Recommended before further processing.
    :param cities: list of cities (areas) you are interested in
    :return: GeoDataFrame that contains polygons
    """
    # скачиваем и удаляем ненужные столбцы
    raw_polygon_cities = ox.geocode_to_gdf(cities)
    raw_polygon_cities.drop(['bbox_east', 'bbox_west', 'bbox_north',
                             'bbox_south', 'lat', 'lon', 'osm_type',
                             'osm_id', 'place_id', 'importance'], axis=1, inplace=True)

    # создаем два списка: индекс мультиполигонов и список полигонов из мультиполигонов
    to_delete, new_polygons = [], []
    # проходимся по строкам столбца и ищем мультиполигоны
    for index, row in raw_polygon_cities.iterrows():
        if row.geometry.type == 'MultiPolygon':
            Polygons = list(row.geometry)
            to_delete.append(index)
            # если нашли мультиполигон - создаем новый ряд, в который кладем полигон
            # и копируем остальные столбцы из мультиполигона. Потом добавляем их в список new_polygons
            for poly in Polygons:
                new_poly_row = pd.Series(poly)
                new_poly_row = new_poly_row.append(raw_polygon_cities.iloc[index, 1:])
                new_polygons.append(new_poly_row)

    # объединяем элементы (ряды) списка и создаем геодатафрейм
    new_polygons = gpd.GeoDataFrame(new_polygons).rename(columns={0: 'geometry'})
    # присоединяем датафрейм new_polygons к исходному геодатафрейму и удаляем мультиполигоны (мы их уже разбили на полигоны)
    raw_polygon_cities = raw_polygon_cities.append(gpd.GeoDataFrame(new_polygons), ignore_index=True)
    raw_polygon_cities.drop(to_delete, axis=0, inplace=True)

    return raw_polygon_cities


def hexagons_from_cities(cities_polygons: 'DataFrame', hexagon_size=9):
    """
    Splits cities polygons Dataframe to hexagons of specified size
    :param cities_polygons: Dataframe of AOI polygons
    :param hexagon_size: set size of hexagon corresponding to https://h3geo.org/docs/core-library/restable/
    :return: dataframe of hexagons
    """

    h_s = gpd.GeoDataFrame()
    for index, row in tqdm(cities_polygons.iterrows()):
        geoJson = json.loads(gpd.GeoSeries(row['geometry']).to_json())
        geoJson = geoJson['features'][0]['geometry']
        geoJson = {'type': 'Polygon', 'coordinates': [np.column_stack((np.array(geoJson['coordinates'][0])[:, 1],
                                                                       np.array(geoJson['coordinates'][0])[:,
                                                                       0])).tolist()]}
        m, hexes, polylines = uh.create_hexagons(geoJson, hexagon_size)
        h_s = h_s.append(gpd.GeoDataFrame(hexes).rename(columns={0: 'geometry'}), ignore_index=True)

    return h_s


def concat_cities_objects(path):
    """
    Concatenates city tags and stores them as data/interim/final_concatenation.csv
    :param path: path to finals directory
    :return: 'ok'
    """

    os.chdir(path)

    city_tags = []  # список датафреймов по городу
    for f in tqdm(os.listdir()):
        # читаем файлы и вытаскиваем из них датафреймы
        if os.path.isfile(f) == True and f != '.DS_Store':  # .DS_Store и папки игнорируем
            df = pd.read_csv(f)
            df['geometry'] = gpd.GeoSeries.from_wkt(df['geometry'])
            gdf = gpd.GeoDataFrame(df, geometry='geometry')
            city_tags.append(gdf)

    data_poi = pd.concat(city_tags)
    data_poi.groupby(['city', 'object', 'type'], as_index=False).agg({'geometry': 'count'})

    os.chdir('/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/data/interim')
    data_poi.to_csv('final_concatenation.csv')
    print('process finished')


def count_objects(objects_df: 'DataFrame'):
    """
    :param objects_df: dataframe of objects assigned to polygons
    :return: dataframe of polygons with columns: hex_id, city, geometry,
    counter_dict - dictionary of object-type counter
    """

    hex_ids = objects_df['hex_index'].unique()
    new_df = gpd.GeoDataFrame(hex_ids)
    poly_lists, geometries, counters, cities = [], [], [], []

    for hid in tqdm(hex_ids):
        ob_ty = []
        temp_df = gpd.GeoDataFrame(objects_df[objects_df.hex_index == hid])
        geometries.append(objects_df[objects_df.hex_index == hid].iloc[0, 1])
        cities.append(objects_df[objects_df.hex_index == hid].iloc[0, 2])
        for i, row in temp_df.iterrows():
            ob_ty.append(str(row.object) + '_' + str(row.type))

        counters.append(Counter(ob_ty))

    new_df['city'] = pd.Series(cities)
    new_df['geometry'] = pd.Series(geometries)
    new_df['counter_dict'] = pd.Series(counters)
    new_df.rename(columns={'0': 'hexagon_id'}, inplace=True)
    new_df.drop('Unnamed: 0', axis=1, inplace=True)
    return new_df
