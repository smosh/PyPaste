from flask import Flask, redirect, url_for, render_template, flash, request, abort, jsonify
from flaskext.sqlalchemy import SQLAlchemy
from datetime import datetime
import highlight, random

app = Flask(__name__)
app.config.from_pyfile('config.py')
db = SQLAlchemy(app)

class paste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    posted = db.Column(db.DateTime)
    title = db.Column(db.String(50))
    contents = db.Column(db.Text)
    password = db.Column(db.String(20))
    language = db.Column(db.String(40))
    unlisted = db.Column(db.Integer(16))
    p_hash = db.Column(db.String(6))
    
    def __init__(self, title, contents, password, language, unlisted, p_hash):
        self.posted = datetime.utcnow()
        self.title = title
        self.contents = contents
        self.password = password
        self.language = language
        self.unlisted = unlisted
        self.p_hash = p_hash

def addPaste(title, contents, password, language, unlisted, p_hash):
    if title.strip() == '':
        title = "Untitled"
    if contents.strip() == '':
        return redirect(url_for('index'))
    p = paste(title, contents, password, language, unlisted, p_hash)
    db.session.add(p)
    db.session.commit()
    
@app.route('/add/', methods=['POST', 'GET'])
def add():
    r = request
    if r.method == 'GET':
        return redirect(url_for('index'))
    if r.form['contents'].strip(' ') == '':
        flash('You need to paste some text')
        return redirect(url_for('index'))
        
    p_hash = str(random.getrandbits(50))[:7]
    addPaste(r.form['title'], r.form['contents'], None, r.form['language'], r.form['unlisted'], p_hash)
    pastes = paste.query.order_by(paste.posted.desc()).limit(1).all()
    
    if r.form['unlisted'] == '1':
        flash('Unlisted paste created! It can only be accessed via this URL, so be careful who you share it with')
        return redirect(url_for('index')+'unlisted/'+str(pastes[0].p_hash))    
    else:
        return redirect(url_for('view_list')+str(pastes[0].id))

# Pages

@app.route('/')
def index():
    error = None
    pastes = paste.query.filter_by(unlisted=0).order_by(paste.posted.desc()).limit(7).all()
    for thing in pastes:
        if len(thing.title) >= 15:
            thing.title = thing.title[:12] + '...'
        thing.posted = datetime.utcnow() - thing.posted
        thing.posted = str(thing.posted).split('.')[0]
    return render_template('add_paste.html', pastes=pastes, error=error)

@app.route('/view/')
def view_list():
    error = None
    pastes = paste.query.filter_by(unlisted=0).order_by(paste.posted.desc()).limit(40).all()
    for thing in pastes:
        thing.title = thing.title[:50]
        thing.contents = thing.contents[:40]
        thing.posted = datetime.utcnow() - thing.posted
        thing.posted = str(thing.posted).split('.')[0]
    return render_template('paste_list.html', pastes=pastes, error=error)

@app.route('/view/<int:paste_id>/')
def view_paste(paste_id):
    error = None
    highlighted = None
    cur_paste = paste.query.get(paste_id)
    if cur_paste == None or cur_paste.unlisted == 1:
        abort(404)
    title = cur_paste.title
    try: highlighted = highlight.syntax(cur_paste.contents, cur_paste.language)
    except:
        ''' In the case where the user was able to select a language which has no syntax highlighting configured 
            (by sending a POST request and not using the form) it will alert them to it '''
        error = 'That language has no highlighting available! Oops! <a href="mailto://%(email)s">email</a> me and tell me to fix it!' % { 'email': app.config['EMAIL'] }    
        highlighted = highlight.syntax(cur_paste.contents, 'none')
    recent_pastes = paste.query.filter_by(unlisted=0).order_by(paste.posted.desc()).limit(7).all()
    for thing in recent_pastes:
        if len(thing.title) >= 15:
            thing.title = thing.title[:12] + '...'
        thing.posted = datetime.utcnow() - thing.posted
        thing.posted = str(thing.posted).split('.')[0]
    return render_template('view_paste.html', cur_paste=cur_paste, recent_pastes=recent_pastes, highlighted=highlighted, title=title, error=error)

@app.route('/unlisted/<int:paste_hash>/')
def view_unlisted_paste(paste_hash):
    error = None
    highlighted = None
    cur_paste = paste.query.filter_by(p_hash=paste_hash).first()
    if cur_paste == None:
        abort(404)
    title = cur_paste.title
    try: highlighted = highlight.syntax(cur_paste.contents, cur_paste.language)
    except:
        error = 'That language has no highlighting available! Oops! <a href="mailto://%(email)s">email</a> me and tell me to fix it!' % { 'email': app.config['EMAIL'] }    
        highlighted = highlight.syntax(cur_paste.contents, 'none')
    recent_pastes = paste.query.filter_by(unlisted=0).order_by(paste.posted.desc()).limit(7).all()
    for thing in recent_pastes:
        if len(thing.title) >= 15:
            thing.title = thing.title[:12] + '...'
        thing.posted = datetime.utcnow() - thing.posted
        thing.posted = str(thing.posted).split('.')[0]
    return render_template('view_paste.html', cur_paste=cur_paste, recent_pastes=recent_pastes, highlighted=highlighted, title=title, error=error)

# API

@app.route('/api/add', methods=['POST'])
def api_add():
    r = request  
    if r.form['contents'] == '':
        return jsonify(success=False, error='No content')
    p_hash = str(random.getrandbits(50))[:7]
    addPaste(r.form['title'], r.form['contents'], None, r.form['language'], r.form['unlisted'], p_hash)
    pastes = paste.query.order_by(paste.posted.desc()).limit(1).all()
    if r.form['unlisted'] == '1':
        return jsonify(success=True, url=url_for('index')+'unlisted/'+str(pastes[0].p_hash))    
    else:
        return jsonify(success=True, url=url_for('view_list')+str(pastes[0].id))


# Errors

@app.errorhandler(404)
def error_404(error):
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run()
