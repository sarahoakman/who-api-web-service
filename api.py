import flask
from flask import request, jsonify
import sqlite3
import os

app = flask.Flask(__name__)
app.config["DEBUG"] = True
api = Api(app)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class Report(Resource):
    def get(self, start_date,end_date,location='',key_terms=''):
        if start_date == "" or end_date == "":
            return "Please provide start and end date in correct format",404
        elif location == "" and key_terms == "":
            result = self.get_date_only(start_date,end_date)
        # key terms and location are provided
        elif location != "" and key_terms != "":
            result = self.get_date_location_key_terms(start_date,end_date,location,key_terms)
        # location is provided
        elif location != "":
            result = self.get_date_location(start_date,end_date,location)
            return result
        #  key_terms is provided
        elif key_terms != "":
            result = self.get_data_key_terms(start_date,end_date,key_terms)
            return result
        else:
            result = "Error",404

        return result

    def get_data_key_terms(self,start_date,end_date,key_terms):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        query= self.construct_date_query(start_date,end_date) + ' and d.disease=\'' + key_terms.title() + '\';'
        all_results = cur.execute(query).fetchall()
        if not all_results:
            return 'No data found',404
        return all_results,200

    def get_date_location_key_terms(self,start_date,end_date,location,key_terms):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        # logic for key_terms can be better
        # handle more than one key term
        query= self.construct_date_query(start_date,end_date) + ' and l.location=\'' + location.title() + '\' and d.disease=\'' + key_terms + '\';'
        all_results = cur.execute(query).fetchall()
        if not all_results:
            return 'No data found',404
        return all_results,200

    def get_date_location(self,start_date,end_date,location):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        query= self.construct_date_query(start_date,end_date) + ' and l.location=\'' + location.title() + '\';'
        all_results = cur.execute(query).fetchall()
        if not all_results:
            return 'No data found',404
        return all_results,200

    def get_date_only(self,start_date,end_date):
        conn = sqlite3.connect('who.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        query= self.construct_date_query(start_date,end_date) + ';'
        all_results = cur.execute(query).fetchall()
        if not all_results:
            return 'No data found',404
        return all_results,200

    def construct_date_query(self,start_date,end_date):
        start_day,start_time = start_date.split('T')
        end_day,end_time = end_date.split('T')
        sd = start_day.replace("-","")
        ed = end_day.replace("-","")
        st = start_time.replace(":","")
        et = end_time.replace(":","")
        final_start = sd + st
        final_end = ed + et
        query = 'SELECT a.Headline,a.MainText,a.PublicationDate,a.URL,c.Source,c.Cases,c.Deaths,c.Controls,d.disease,l.location,r.eventdate,s.symptom from Article a JOIN Report r on r.url = a.url LEFT JOIN Disease d on d.ReportID = r.id LEFT JOIN Description c on c.ReportID = r.id LEFT JOIN Location l on l.ReportID = r.id LEFT JOIN Syndrome s on s.ReportID = r.id where a.PublicationDate >=' + final_start + ' and a.PublicationDate <=' + final_end
        return query

api.add_resource(Report, "/teletubbies/who-api/report/start_date=<string:start_date>&end_date=<string:end_date>","/teletubbies/who-api/report/start_date=<string:start_date>&end_date=<string:end_date>&location=<string:location>","/teletubbies/who-api/report/start_date=<string:start_date>&end_date=<string:end_date>&key_terms=<string:key_terms>","/teletubbies/who-api/report/start_date=<string:start_date>&end_date=<string:end_date>&key_terms=<string:key_terms>&location=<string:location>","/teletubbies/who-api/report/start_date=<string:start_date>&end_date=<string:end_date>&location=<string:location>&key_terms=<string:key_terms>")

if __name__ == "__main__":
    app.run()
