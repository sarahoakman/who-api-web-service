# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
#does this scraping and adding to database when in this folder, terminal command is : scrapy runspider who_scraper/spiders/reportbot.py
import scrapy, sqlite3, re, datetime,sys, logging, os

class WhoScraperPipeline(object):
    def __init__(self):
        current_dir = os.getcwd()
        database_path = current_dir + '\\who.db'
        self.connection = sqlite3.connect(database_path)
        self.cursor = self.connection.cursor()
        #log.msg("Established connection with database") is this log file??

    def process_item(self, item, spider):
        #print((item['reports'][0]['syndromes']))
        #remove spaces and - in publication_date
        pub = int(''.join(filter(str.isdigit, item['publication_date'])))
        #print(pub)
        self.cursor.execute("select * from article where url=?", (item['url'],))
        result = self.cursor.fetchone()
        if result: #already in database
            print("record already in database")
            #self.connection.close()
            return item
        else:
            self.cursor.execute(
                "insert into article (URL, Headline, Main_Text, Date_of_publication) values (?, ?, ?, ?)",
                    (item['url'], item['headline'], item['maintext'], pub))
            self.connection.commit()
            for reports in item['reports']:
                self.cursor.execute(
                    "insert into report (URL, Event_Date) values (?, ?)",
                    (item['url'], reports['event_date'])
                    )
                self.connection.commit()
                self.cursor.execute("select id from report order by id desc limit 1 ")
                result = self.cursor.fetchone()
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
                self.cursor.execute(
                    "insert into description (ReportID, Source, Cases, Deaths, Controls) values (?, ?, ?, ?, ?)",
                    (report_id, source, reports['cases'], reports['deaths'], controls)
                )
                self.connection.commit()

                self.cursor.execute(
                    "insert into disease (ReportID, Disease) values (?, ?)",
                    (report_id, reports['disease'])
                )
                self.connection.commit()

                if reports['timezone']:
                    self.cursor.execute(
                        "insert into timezone (ReportID, Timezone) values (?, ?)",
                        (report_id, reports['timezone'])
                    )
                    self.connection.commit()

                for location in reports['locations']:
                    self.cursor.execute(
                        "insert into location (ReportID, Location, Country) values (?, ?, ?)",
                        (report_id, location['location'], location['country'])
                    )
                    self.connection.commit()

                for search in reports['key_terms']:
                    self.cursor.execute(
                        "insert into searchterm (ReportID, SearchTerm) values (?, ?)",
                        (report_id, search)
                    )
                    self.connection.commit()

                if not reports['syndromes']:
                    syndromes = None
                else:
                    syndromes = reports['syndromes'][0]
                self.cursor.execute(
                    "insert into syndrome (ReportID, Symptom) values (?, ?)",
                    (report_id, syndromes)
                )
                self.connection.commit()
        #for each location : add(id, location, country)
        #for each search term: add(id,term)
        #add (id,symptom)
        #self.connection.close()
        return item
