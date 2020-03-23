
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

def update_db(item):
    connection = sqlite3.connect('who.db')
    cursor = connection.cursor()
    pub = int(''.join(filter(str.isdigit, item['publication_date'])))
    cursor.execute("select * from article where url=?", (item['url'],))
    result = cursor.fetchone()
    if result: #already in database
        print("record already in database")
        connection.close()
        return item
    else:
        cursor.execute(
            "insert into article (URL, Headline, Main_Text, Date_of_publication) values (?, ?, ?, ?)",
                (item['url'], item['headline'], item['maintext'], pub))
        connection.commit()
        for reports in item['reports']:
            cursor.execute(
                "insert into report (URL, Event_Date) values (?, ?)",
                (item['url'], reports['event_date'])
                )
            connection.commit()
            cursor.execute("select id from report order by id desc limit 1 ")
            result = cursor.fetchone()
            report_id = result[0]
            #print(report_id)
            if not reports['source']: #if empty
                source = None
            else:
                source = reports['source']
            if not reports['controls']:
                controls = None
            else:
                controls = reports['controls']
            cursor.execute(
                "insert into description (ReportID, Source, Cases, Deaths, Controls) values (?, ?, ?, ?, ?)",
                (report_id, source, reports['cases'], reports['deaths'], controls)
            )
            connection.commit()

            cursor.execute(
                "insert into disease (ReportID, Disease) values (?, ?)",
                (report_id, reports['disease'])
            )
            connection.commit()

            if reports['timezone']:
                cursor.execute(
                    "insert into timezone (ReportID, Timezone) values (?, ?)",
                    (report_id, reports['timezone'])
                )
                connection.commit()

            for location in reports['locations']:
                cursor.execute(
                    "insert into location (ReportID, Location, Country) values (?, ?, ?)",
                    (report_id, location['location'], location['country'])
                )
                connection.commit()

            for search in reports['key_terms']:
                cursor.execute(
                    "insert into searchterm (ReportID, SearchTerm) values (?, ?)",
                    (report_id, search)
                )
                connection.commit()

            if not reports['syndromes']:
                syndromes = None
            else:
                syndromes = reports['syndromes'][0]
            cursor.execute(
                "insert into syndrome (ReportID, Symptom) values (?, ?)",
                (report_id, syndromes)
            )
            connection.commit()
    connection.close()
    return

# print the items
for item in items:
    update_db(item)
