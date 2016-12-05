from flask import Flask, g, session, abort, redirect, url_for, render_template, request, escape, send_from_directory
from werkzeug.utils import secure_filename
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
import hashlib
import os
import subprocess
import bcrypt

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'uploads')
ALLOWED_EXTENSIONS = set(['pdf'])

app = Flask(__name__)

# set the upload path
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# set the secret key.  keep this really secret:
app.secret_key = 'ff29b42f8d7d5cbefd272eab3eba6ec8'

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/libreread_dev'
db = SQLAlchemy(app)

from models import User, Book

@app.before_request
def before_request():
    if 'email' in session:
        g.user = session['email']
    else:
        g.user = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'email' in session:
        return render_template('home.html')
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        password_hash = bcrypt.hashpw(password, bcrypt.gensalt())

        user = User(name, email, password_hash)
        db.session.add(user)
        db.session.commit()
        session['email'] = email
        users = User.query.all()

        print (users)

        return redirect(url_for('index'))
    return '''
        <form action="" method="post">
            <p><input type=text name=name></p>
            <p><input type=text name=email></p>
            <p><input type=text name=password></p>
            <p><input type=submit value=sign up></p>
        </form>
    '''

@app.route('/signin', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user is not None:
            if bcrypt.hashpw(password, user.password_hash) == user.password_hash:
                session['email'] = email
                return redirect(url_for('index'))
    return '''
        <form action="" method="post">
            <p><input type=text name=email></p>
            <p><input type=text name=password></p>
            <p><input type=submit value=Login></p>
        </form>
    '''

@app.route('/signout')
def logout():
    # remove the email from the session if it's there
    session.pop('email', None)
    return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

@app.route('/book-upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        for i in range(len(request.files)):
          file = request.files['file['+str(i)+']']
          if file.filename == '':
              print ('No selected file')
              return redirect(request.url)
          if file and allowed_file(file.filename):
              filename = secure_filename(file.filename)
              file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
              file.save(file_path)

              info = _pdfinfo(file_path)
              print (info)

              img_folder = 'images/' + '_'.join(info['Title'].split(' '))
              cover_path = os.path.join(app.config['UPLOAD_FOLDER'], img_folder)

              _gen_cover(file_path, cover_path)

              cover = cover_path + '-001-000.png'
              print cover

              book = Book(title=info['Title'], author=info['Author'], url=file_path, cover=cover, pages=info['Pages'])

              user = User.query.filter_by(email=session['email']).first()
              user.books.append(book)
              db.session.add(user)
              db.session.add(book)
              db.session.commit()

              print user.books

              print ('Book uploaded successfully!')
        return 'success'
    else:
        return redirect(url_for('index'))

@app.route('/b/<filename>')
def send_book(filename):
    return send_from_directory('uploads', filename)

@app.route('/b/cover/<filename>')
def send_book_cover(filename):
    return send_from_directory('uploads/images', filename)

def _pdfinfo(infile):
    """
    Wraps command line utility pdfinfo to extract the PDF meta information.
    Returns metainfo in a dictionary.
    sudo apt-get install poppler-utils
    This function parses the text output that looks like this:
        Title:          PUBLIC MEETING AGENDA
        Author:         Customer Support
        Creator:        Microsoft Word 2010
        Producer:       Microsoft Word 2010
        CreationDate:   Thu Dec 20 14:44:56 2012
        ModDate:        Thu Dec 20 14:44:56 2012
        Tagged:         yes
        Pages:          2
        Encrypted:      no
        Page size:      612 x 792 pts (letter)
        File size:      104739 bytes
        Optimized:      no
        PDF version:    1.5
    """
    import os.path as osp
    import subprocess

    cmd = '/usr/bin/pdfinfo'
    # if not osp.exists(cmd):
    #     raise RuntimeError('System command not found: %s' % cmd)

    if not osp.exists(infile):
        raise RuntimeError('Provided input file not found: %s' % infile)

    def _extract(row):
        """Extracts the right hand value from a : delimited row"""
        return row.split(':', 1)[1].strip()

    output = {}

    labels = ['Title', 'Author', 'Creator', 'Producer', 'CreationDate',
              'ModDate', 'Tagged', 'Pages', 'Encrypted', 'Page size',
              'File size', 'Optimized', 'PDF version']

    cmd_output = subprocess.check_output(['pdfinfo', infile])
    for line in cmd_output.splitlines():
        for label in labels:
            if label in line:
                output[label] = _extract(line)

    return output

def _gen_cover(file_path, cover_path):
    print file_path
    print cover_path
    subprocess.call('pdfimages -p -png -f 1 -l 2 ' + file_path + ' ' + cover_path, shell=True)