import flask
from flask import request, jsonify
import sqlite3
import os

app = flask.Flask(__name__)
app.config["DEBUG"] = True

@app.route('/', methods=['GET'])
def home():
    return "<h1>Distant Reading Archive</h1><p>This site is a TELETUBBIES prototype API.</p>"

@app.route('/api/v1/resources/books/all', methods=['GET'])
def api_all():
    conn = sqlite3.connect('books.db')
    conn.row_factory = dict_factory
    cur = conn.cursor()
    all_books = cur.execute('SELECT * FROM books;').fetchall()

    return jsonify(all_books)
# user specify an id
@app.route('/api/v1/resources/books', methods=['GET'])
def api_id():
    # Check if an ID was provided as part of the URL.
    # If ID is provided, assign it to a variable.
    # If no ID is provided, display 404 page.
    results = []
    if 'id' in request.args:
        id = int(request.args['id'])
        to_filter = []
        query = "SELECT * FROM books WHERE id = "
        query += str(id) + ';'

        conn = sqlite3.connect('books.db')
        conn.row_factory = dict_factory
        cur = conn.cursor()
        results = cur.execute(query, to_filter).fetchall()
    else:
         return page_not_found(404)

    # Use the jsonify function from Flask to convert our list of
    # Python dictionaries to the JSON format.
    return jsonify(results)

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

# helper function
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

if __name__ == "__main__":
    app.run()
