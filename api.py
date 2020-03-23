import flask
from flask import request, jsonify,send_from_directory, make_response, Flask,  Blueprint
import sqlite3
import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property
from flask_swagger_ui import get_swaggerui_blueprint
from flask_restplus import Api, Resource, fields,marshal
from flask_restful import reqparse
from datetime import datetime
import re
import json
import enum

from time import process_time
from Logfile.logfile import LogFile
from flask import request

log = LogFile()

app = Flask(__name__)
authentication_code = "1810051939"
app.config.SWAGGER_UI_OAUTH_APP_NAME = 'WHO REST Api - Teletubbies'
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
api = Api(app,title=app.config.SWAGGER_UI_OAUTH_APP_NAME,description="This API can be used to access news articles from the WHO website. The WHO news articles have been scraped and separated into disease reports in the hopes of detecting epidemics by collecting global disease data. Disease reports can be accessed using GET requests whilst the POST, PUT and DELETE request can be accessed by authorised users which manipulates the scraped data stored within an SQL database.")
parser = reqparse.RequestParser()

api = api.namespace('article', description = 'WHO Disease Article and Report Operations')


locations = api.model('Locations', {
    "country": fields.String,
    "location": fields.String
})

description = api.model('Description', {
    "source": fields.String,
    "cases": fields.Integer,
    "deaths":fields.Integer,
    "controls":fields.String
})

reports = api.model('Report', {
    "event_date": fields.String,
    "locations": fields.List(fields.Nested(locations)),
    "diseases": fields.List(fields.String),
    "syndromes": fields.List(fields.String),
    "description": fields.List(fields.Nested(description))
})

updated_reports = api.model('UpdatedReport', {
    "url": fields.Url,
    "reports": fields.List(fields.Nested(reports))
})

articles = api.model('Article', {
    "url": fields.Url,
    "date_of_publication": fields.String,
    "headline": fields.String,
    "main_text": fields.String,
    "reports": fields.List(fields.Nested(reports))
})

parser1 = api.parser()
parser1.add_argument('start_date', help='Start date for the articles. Use format YYYY-MM-DDTHH:MM:SS. Eg:2001-01-01T00:00:00', location='args',required=True)
parser1.add_argument('end_date', help='End date for the articles. Use format YYYY-MM-DDTHH:MM:SS Eg:2019-12-31T11:59:59', location='args',required=True)
parser1.add_argument('timezone', type=str, default='AEDT',
                                choices=('ADT', 'AEDT', 'AEST', 'AET', 'MEST', 'UTC', 'WAST', 'WAT', 'WEST', 'WGT', 'WST'),
                                help='Timezone to filter Who news articles by')
#DELETE
parser2 = api.parser()
parser2.add_argument('id', help='Authorisation id to delete an existing article (only available to authorised users)', location='args', required=True)
parser2.add_argument('url', help='Url to the Who news article to be deleted. Url must exist in the database', location='args', required=True)

#POST
parser3 = api.parser()
parser3.add_argument('id', help='Authorisation id to post an article (only available to authorised users) (string)', location='args', required=True)

#PUT
parser4 = api.parser()
parser4.add_argument('id', help='Authorisation id to put a disease report into an existing article (only available to authorised users)', location='args', required=True)

