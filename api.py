
from flask import Flask,jsonify,request
import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property
from flask_restplus import Api, Resource, fields
import sqlite3
import datetime

app = Flask(__name__)
app.config["DEBUG"] = True
api = Api(app)

class Article(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'No data found')
    def get(self, start_date,end_date):
        location = request.args.get('location')
        if not location:
            location = ""
        key_terms = request.args.get('key_terms')
        if not key_terms:
            key_terms = ""
        final_start,final_end = self.convert_date_to_int(start_date,end_date)
        if final_end < final_start:
            return "End date must be larger than start date",404
        articles = self.check_data_exists(final_start,final_end,location,key_terms)
        if articles == False:
            return "No data found",404
        result = self.get_results(articles)
        return result,200

    @api.response(403, 'Not Authorized')
    def post(self, id):
        api.abort(403)

    @api.response(403, 'Not Authorized')
    def put(self, id):
        api.abort(403)

    @api.response(403, 'Not Authorized')
    def delete(self, id):
        api.abort(403)

    # check if any data exists for the query
    def check_data_exists(self,start_date,end_date,location,key_terms):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date from Article a JOIN Report r on r.url = a.url where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ';'
        if location != '' and key_terms != '':
            query = 'SELECT * from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id JOIN Disease d on d.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location + '\'  and d.Disease = \'' + key_terms + '\';'
        elif location != '':
            query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,l.location,r.event_date from Article a JOIN Report r on r.url = a.url JOIN Location l on l.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and l.location = \'' + location + '\';'
        elif key_terms != '':
            query = 'SELECT r.id,a.headline,a.main_text,a.date_of_publication,a.url,r.event_date,d.disease from Article a JOIN Report r on r.url = a.url JOIN Disease d on d.ReportID = r.id where a.date_of_publication >=' + start_date + ' and a.date_of_publication <=' + end_date + ' and d.Disease = \'' + key_terms + '\';'
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

api.add_resource(Article, "/article/<string:start_date>/<string:end_date>")

if __name__ == "__main__":
    app.run()
