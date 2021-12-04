import sys
sys.path.append('/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/src/utils')
import parsutils as pu

tags_file = "/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/references/tags_list_OSM.txt"
cities_file = "/Users/ivanesipov/Desktop/Учеба/Курсовая_3/Coursework_3/references/cities_list_OSM.txt"
L0 = open(tags_file).readlines()
L1 = open(cities_file).readlines()
needed_tags, cities = [], []
for tag in L0:
    needed_tags.append(tag.replace('\n',''))
for city in L1:
    cities.append(city.replace('\n',''))

tags = pu.tags_to_dict(needed_tags)
errors = pu.parse_cities(cities,tags) # используем тэги и города из OSM для парсинга
pu.concat_cities(cities)