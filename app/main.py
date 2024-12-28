from flask import Flask, render_template, request, redirect, url_for, abort, session
from flask_session import Session
import flask_login as flogin
from modules import db, News, Sentence, LoginUser
import re
from werkzeug.exceptions import HTTPException
from datetime import datetime
import translate
import os

SESSION_DIR = os.path.join(os.path.dirname(__file__), 'session')

app = Flask(__name__)
app.secret_key = 'secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = SESSION_DIR
app.config['SESSION_PERMANENT'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'

Session(app)
db.init_app(app)

with app.app_context():
	db.create_all()

login_manager = flogin.LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
	return LoginUser.query.get(int(user_id))
@login_manager.unauthorized_handler
def unauthorized():
	return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
	if not LoginUser.query.first():
		return redirect(url_for('signup'))
	if request.method == 'GET':
		return render_template('account/login.html')
	elif request.method == 'POST':
		username = request.form.get('username', None)
		password = request.form.get('password', None)
		
		# 入力チェック
		blank_error = []
		if not username:
			blank_error.append('Username')
		if not password:
			blank_error.append('Password')
		if blank_error:
			return render_template('account/login.html', error=f"{', '.join(blank_error)} field(s) are required.", username=username)
		
		user:LoginUser = LoginUser.query.filter_by(name=username).first()
		if not user or not user.authenticate(password):
			return render_template('account/login.html', error='Invalid Username or Password.', username=username)
		
		if not flogin.current_user.is_authenticated or flogin.current_user.id != user.id:
			flogin.logout_user()
		flogin.login_user(user)
		return redirect(url_for('home'))
	else:
		abort(405)

@app.route('/logout', methods=['GET','POST'])
def logout():
	if request.method == 'GET' or 'POST':
		flogin.logout_user()
		return redirect(url_for('login'))
	else:
		abort(405)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
	# 既存ユーザーがいる場合は、未認証のクライアントによる新規登録を禁止
	if flogin.current_user.is_anonymous and LoginUser.query.first():
		abort(401)
	if request.method == 'GET':
		return render_template('/account/signup.html')
	elif request.method == 'POST':
		username = request.form.get('username', None)
		password = request.form.get('password', None)
		
		# 入力チェック
		blank_error = []
		if not username:
			blank_error.append('Username')
		if not password:
			blank_error.append('Password')
		if blank_error:
			return render_template('signup.html', error=f"{', '.join(blank_error)} field(s) are required.", username=username)
		if LoginUser.query.filter_by(name=username).first():
			return render_template('signup.html', error=f'{username} : Username already exists.')
		if len(password) < 8 or len(password) > 16 or re.match(r'^[a-z]+$', password) or re.match(r'^[0-9]+$', password):
			return render_template('signup.html', error='Invalid Password.', username=username)
		
		user = LoginUser(name=username, password=password)
		db.session.add(user)
		db.session.commit()

		flogin.logout_user()
		flogin.login_user(user)
		return redirect(url_for('home'))
	else:
		abort(405)

# ホーム画面
@app.route('/', methods=['GET'])
@flogin.login_required
def home():
	if request.method == 'GET':
		news_list = News.WhiteListNewsQuery([News.CREATING, News.CREATED, News.PROCESSING, News.DONE]).all()
		return render_template('index.html', user=flogin.current_user, news_list=news_list)
	else:
		abort(405)

# 新規ニュース追加画面
@app.route('/new', methods=['GET', 'POST'])
@flogin.login_required
def new():
	if request.method == 'GET':
		return render_template('news/new.html')
	elif request.method == 'POST':
		jp_title:str = request.form.get('jp_title', None)
		eng_title:str = request.form.get('eng_title', None)
		jp_url:str = request.form.get('jp_url', None)
		eng_url:str = request.form.get('eng_url', '')
		start_date_str:str = request.form.get('start_date', None)
		private_chk:str = request.form.get('private', None)
		private:bool = True if private_chk == 'on' else False
		
		# 入力チェック
		errors = []
		blank_error = []
		if not jp_title:
			blank_error.append('Japanese Title')
		if not eng_title:
			blank_error.append('English Title')
		if not jp_url:
			blank_error.append('Japanese URL')
		if not start_date_str:
			blank_error.append('Start Date')
		if blank_error:
			errors.append(f"{', '.join(blank_error)} field(s) are required.")
		type_error = []
		try:
			start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
		except ValueError:
			type_error.append('Start Date')
		if type_error:
			errors.append(f"{', '.join(type_error)} field(s) are invalid.")
		if errors:
			return render_template('news/new.html', user=flogin.current_user, errors=errors, jp_title=jp_title, eng_title=eng_title, jp_url=jp_url, eng_url=eng_url, start_date=start_date_str)

		news = News(eng_title=eng_title, jp_title=jp_title, eng_url=eng_url, jp_url=jp_url, start_date=start_date, end_date=None, status=News.CREATING, last_updated=None, user_id=flogin.current_user.user_id, private=private)
		db.session.add(news)
		db.session.commit()

		return redirect(url_for('jparticle', news_id=news.news_id))
	else:
		abort(405)

# ニュースの検索およびログイン可否を確認
def news_loginable(news_id, user_id=None, statuses=None, public_access=False)->News:
	news: News = News.query.filter(News.status.in_(statuses), News.news_id == news_id).first()
	if news is None:
		abort(400)
	if not public_access and news.private and news.user_id != user_id:
		abort(403)
	return news

# 日本語ニュース記事入力画面
@app.route('/<news_id>/jparticle', methods=['GET', 'POST'])
@flogin.login_required
def jparticle(news_id):
	news = news_loginable(news_id, flogin.current_user.user_id, [News.CREATING])
	if request.method == 'GET':
		# セッションにデータがあればそれを使う
		jparticle = session.get(f'jparticle_{news_id}', "")
		eng_sametime = session.get(f'eng_sametime_{news_id}', False)
		return render_template('news/jparticle.html', user=flogin.current_user, news_id=news.news_id, news_title=news.eng_title, jparticle=jparticle, eng_sametime=eng_sametime)

	elif request.method == 'POST':
		jparticle:str = request.form.get('jparticle', None)
		eng_sametime:bool = request.form.get('eng_sametime', False)
		
		# 入力チェック
		errors = []
		blank_error = []
		if not jparticle:
			blank_error.append('Japanese Content')
		if blank_error:
			errors.append(f"{', '.join(blank_error)} field(s) are required.")
		if errors:
			return render_template('news/jparticle.html', user=flogin.current_user, errors=errors, news_id=news.news_id, news_title=news.eng_title, jparticle=jparticle, eng_sametime=eng_sametime)

		# セッションデータに保存
		session[f'jparticle_{news_id}'] = jparticle
		return redirect(url_for('jpconfirm', news_id=news.news_id))
	else:
		abort(405)

# 日本語ニュース記事読み込み確認画面
@app.route('/<news_id>/jparticle/confirm', methods=['GET', 'POST'])
@flogin.login_required
def jpconfirm(news_id):
	news = news_loginable(news_id, flogin.current_user.user_id, [News.CREATING])
	jparticle:str = session.get(f'jparticle_{news_id}', None)
	if jparticle is None:
		abort(400)
	sentences = [sentence.strip() for sentence in jparticle.strip().split('\n') if sentence.strip()]
	if request.method == 'GET':
		return render_template('news/jpconfirm.html', user=flogin.current_user, news_id=news_id, news_title=news.eng_title, sentences=sentences)
	elif request.method == 'POST':
		session.pop(f'jparticle_{news_id}', [])
		for i, jp_sentence in enumerate(sentences):
			sentence = Sentence(news_id=news_id, sentence_id=i, origin_jp=True, jp_sentence=jp_sentence, eng_sentence='')
			db.session.add(sentence)
		news.status = News.CREATED
		db.session.commit()
		return redirect(url_for('home'))
	else:
		abort(405)

# ニュース記事入力キャンセル
@app.route('/<news_id>/jparticle/cancel', methods=['POST'])
@flogin.login_required
def content_cancel(news_id):
	news = news_loginable(news_id, flogin.current_user.user_id, [News.CREATING])
	if request.method == 'POST':
		session.pop(f'jparticle_{news_id}')
		News.deleteNewsQuery(news_id)
		return redirect(url_for('home'))
	else:
		abort(405)

@app.route('/<news_id>/translearn', methods=['GET', 'POST'])
@flogin.login_required
def translearn(news_id):
	news = news_loginable(news_id, flogin.current_user.user_id, [News.CREATED, News.PROCESSING, News.DONE])
	sentences:list[Sentence] = Sentence.query.filter(Sentence.news_id == news_id, Sentence.origin_jp == True).all()
	if request.method == 'GET':
		return render_template('news/translearn.html', user=flogin.current_user, news_id=news_id, news_title=news.eng_title, sentences=sentences)
	elif request.method == 'POST':
		for sentence in sentences:
			eng_sentence = request.form.get(f'eng_sentence_{sentence.sentence_id}', "")
			sentence.eng_sentence = eng_sentence
			db.session.add(sentence)
		news.status = News.PROCESSING
		db.session.commit()
		return redirect(url_for('transconfirm', news_id=news.news_id))


# ニュース削除
@app.route('/<news_id>/delete', methods=['POST'])
@flogin.login_required
def delete_news(news_id):
	news:News = News.query.filter(News.status != News.DELETED, News.news_id == news_id).first()
	if news is None:
		abort(400)
	if request.method == 'POST':
		News.deleteNewsQuery(news_id)
		return redirect(url_for('home'))
	else:
		abort(405)

@app.errorhandler(HTTPException)
def handle_error(error: HTTPException):
	return render_template('error.html', error=error), error.code

if __name__ == '__main__':
	app.run(debug=True, host='0.0.0.0', port=8080)