from bs4 import BeautifulSoup
from urllib.request import urlopen
from scrapy.crawler import CrawlerProcess, CrawlerRunner
from who_scraper.spiders.reportbot import ReportbotSpider
from twisted.internet import reactor
from scrapy.utils.project import get_project_settings
import sqlite3
import os
import re

class UpdateBot:
    def find_current_year(self):
        c = urlopen('https://www.who.int/csr/don/archive/year/en/')
        contents = c.read()
        soup = BeautifulSoup(contents,'html.parser')
        date_links = soup.find_all('ul',{'class': 'list'})
        # get the first year as it's in descending order 
        date = date_links[0].find('li')
        a = date.find('a')
        return 'https://www.who.int' + a['href']

    def get_database_path(self):
        current_dir = os.getcwd()
        if ('scraper' in current_dir):
            index = current_dir.index('scraper')
            database_path = current_dir[:index] + '\\who.db'
        else:
            database_path = current_dir + '\\who.db'
        return database_path

    def get_new_reports(self):
        most_recent_year = self.find_current_year()
        c = urlopen(most_recent_year)
        contents = c.read()
        soup = BeautifulSoup(contents,'html.parser')
        actual_links = soup.find_all('ul',{'class':'auto_archive'})
        database_path = self.get_database_path()
        check = 0
        unscraped_links = []
        for a in actual_links[0].find_all('li'):
            for l in a.find_all('a'):
                link = 'https://www.who.int'+ l['href']
                with sqlite3.connect(database_path) as db:
                    cursor = db.cursor()
                    sql = '''select URL from Article WHERE URL=?'''
                    cursor.execute(sql, (link,))
                    if (len(cursor.fetchall()) == 0):
                        unscraped_links.append(link)
                    else: 
                        check = 1
                        break
            if (check == 1):
                break
        return unscraped_links

    def scrape_new_reports(self):
        unscraped_links = self.get_new_reports()
        print(unscraped_links)
        settings = get_project_settings()
        process = CrawlerProcess(settings)
        process.crawl(ReportbotSpider, start_urls=unscraped_links)
        process.start()

t = UpdateBot()
t.scrape_new_reports()