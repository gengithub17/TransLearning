from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import secrets
from sqlalchemy.orm import Query
from werkzeug.security import generate_password_hash, check_password_hash
from googletrans import Translator

db = SQLAlchemy()

class News(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	news_id = db.Column(db.String(8), unique=True, nullable=False)
	eng_title = db.Column(db.String(255))
	jp_title = db.Column(db.String(255))
	eng_url = db.Column(db.String(255))
	jp_url = db.Column(db.String(255))
	start_date = db.Column(db.Date)
	end_date = db.Column(db.Date)
	last_updated = db.Column(db.DateTime)
	user_id = db.Column(db.Integer, db.ForeignKey('login_user.id'))
	private = db.Column(db.Boolean, default=False)

	# News Status
	CREATING, CREATED, PROCESSING, DONE, DELETED = range(5)
	STATUS_NAME = ['Creating', 'Created', 'Processing', 'Done', 'Deleted']
	status = db.Column(db.Integer, nullable=False)

	def __init__(self, eng_title, jp_title, eng_url, jp_url, start_date, end_date, status, last_updated, user_id, private=False):
		self.eng_title = eng_title
		self.jp_title = jp_title
		self.eng_url = eng_url
		self.jp_url = jp_url
		self.start_date = start_date
		self.end_date = end_date
		self.news_id = self.generate_unique_news_id()  # ユニークなIDを生成
		self.status = status
		self.last_updated = last_updated
		self.user_id = user_id
		self.private = private

	def generate_unique_news_id(self):
		"""一意なランダムなニュースIDを生成する（衝突があれば再生成）"""
		while True:
			# ランダムなnews_idを生成
			news_id = secrets.token_hex(4)
			# データベースに同じnews_idがすでに存在する場合、再生成
			if not News.query.filter_by(news_id=news_id).first():
				return news_id
	
	def print_status(self):
		return self.STATUS_NAME[self.status]
	
	@classmethod
	def WhiteListNewsQuery(cls, status:list[int])->Query:
		return cls.query.filter(cls.status.in_(status))
	
	@classmethod
	def deleteNewsQuery(cls, news_id)->bool:
		Sentence.query.filter_by(news_id=news_id).delete()
		cls.query.filter_by(news_id=news_id).delete()
		db.session.commit()
		return True

class Sentence(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	news_id = db.Column(db.Integer, db.ForeignKey('news.id'))
	sentence_id = db.Column(db.Integer)
	origin_jp = db.Column(db.Boolean)
	jp_sentence = db.Column(db.String(511), default='')
	eng_sentence = db.Column(db.String(511), default='')

class LoginUser(db.Model, UserMixin):
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.String(8), unique=True, nullable=False)
	name = db.Column(db.String(255), unique=True, nullable=False)
	password = db.Column(db.String(255), nullable=False)

	def __init__(self, name, password):
		self.user_id = self.generate_unique_user_id()  # ユニークなIDを生成
		self.name = name
		self.password = generate_password_hash(password)

	def generate_unique_user_id(self):
		"""一意なランダムなユーザーIDを生成する（衝突があれば再生成）"""
		while True:
			# ランダムなuser_idを生成
			user_id = secrets.token_hex(4)
			# データベースに同じuser_idがすでに存在する場合、再生成
			if not LoginUser.query.filter_by(user_id=user_id).first():
				return user_id
	
	def authenticate(self, password):
		return check_password_hash(self.password, password)
