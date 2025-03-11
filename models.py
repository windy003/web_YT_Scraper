from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # 建立与 Channel 的关系（一个用户可以有多个频道）
    channels = db.relationship('Channel', backref='user', lazy=True)

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Channel(db.Model):
    __tablename__ = 'channels'
    
    id = db.Column(db.Integer, primary_key=True)
    channel_url = db.Column(db.String(255), unique=True)
    channel_name = db.Column(db.String(255), nullable=False)
    channel_id = db.Column(db.String(100), unique=True, nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 添加用户外键
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # 与 Video 的关系
    videos = db.relationship('Video', backref='channel', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Channel {self.channel_name}>'

class Video(db.Model):
    __tablename__ = 'videos'
    
    id = db.Column(db.String(100), primary_key=True)
    channel_url = db.Column(db.String(255), db.ForeignKey('channels.channel_url'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    thumbnail_url = db.Column(db.String(500))
    published_at = db.Column(db.DateTime)
    duration = db.Column(db.String(50))
    
    def __repr__(self):
        return f'<Video {self.title}>'
