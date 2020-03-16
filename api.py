import flask
from flask import request, jsonify,send_from_directory, make_response, Flask,  Blueprint
import sqlite3
import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property
from flask_swagger_ui import get_swaggerui_blueprint
from flask_restplus import Api, Resource, fields,marshal
import datetime
import re
import json


app = Flask(__name__)

app.config.SWAGGER_UI_OAUTH_APP_NAME = 'WHO REST Api - Teletubbies'
app.config.SWAGGER_UI_DOC_EXPANSION = 'list'
api = Api(app,title=app.config.SWAGGER_UI_OAUTH_APP_NAME,description="This API can be used to access news articles from the WHO website. The WHO news articles have been scraped and separated into disease reports in the hopes of detecting epidemics by collecting global disease data. Disease reports can be accessed using GET requests whilst the POST, PUT and DELETE request can be accessed by authorised users which manipulates the scraped data stored within an SQL database.")

#api = Api(app,default='article',default_label='WHO Disease Article Operations',title=app.config.SWAGGER_UI_OAUTH_APP_NAME,description="This API can be used to access news articles from the WHO website. The WHO news articles have been scraped and separated into disease reports in the hopes of detecting epidemics by collecting global disease data. Disease reports can be accessed using GET requests whilst the POST, PUT and DELETE request can be accessed by authorised users which manipulates the scraped data stored within an SQL database.")


api = api.namespace('article', description = 'WHO Disease Article and Report Operations')


locations = api.model('Locations', {
    "country": fields.String,
    "location": fields.String
})

reports = api.model('Report', {
    "event_date": fields.DateTime,
    "locations": fields.List(fields.Nested(locations)),
    "diseases": fields.List(fields.String),
    "syndromes": fields.List(fields.String)
})


articles = api.model('Article', {
    "url": fields.Url,
    "date_of_publication": fields.DateTime,
    "headline": fields.String,
    "main_text": fields.String,
    "reports": fields.List(fields.Nested(reports)),
})

