# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy.item import Item, Field

class WhoScraperItem(Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    url = Field()
    headline = Field()
    publication_date = Field()
    maintext = Field()
    reports = Field()

class ReportsItem(Item):
    event_date = Field()
    disease = Field()
    controls = Field()
    syndromes = Field()
    source = Field()
    cases = Field()
    deaths = Field()
    key_terms = Field()
    locations = Field()
    timezone = Field()

class LocationsItem(Item):
    country = Field()
    location = Field()
