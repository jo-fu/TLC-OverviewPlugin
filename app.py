import time, os, json, base64, hmac, urllib, requests
import boto
from boto.s3.key import Key
from boto.s3.connection import S3Connection

from flask import Flask, Response, render_template, request, make_response, jsonify, redirect, url_for
import numpy as np

import nltk
import ternip
from ternip.formats.tern import TernDocument

from hashlib import sha1

# could alternatively use goose
from newspaper import Article

nltk.data.path.append("./nltk_data")
UPLOAD_FOLDER = '/uploads'
ALLOWED_EXTENSIONS = set(['json','tl'])



app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# From the tutorial
@app.route('/metadata')
def metadata():
    resp = Response("ok")
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/show')
def show():
   
    global setId 
    setId = request.args.get('documentSetId')
    global token
    token = request.args.get('apiToken')

    # Find out ID of tag called "tlc"
    tagList = requests.get('http://localhost:9000/api/v1/document-sets/' + setId + '/tags', auth=(token, 'x-auth-token')).json()
    myarray = np.asarray(tagList)
    for el in myarray:
        if el["name"] == "tlc":
            tagId = str(el["id"])

    # Call documents
    url = 'http://localhost:9000/api/v1/document-sets/' + setId + '/documents?tags=' + tagId + '&limit=6' 
    documents = requests.get(url, auth=(token, 'x-auth-token')).json()
    
    return render_template('index.html', docs=documents['items'])

@app.route('/getSingleDoc', methods=['GET','POST'])
def getSingleDoc():
   
    thisID = str(request.json['thisID'])
    url = 'http://localhost:9000/api/v1/document-sets/' + setId + '/documents/' + thisID
    r = requests.get(url, auth=(token, 'x-auth-token'))
    thisDoc = r.json()
    
    response = { 'title' : thisDoc.get('title') , 'text' : thisDoc.get('text') }
    return jsonify(result=response)

@app.route('/tljs')
def tljs():
    return render_template('tl.html')

@app.route('/tlcOutput')
def tlcOutput():
    return redirect("http://johanna-fulda.de/ubc/newOutput/", code=302)

@app.route('/scrape', methods=['GET', 'POST'])
def scrape():

    if request.method == "POST":
        try:
            myURL = request.json['myURL']

            article = Article(myURL)
            article.download()
            article.parse()

            response = {'title': article.title, 'text': article.text,  'date': str(article.publish_date)}
            return jsonify(result=response)

        except:
            return jsonify(result="fetching unsucessful")


# Route that will process the AJAX request, sum up two
# integer numbers (defaulted to zero) and return the
# result as a proper JSON response (Content-Type, etc.)
@app.route('/dothenlp', methods=['GET','POST'])
def dothenlp():

    if request.method == "POST":
        try:
            myData = request.json['myData']
            recogniser = ternip.recogniser()
            normaliser = ternip.normaliser()
            doc = TernDocument(myData)
            strdoc = str(doc)
            ref_date = find_between(strdoc, "<DATE_TIME>", "</DATE_TIME>").replace("-","")

            sents = recogniser.tag(doc.get_sents())
            normaliser.annotate(sents, ref_date)
            doc.reconcile(sents)
            # Single Sentences
            s = find_between(str(doc), "<TEXT>", "</TEXT>").replace("\n"," <br>")
            s = s.replace("_QUOTE_","&quot;")
            s = s.replace("_APOSTROPHE_","&#39;")
            s = s.replace("_AND_","&")

            sent_tokens = nltk.sent_tokenize(s)

            t = str(doc).split("<TEXT>")[0]
            t = t.replace("_QUOTE_","&quot;")
            t = t.replace("_APOSTROPHE_","&#39;")
            t = t.replace("_AND_","&")

            output = t + "\n\n<SENTENCES>\n\n" + str(sent_tokens) + "\n\n</SENTENCES>"
            return jsonify(result=output)
        except:
            return jsonify(result="something wrong")

# Upload to Server
@app.route('/upload', methods=['POST'])
def upload():
    
    if request.method == "POST":
        try:
            myData = request.json['myData']
            title = request.json['title']
            conn = S3Connection(os.environ.get('AWS_ACCESS_KEY'), os.environ.get('AWS_SECRET_KEY'))
            bucket = conn.get_bucket('timelinecurator')
            k = Key(bucket)
            k.key = title
            k.set_contents_from_string(myData)
            k.make_public()
            return jsonify(result="successfully")

        except:
            return jsonify(result="not so successfully")


def find_between(str, f, l):
        try:
            start = str.index(f) + len(f)
            end = str.index(l, start)
            return str[start:end]
        except ValueError:
            return ""

if __name__ == '__main__':
	app.debug = True
	app.run()