parser1 = api.parser()
parser1.add_argument('start_date', help='Start date for the articles. Use format YYYY-MM-DDTHH:MM:SS. Eg:2001-01-01T00:00:00', location='args',required=True)
parser1.add_argument('end_date', help='End date for the articles. Use format YYYY-MM-DDTHH:MM:SS Eg:2019-12-31T11:59:59', location='args',required=True)
parser2 = api.parser()
parser2.add_argument('id', help='Authorisation id to delete an existing article (only available to authorised users)', location='args', required=True)
parser2.add_argument('url', help='Url to the Who news article to be deleted. Url must exist in the database', location='args', required=True)
parser3 = api.parser()
parser3.add_argument('id', help='Authorisation id to post an article (only available to authorised users)', location='args', required=True)
parser3.add_argument('url', help='Url to a Who news article. Must not already exist in the database', location='args', required=True)
parser4 = api.parser()
parser4.add_argument('id', help='Authorisation id to put a disease report into an existing article (only available to authorised users)', location='args', required=True)
parser4.add_argument('url', help='Url to the Who news article a report is to be added to. Url must exist in the database', location='args', required=True)
class Article(Resource):
    @api.response(200, 'Success',[articles])
    @api.response(404, 'No data found')
    @api.doc(params={'key_terms': 'The key terms to look for when finding article. Separate multiple key terms by comma. Eg:ebola,virus'})
    @api.doc(params={'location': 'The country where the epidemic takes place. Eg: Guinea'})
    @api.response(400, 'Invalid date format')
    @api.doc(summary='Get request gets all the articles given the parameters')
    @api.expect(parser1,validate=False)
    def get(self):
        args = parser1.parse_args()
        start_date = args['start_date']
        end_date = args['end_date']
        # check start and end date format
        if not re.match(r"^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$", start_date):
            return "Invalid date input",400
        if not re.match(r"^[0-9]{4}\-[0-9]{2}\-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$", end_date):
            return "Invalid date input",400
        location = request.args.get('location')
        if not location:
            location = ""
        key_terms = request.args.get('key_terms')
        if not key_terms:
            key_terms = ""
        final_start,final_end = self.convert_date_to_int(start_date,end_date)
        if final_end < final_start:
            return "End date must be larger than start date",400
        articles = self.check_data_exists(final_start,final_end,location,key_terms)
        if articles == False:
            return "No data found",404
        result = self.get_results(articles)
        return result,200

    @api.response(403, 'url does not exist')
    @api.response(401, 'Unauthorised id')
    @api.response(200, 'Success')
    @api.expect(parser2,validate=False)
    def delete(self, id):
         api.abort(401)

    @api.doc(params={'date_of_publication': "Date the Who news article was published. Use format YYYY-MM-DD hh:mm:ss e.g. '2020-01-17 13:09:44'"})
    @api.doc(params={'headline': 'Headline of the Who news article'})
    @api.doc(params={'main-text': 'Main text body of the Who news article'})
    @api.response(400, 'Invalid date_of_publication format')
    @api.response(403, 'url already exists')
    @api.response(401, 'Unauthorised id')
    @api.response(200, 'Success')
    @api.expect(parser3,validate=False)
    def post(self):
        api.abort(401)

    # adds a report to an article
    @api.doc(params={'event_date': "The date or date range the diseases were reported. Use format YYYY-MM-DD e.g. '2020-01-03' or '2018-12-01 to 2018-12-10'"})
    @api.doc(params={'country': 'The country the disease was reported in'})
    @api.doc(params={'location': 'The location within a country the disease was reported in'})
    @api.doc(params={'diseases': 'The disease reported in the article'})
    @api.doc(params={'syndromes': 'The symptoms reported in the article. Separate the symptoms with a comma'})
    @api.response(401, 'Unauthorised id')
    @api.response(400, 'url cannot be empty')
    @api.response(200, 'Success')
    @api.response(403, 'url does not exist')
    @api.expect(parser4,validate=False)
    def put(self):
        api.abort(401)

    # check if any data exists for the query
    def check_data_exists(self,start_date,end_date,location,key_terms):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ';'
        if location != '' and key_terms != '':
            if ',' in key_terms:
                k = key_terms.split(',')
                i = 1
                query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN Disease d on d.ReportID = r.id JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and d.Disease = \'' + k[0].lower() + '\'and l.location = \'' + location.title() + '\''
                while i < len(k):
                    query = query + ' UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN Disease d on d.ReportID = r.id JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and d.Disease = \'' + k[i].lower() + '\'and l.location = \'' + location.title() + '\''
                    i+=1
                query = query + ';'
            else:
                query = 'SELECT * from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id JOIN Disease d on d.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location.title() + '\'  and d.Disease = \'' + key_terms.lower() + '\';'
        elif location != '':
            query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,l.location,r.event_date from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location.title() + '\';'
        elif key_terms != '':
            if ',' in key_terms:
                k = key_terms.split(',')
                i = 1
                query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN Disease d on d.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and d.Disease = \'' + k[0].lower() + '\''
                while i < len(k):
                    query = query + ' UNION SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN Disease d on d.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and d.Disease = \'' + k[i].lower() + '\''
                    i+=1
                query = query + ';'
            else:
                query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN Disease d on d.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and d.Disease = \'' + key_terms.lower() + '\';'
        results = cur.execute(query).fetchall()
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
                query = 'SELECT * from Report r left join Syndrome s on s.ReportID = r.id left join Location l on l.ReportID = r.id left join Disease d on d.ReportID = r.id where r.id =' + str(id) + ';'
                report = cur.execute(query).fetchall()
                b = {}
                if len(report) > 0:
                    b['event_date'] = report[0]['event_date']
                # get list of locations, diseases and syndromes
                b['locations'] = []
                b['diseases'] = []
                b['syndromes'] = []
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