class Article(Resource):
    @api.response(200, 'Success',[articles])
    @api.response(404, 'No data found')
    @api.doc(params={'key_terms': 'The key terms to look for when finding article. Separate multiple key terms by comma. Eg:ebola,virus'})
    @api.doc(params={'location': 'The location or country where the epidemic takes place. Eg: Guinea'})
    @api.response(400, 'Invalid date format')
    @api.doc(summary='Get request gets all the articles given the parameters')
    @api.expect(parser1,validate=False)
    def get(self):
        # log file
        now = datetime.now()
        accessed_time = now.strftime('%A, %d %B %Y %H:%M:%S AEDT')
        start_time = process_time()

        args = parser1.parse_args()
        start_date = args['start_date']
        end_date = args['end_date']
        # check start and end date format
        if not re.match(r"^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$", start_date):
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Invalid date input", '400', 'False', 'False')
            return {
                'message' : 'Invalid date input',
                'status' : 400
            },400
        if not re.match(r"^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$", end_date):
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Invalid date input", '400', 'False', 'False')
            return {
                'message' : 'Invalid date input',
                'status' : 400
            },400
        location = request.args.get('location')
        if not location:
            location = ""
        elif ',' in location:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Invalid number of locations given", '400', 'False', 'False')
            return {
                'message' : 'Invalid number of locations given',
                'status' : 400
            },400
        key_terms = request.args.get('key_terms')
        if not key_terms:
            key_terms = ""
        final_start,final_end = self.convert_date_to_int(start_date,end_date)
        if final_end < final_start:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "End date must be larger than start date", '400', 'False', 'False')
            return {
                'message' : 'End date must be larger than start date',
                'status' : 400
            },400
        articles = self.check_data_exists(final_start,final_end,location,key_terms)
        if articles == False:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "No data found", '404', 'True', 'False')
            return {
                'message' : 'No data found',
                'status' : 404
            },404
        result = self.get_results(articles)
        log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Success', '200', 'True', 'False')
        return {
            'result' : result,
            'status' : 200
        },200


    @api.response(400, 'Invalid data given')
    @api.response(403, 'Url already exists')
    @api.response(401, 'Unauthorised id')
    @api.response(200, 'Success')
    @api.expect(articles,parser3,validate=True)
    def post(self):
        # log file
        now = datetime.now()
        accessed_time = now.strftime('%A, %d %B %Y %H:%M:%S AEDT')
        start_time = process_time()
        
        args = {}
        a = parser3.parse_args()
        # return 401 if authorization code is wrong
        if 'id' not in a:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Unable to access authorised data', '400', 'False', 'False')
            return {
                'message' : 'Unable to access authorised data',
                'status' : 400
            },400
        if a['id'] != authentication_code:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Invalid authentication id', '401', 'False', 'False')
            return {
                'message' : 'Invalid authentication id',
                'status' : 401
            },401
        args['id'] = a['id']
        # return 400 if url or date of publication is empty
        if 'url' not in request.json or 'date_of_publication' not in request.json:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Missing required url field & date of publication in body', '400', 'False', 'False')
            return {
                'message' : 'Missing required url field & date of publication in body',
                'status' : 400
            },400

        args['url'] = request.json['url']
        args['date_of_publication'] = request.json['date_of_publication']
        args['headline'] = request.json['headline']
        args['main_text'] = request.json['main_text']
        args['event_date'] = request.json['reports'][0].get("event_date")
        args['country'] = request.json['reports'][0].get("locations")[0].get('country')
        args['location'] = request.json['reports'][0].get("locations")[0].get('location')
        args['disease'] = request.json['reports'][0].get("diseases")[0]
        args['syndrome'] = request.json['reports'][0].get("syndromes")[0]
        args['source'] = request.json['reports'][0].get("description")[0].get('source')
        args['cases'] = request.json['reports'][0].get("description")[0].get('cases')
        args['deaths'] = request.json['reports'][0].get("description")[0].get('deaths')
        args['controls'] = request.json['reports'][0].get("description")[0].get('controls')
        if args['event_date'] and not self.check_match_date_range(args['event_date']):
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Invalid date input", '400', 'False', 'False')
            return {
                'message' : "Invalid date input",
                'status' : 400
            },400
        # if url or publication date is empty
        if args['url'] == "" or args['date_of_publication'] == "":
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Missing required url field & date of publication in body', '400', 'False', 'False')
            return {
                'message' : 'Missing required url field & date of publication in body',
                'status' : 400
            },400

        # check if url exist already
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        # only date given
        query = 'SELECT * from Article where url = \'' + args['url'] + '\';'
        results = cur.execute(query).fetchall()
        if len(results) > 0:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Url already exists', '403', 'True', 'False')
            return {
                'message' : 'Url already exists',
                'status' : 403
            },403
        cur.close()
        # insert data into db
        conn = sqlite3.connect('who.db')
        with conn:
            # insert article
            sql = ''' INSERT INTO Article(url,headline,date_of_publication,main_text) VALUES(?,?,?,?) '''
            val = (args['url'], args['date_of_publication'],args['date_of_publication'],args['main_text']);
            cur2 = conn.cursor()
            cur2.execute(sql, val)
            # insert report
            sql = ''' INSERT INTO Report (url,event_date) VALUES(?,?) '''
            val = (args['url'], args['event_date']);
            cur = conn.cursor()
            cur.execute(sql, val)
            # insert disease
            if args['disease']:
                sql = ''' INSERT INTO Disease(Disease,ReportID) VALUES(?,?) '''
                val = (args['disease'], cur.lastrowid);
                cur3 = conn.cursor()
                cur3.execute(sql, val)
                sql = ''' INSERT INTO SearchTerm(SearchTerm,ReportID) VALUES(?,?) '''
                val = (args['disease'], cur.lastrowid);
                cur3 = conn.cursor()
                cur3.execute(sql, val)
            # insert Country/location
            if args['country'] or args['location']:
                sql = ''' INSERT INTO Location(Location,Country,ReportID) VALUES(?,?,?) '''
                val = (args['location'],args['country'],cur.lastrowid);
                cur4 = conn.cursor()
                cur4.execute(sql, val)
            # insert syndrome
            if args['syndrome']:
                sql = ''' INSERT INTO Syndrome(Symptom,ReportID) VALUES(?,?) '''
                val = (args['syndrome'], cur.lastrowid);
                cur5 = conn.cursor()
                cur5.execute(sql, val)
            if args['cases'] or args['deaths'] or args['controls'] or args['source']:
                sql = ''' INSERT INTO Description(Source,Cases,Deaths,Controls,ReportID) VALUES(?,?,?,?,?) '''
                val = (args['source'],args['cases'],args['deaths'],args['controls'], cur.lastrowid);
                cur5 = conn.cursor()
                cur5.execute(sql, val)
        log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Article successfully added', '200', 'True', 'True')
        return {
            'message': 'Article successfully added ',
            'status' : 200
        },200


    @api.response(403, 'Url does not exist')
    @api.response(401, 'Unauthorised id')
    @api.response(200, 'Success')
    @api.response(500, 'Url was not deleted')
    @api.expect(parser2,validate=False)
    def delete(self):
        # log file
        now = datetime.now()
        accessed_time = now.strftime('%A, %d %B %Y %H:%M:%S AEDT')
        start_time = process_time()

        args = parser2.parse_args()
        au_key = args['id']
        url = args['url']
        if authentication_code == au_key:
            article = self.check_url_exists(url)
            print(article)
            if article == False:
                log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Url does not exist', '403', 'True', 'False')
                return {
                'message': 'Url does not exist',
                'status' : 403
                },403
            result = self.delete_result(url)
            if result == False:
                log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Could not delete url', '500', 'True', 'False')
                return {
                'message': 'Could not delete url',
                'status' : 500
                },500
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Article and linked reports successfully deleted', '200', 'True', 'True')
            return {
            'message': 'Article and linked reports successfully deleted ',
            'status' : 200
            },200
        else:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Incorrect Authorization Key', '401', 'False', 'False')
            return {
            'message': 'Incorrect Authorization Key',
            'status' : 401
            },401


    # adds a report to an article
    @api.response(401, 'Unauthorised id')
    @api.response(400, 'Url cannot be empty')
    @api.response(200, 'Success')
    @api.response(403, 'Url does not exist')
    @api.expect(parser4,updated_reports,validate=False)
    def put(self):
        # log file
        now = datetime.now()
        accessed_time = now.strftime('%A, %d %B %Y %H:%M:%S AEDT')
        start_time = process_time()

        args = {}
        a = parser4.parse_args()
        args['id'] = a['id']
        args['event_date'] = request.json['reports'][0].get("event_date")
        args['country'] = request.json['reports'][0].get("locations")[0].get('country')
        args['location'] = request.json['reports'][0].get("locations")[0].get('location')
        args['disease'] = request.json['reports'][0].get("diseases")[0]
        args['syndrome'] = request.json['reports'][0].get("syndromes")[0]
        args['source'] = request.json['reports'][0].get("description")[0].get('source')
        args['cases'] = request.json['reports'][0].get("description")[0].get('cases')
        args['deaths'] = request.json['reports'][0].get("description")[0].get('deaths')
        args['controls'] = request.json['reports'][0].get("description")[0].get('controls')


        # return 401 if authorization code is wrong
        if authentication_code != args['id']:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, 'Incorrect Authorization Key', '401', 'False', 'False')
            return {
                'message' : "Incorrect Authorization Key",
                'status' : 401
            },401
        # return 400 if url is empty
        if 'url' not in request.json or request.json['url'] == "":
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Url can't be empty", '400', 'False', 'False')
            return {
                'message' : "Url can't be empty",
                'status' : 400
            },400
        url = request.json['url']
        article = self.check_url_exists(url)
        if article == False:
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Url does not exist", '403', 'True', 'False')
            return {
                'message' : "Url does not exist",
                'status' : 403
            },403
        if args['event_date'] and not self.check_match_date_range(args['event_date']):
            log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Invalid date input", '400', 'False', 'False')
            return {
                'message' : "Invalid date input",
                'status' : 400
            },400
        self.add_report(url, args['event_date'], args['country'], args['location'], args['disease'], args['syndrome'], args['source'], args['cases'], args['deaths'], args['controls'])
        log.make_log_entry(accessed_time, start_time, process_time(), request.method, request.url, args, "Url Successfully added", '200', 'True', 'True')
        return {
            'message' : "Url Successfully added",
            'status' : 200
        },200

    # check if the input match for the date or date range
    def check_match_date_range(self, input):
        return re.match(r"^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$", input) or re.match(r"^[0-9]{4}\-[0-9]{2}\-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} to [0-9]{4}\-[0-9]{2}\-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$", input)


    # put new report to article
    def add_report(self, url, event_date, country, location, disease, syndrome, source, case, death, control):
        conn = sqlite3.connect('who.db')
        with conn:
            # insert report
            sql = ''' INSERT INTO Report (url,event_date) VALUES(?,?) '''
            val = (url, event_date);
            cur = conn.cursor()
            cur.execute(sql, val)
            # insert disease
            if disease:
                sql = ''' INSERT INTO Disease(Disease,ReportID) VALUES(?,?) '''
                val = (disease, cur.lastrowid);
                cur3 = conn.cursor()
                cur3.execute(sql, val)
            # insert Country/location
            if country or location:
                sql = ''' INSERT INTO Location(Location,Country,ReportID) VALUES(?,?,?) '''
                val = (location,country,cur.lastrowid);
                cur4 = conn.cursor()
                cur4.execute(sql, val)
            # insert syndrome
            if syndrome:
                sql = ''' INSERT INTO Syndrome(Symptom,ReportID) VALUES(?,?) '''
                val = (syndrome, cur.lastrowid);
                cur5 = conn.cursor()
                cur5.execute(sql, val)
            if case or death or control or source:
                sql = ''' INSERT INTO Description(Source,Cases,Deaths,Controls,ReportID) VALUES(?,?,?,?,?) '''
                val = (source,case,death,control, cur.lastrowid);
                cur5 = conn.cursor()
                cur5.execute(sql, val)

    # check if any data exists for the url
    def check_url_exists(self,url):
        conn = sqlite3.connect('who.db')
        cur = conn.cursor()
        query = 'SELECT url from Article WHERE url = \'' + url + '\';'
        result = cur.execute(query).fetchall()
        conn.close()
        if len(result) == 0:
            return False
        return result


    def delete_result(self,url):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        query1 = 'SELECT id from Report WHERE url = \'' + url + '\';'
        cur.execute(query1)
        ids = cur.fetchall()
        for value in ids:
            id = value['id']
            q1 = 'DELETE from Disease WHERE ReportID = ' + str(id) + ';'
            cur.execute(q1)
            conn.commit()
            q2 = 'DELETE from Description WHERE ReportID = ' + str(id) + ';'
            cur.execute(q2)
            conn.commit()
            q3 = 'DELETE from Location WHERE ReportID = ' + str(id) + ';'
            cur.execute(q3)
            conn.commit()
            q4 = 'DELETE from Syndrome WHERE ReportID = ' + str(id) + ';'
            cur.execute(q4)
            conn.commit()
            q5 = 'DELETE from SearchTerm WHERE ReportID = ' + str(id) + ';'
            cur.execute(q5)
            conn.commit()

        query2 = 'DELETE from Report WHERE url = \'' + url + '\';'
        cur.execute(query2)
        conn.commit()
        query3 = 'DELETE from Article WHERE url = \'' + url + '\';'
        cur.execute(query3)
        conn.commit()
        query4 = 'SELECT url from Article WHERE url = \'' + url + '\';'
        cur.execute(query4)
        records = cur.fetchall()
        conn.close()
        if len(records) != 0:
            return False
        return True


    # check if any data exists for the query
    def check_data_exists(self,start_date,end_date,location,key_terms):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        # only date given
        query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ';'
        # key terms and location given
        if location != '' and key_terms != '':
            if ',' in key_terms:
                k = key_terms.split(',')
                i = 1
                query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id JOIN SearchTerm s on s.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location.title() + '\'  and s.SearchTerm = \'' + k[0].lower() + '\' '
                query = query + ' UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN SearchTerm s on s.ReportID = r.id JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and s.SearchTerm = \'' + k[0].lower() + '\'and l.country = \'' + location.title() + '\' '
                while i < len(k):
                    query = query + ' UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id JOIN SearchTerm s on s.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location.title() + '\'  and s.SearchTerm = \'' + k[i].lower() + '\' '
                    query = query + ' UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN SearchTerm s on s.ReportID = r.id JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and s.SearchTerm = \'' + k[i].lower() + '\'and l.country = \'' + location.title() + '\' '
                    i+=1
                query = query + ';'
            else:
                query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN SearchTerm s on s.ReportID = r.id JOIN Location l on l.ReportID = r.id JOIN Disease d on d.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location.title() + '\'  and d.Disease = \'' + key_terms.lower() + '\' '
                query = query + ' UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN SearchTerm s on s.ReportID = r.id JOIN Disease d on d.ReportID = r.id JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and s.SearchTerm = \'' + key_terms.lower() + '\'and l.country = \'' + location.title() + '\';'
        #location only
        elif location != '':
            query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location.title() + '\' '
            query = query + 'UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.country = \''   + location.title() + '\';'
        # key terms only
        elif key_terms != '':
            if ',' in key_terms:
                k = key_terms.split(',')
                i = 1
                query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN SearchTerm s on s.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and s.SearchTerm = \'' + k[0].lower() + '\' '
                while i < len(k):
                    query = query + ' UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN SearchTerm s on s.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and s.SearchTerm = \'' + k[i].lower() + '\' '
                    i+=1
                query = query + ';'
            else:
                query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url JOIN SearchTerm s on s.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and s.SearchTerm = \'' + key_terms.lower() + '\';'
        results = cur.execute(query).fetchall()
        # filter if duplicate reports
        id_list = []
        filtered_location = []
        for r in results:
            if r['id'] not in id_list:
                id_list.append(r['id'])
                filtered_location.append(r)
        results = filtered_location
        articles = {}
        if len(results) == 0:
            return False
        for r in results:
            if r['url'] in articles:
                u = r['url']
                articles[u].append(r['id'])
            else:
                arr = []
                arr.append(r['id'])
                u = r['url']
                articles[u] = arr
        return articles

    # compile the results into correct format
    def get_results(self,articles):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        res = []
        for key in articles:
            query = 'SELECT a.url,a.date_of_publication,a.headline,a.main_text from Article a WHERE a.url = \'' + key + '\';'
            data = cur.execute(query).fetchall()
            data[0]['reports'] = []
            # change publication date format
            date = str(data[0]['date_of_publication'])
            data[0]['date_of_publication'] = date[0:4] + '-' + date[4:6] + '-' + date[6:8] + ' ' + date[8:10] + ':' + date[10:12] + ':' + date[12:14]
            for id in articles[key]:
                query = 'SELECT * from Report r left join Description ds on ds.ReportID = r.id left join Syndrome s on s.ReportID = r.id left join Location l on l.ReportID = r.id left join Disease d on d.ReportID = r.id where r.id =' + str(id) + ';'
                report = cur.execute(query).fetchall()
                b = {}
                if len(report) > 0:
                    b['event_date'] = report[0]['event_date']
                # get list of locations, diseases and syndromes
                b['locations'] = []
                b['diseases'] = []
                b['syndromes'] = []
                b['description'] = []
                for l in report:
                    if l['Country'] or l['Location']:
                        places = {}
                        if not l['Country']:
                            l['Country'] = ""
                        if not l['Location']:
                            l['Location']= ""
                        places['country'] = l['Country']
                        places['location'] = l['Location']
                        if places not in b['locations']:
                            b['locations'].append(places)
                    else:
                        b['locations'] = ""
                    if l['Disease'] :
                        if l['Disease'] not in b['diseases']:
                            b['diseases'].append(l['Disease'])
                    else:
                        b['diseases'] = ""
                    if l['Symptom'] :
                        if l['Symptom'] not in b['syndromes']:
                            b['syndromes'].append(l['Symptom'])
                    else:
                        b['syndromes'] = ""
                    if l['Source'] or l['Cases'] or l['Deaths'] or l['Controls'] :
                        desc = {}
                        if not l['Source']:
                            l['Source'] = ""
                        if not l['Cases']:
                            l['Cases']= ""
                        if not l['Deaths']:
                            l['Deaths']= ""
                        if not l['Controls']:
                            l['Controls']= ""
                        desc['Source'] = l['Source']
                        desc['Cases'] = l['Cases']
                        desc['Deaths'] = l['Deaths']
                        desc['Controls'] = l['Controls']
                        if desc not in b['description']:
                            b['description'].append(desc)
                data[0]['reports'].append(b)
            res.append(data[0])
        return res

    def convert_date_to_int(self,start_date,end_date):
        start_day,start_time = start_date.split('T')
        end_day,end_time = end_date.split('T')
        sd = start_day.replace("-","")
        ed = end_day.replace("-","")
        st = start_time.replace(":","")
        et = end_time.replace(":","")
        final_start = sd + st
        final_end = ed + et
        return final_start,final_end

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static',path)


@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

api.add_resource(Article, "")
if __name__ == "__main__":
    app.run(debug=True)