from datetime import datetime
import hashlib
import random
from collections import Iterable
from os import urandom
from optparse import OptionParser
import getpass
import logging
import time


from flask import Flask, redirect, url_for, render_template, flash, request
from flask import abort, jsonify, session, make_response
from flask.ext.sqlalchemy import SQLAlchemy

import highlight
import pretty_age

app = Flask(__name__)
app.config.from_pyfile('config.py')
db = SQLAlchemy(app)
logging.basicConfig(filename=app.config['LOG_PATH'], format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%Y/%m/%d %H:%M', level=logging.INFO)


class pastes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    posted = db.Column(db.DateTime)
    title = db.Column(db.String(50))
    contents = db.Column(db.Text)
    highlighted = db.Column(db.Text)
    password = db.Column(db.String(20))
    language = db.Column(db.String(40))
    unlisted = db.Column(db.Integer(16))
    p_hash = db.Column(db.String(6))

    def __init__(self, title, contents, highlighted, password, language, unlisted, p_hash):
        self.posted = datetime.now()
        self.title = title
        self.contents = contents
        self.highlighted = highlighted
        self.password = password
        self.language = language
        self.unlisted = unlisted
        self.p_hash = p_hash

class users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    salt = db.Column(db.String(255), nullable=False)

    def __init__(self, username, password, salt):
        self.username = username
        self.password = password
        self.salt = salt

@app.route('/add', methods=['POST'])
def add():
    r = request
    if r.form['do-not-fill-this-in'] != '':
        logging.info('Antispam caught user with IP %s, UA %s. Message: %s' % (r.remote_addr, r.user_agent, r.form['contents']))
        return redirect(url_for('index'))
    if r.form['contents'].strip() == '':
        flash('You need to paste some text')
        return redirect(url_for('index'))
    if r.form['password'] == '':
        password = None
    else: password = r.form['password']

    p = addPaste(r.form['title'], r.form['contents'], password, r.form['language'], r.form['unlisted'])

    if r.form['unlisted'] == '1':
        flash('Unlisted paste created! It can only be accessed via this URL, so be careful who you share it with')
        return redirect(url_for('view_unlisted_paste', paste_hash=p.p_hash))
    else:
        return redirect(url_for('view_paste', paste_id=p.id))

@app.route('/del', methods=['POST'])
def delete():
    if 'logged_in' not in session.keys() or session['logged_in'] != True:
        abort(401)
    r = request
    delPaste(r.form['pid'])
    logging.info('%s deleted paste with ID %s' % (session['username'], r.form['pid']))
    flash('Paste with ID #%s has been deleted' % r.form['pid'])
    return redirect(url_for('view_all_pastes'))


@app.route('/authenticate', methods=['POST'])
def authenticate():
    r = request
    pid = int(r.form['pid'])
    unlisted = bool(int(r.form['unlisted']))

    if unlisted:
        p = pastes.query.filter_by(p_hash=pid).first()
    else:
        p = pastes.query.filter_by(id=pid).first()

    if p == None:
        abort(400)

    if r.form['password'] != p.password:
        flash('Incorrect password')
    elif r.form['password'] == p.password:
        try:
            session['allowed_pastes'].append(p.id)
        except KeyError:
            session['allowed_pastes'] = [pid]
        session.modified = True
    
    if unlisted:
        return redirect(url_for('view_unlisted_paste', paste_hash=pid))
    else:
        return redirect(url_for('view_paste', paste_id=pid))



# Pages

@app.route('/')
def index():
    error = None
    _pastes = pastes.query.filter_by(unlisted=0).order_by(pastes.posted.desc()).limit(7).all()
    return render_template('add_paste.html', pastes=format(_pastes), error=error)

@app.route('/view/')
def view_list():
    ''' Lists all public pastes '''
    error = None
    _pastes = pastes.query.filter_by(unlisted=0).order_by(pastes.posted.desc()).limit(40).all()
    return render_template('paste_list.html', pastes=format(_pastes), error=error)

@app.route('/view/all/')
def view_all_pastes():
    ''' Lists both listed and unlisted pastes, must be logged in '''
    if 'logged_in' not in session.keys() or session['logged_in'] != True:
        abort(404)
    all_pastes = pastes.query.order_by(pastes.posted.desc()).limit(40).all()
    return render_template('paste_list.html', pastes=format(all_pastes))

@app.route('/view/<int:paste_id>/')
def view_paste(paste_id):
    ''' Viewing a specific paste '''
    cur_paste = pastes.query.get(paste_id)
    if cur_paste == None or cur_paste.unlisted == 1:
        abort(404)
    return render_template('view_paste.html', cur_paste=format(cur_paste))

@app.route('/view/<int:paste_id>/raw/')
def view_raw_paste(paste_id):
    ''' Raw version of a specific paste '''
    cur_paste = pastes.query.get(paste_id)
    if cur_paste == None or cur_paste.unlisted == 1:
        abort(404)
    response = make_response(cur_paste.contents)
    response.mimetype = 'text/plain'
    if cur_paste.password != None and session.has_key('allowed_pastes') and cur_paste.id in session['allowed_pastes']:
        return response
    elif cur_paste.password == None:
        return response
    else: return redirect(url_for('view_paste', paste_id=paste_id))

@app.route('/unlisted/<int:paste_hash>/')
def view_unlisted_paste(paste_hash):
    ''' Viewing a specific unlisted paste '''
    cur_paste = pastes.query.filter_by(p_hash=paste_hash).first()
    if cur_paste == None:
        abort(404)
    return render_template('view_paste.html', cur_paste=format(cur_paste))

@app.route('/unlisted/<int:paste_hash>/raw/')
def view_raw_unlisted_paste(paste_hash):
    ''' Raw version of a specific unlisted paste '''
    cur_paste = pastes.query.filter_by(p_hash=paste_hash).first()
    if cur_paste == None:
        abort(404)
    response = make_response(cur_paste.contents)
    response.mimetype = 'text/plain'
    if cur_paste.password != None and session.has_key('allowed_pastes') and cur_paste.id in session['allowed_pastes']:
        return response
    elif cur_paste.password == None:
        return response
    else: return redirect(url_for('view_unlisted_paste', paste_hash=paste_hash))

@app.route('/login/', methods=['GET', 'POST'])
def login():
    def logAttempt():
            logging.info('%s attempted to login as user %s' % (r.remote_addr, r.form['username']))

    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        r = request
        u = users.query.filter_by(username=r.form['username']).first()
        if u == None:
            logAttempt()
            flash('User not found')
            return redirect(url_for('login'))

        password = hashPassword(r.form['password'], u.salt)
        if u.password != password:
            logAttempt()
            flash('Incorrect username/password combo')
            return redirect(url_for('login'))
        else:
            session['logged_in'] = True
            session['username'] = u.username
            flash('Successfully logged in')
            return redirect(url_for('index'))

@app.route('/logout/')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You were logged out')
    return redirect(url_for('index'))

# API

@app.route('/api/')
def api():
    return render_template('api.html')

@app.route('/api/add', methods=['POST'])
def api_add():
    r = request
    error = []
    contents = r.form.get('contents', '')
    title = r.form.get('title', 'Untitled')
    password = r.form.get('password')
    language = r.form.get('language', 'text')
    unlisted = r.form.get('unlisted', 0)

    if contents.strip() is '':
        error.append('No contents specified')
    if language.lower().strip() not in highlight.languages.keys():
        error.append('Unsupported language')
    try:
        unlisted = int(unlisted)
    except ValueError:
        error.append('Invalid value: (unlisted: \'{}\')'.format(unlisted))

    if len(error) != 0:
        return jsonify(success=False, error=error)

    p = addPaste(title, contents, password, language.lower(), unlisted)

    if unlisted == 0:
        return jsonify(success=True, password=password, url=url_for('view_paste', paste_id=p.id, _external=True))
    else:
        return jsonify(success=True, password=password, url=url_for('view_unlisted_paste', paste_hash=p.p_hash, _external=True))


# Errors

@app.errorhandler(404)
def error_404(error):
    return render_template('404.html'), 404


# Non-front facing thingies

def format(pastes):
    ''' Formats pastes '''
    # Get age from date
    if isinstance(pastes, Iterable):
        for paste in pastes:
            if not isinstance(paste.posted, str):
                paste.age = pretty_age.get_age(paste.posted)
    else:
        if not isinstance(pastes.posted, str):
            pastes.age = pretty_age.get_age(pastes.posted)
    return pastes

def addPaste(title, contents, password, language, unlisted):
    if title.strip() == '':
        title = "Untitled"
    highlighted = highlight.syntax(contents, language)
    p_hash = generatePasteHash()
    p = pastes(title, contents, highlighted, password, language, unlisted, p_hash)
    db.session.add(p)
    db.session.commit()
    return p

def delPaste(id):
    p = pastes.query.get(id)
    db.session.delete(p)
    db.session.commit()

def addUser(username, password, salt):
    u = users(username, password, salt)
    db.session.add(u)
    db.session.commit()
    print username + ' added'

def generatePasteHash():
    ''' Generates a unique sequence to identify a paste,
        used for unlisted pastes'''
    while True:
        p_hash = str(random.getrandbits(50))[:7]
        otherPastes = pastes.query.filter_by(p_hash=p_hash).order_by(pastes.posted.desc()).all()
        if otherPastes == []:
            break
    return p_hash

def hashPassword(password, salt):
    p = hashlib.new('sha256')
    p.update(password + salt)
    return p.hexdigest()

def newUser(username):
    salt = urandom(60).encode('hex')
    password = hashPassword(getpass.getpass(), salt)
    addUser(username, password, salt)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-a', help='Add an admin account', action="store", type="string", dest="username")
    (options, args) = parser.parse_args()

    if options.username != None:
        newUser(options.username)
    else:
        app.run()
