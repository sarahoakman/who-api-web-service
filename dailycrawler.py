
#!/usr/bin/python3

# Scrapy API imports
import scrapy
from scrapy.crawler import CrawlerProcess
import sqlite3

# your spider
from who_scraper.spiders.reportbot import ReportbotSpider

# list to collect all items
items = []

# pipeline to fill the items list
class ItemCollectorPipeline(object):
    def __init__(self):
        self.ids_seen = set()

    def process_item(self, item, spider):
        items.append(item)

# create a crawler process with the specified settings
process = CrawlerProcess({
    'USER_AGENT': 'scrapy',
    'LOG_LEVEL': 'INFO',
    'ITEM_PIPELINES': { '__main__.ItemCollectorPipeline': 100 }
})

# start the spider
process.crawl(ReportbotSpider, start_urls=['https://www.who.int/csr/don/19-March-2020-ebola-drc/en/'])
process.start()

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def update_db(item):
    conn = sqlite3.connect('who.db')
    conn.row_factory = dict_factory
    cur = conn.cursor()
    # only date given
    result = cur.execute("SELECT * from Article where url=?", (item['url'],))
    results = result.fetchall()
    if len(results) > 0:
        return
    cur.close()
    # insert data into db
    conn = sqlite3.connect('who.db')
    with conn:
        # insert article
        sql = ''' INSERT INTO Article(url,headline,date_of_publication,main_text) VALUES(?,?,?,?) '''
        val = (item['url'], item['headline'],item['publication_date'],item['maintext']);
        cur2 = conn.cursor()
        cur2.execute(sql, val)
        # insert report
        #sql = ''' INSERT INTO Report (url,event_date) VALUES(?,?) '''
        #val = (item['url'], item['event_date']);
        #cur = conn.cursor()
        #cur.execute(sql, val)

# print the items
for item in items:
    print(item)
    update_db(item)
