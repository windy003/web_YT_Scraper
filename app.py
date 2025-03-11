import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import yt_dlp
import logging
import re
import sys
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from models import db, User, Channel, Video  # 添加这行，导入所需的模型类
import dateutil.parser  # 需要安装 python-dateutil 包
from random import sample  # 添加这行导入
from dotenv import load_dotenv
from googleapiclient.discovery import build

# 加载 .env 文件中的环境变量
load_dotenv()

# 然后获取环境变量
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# 使用 API KEY
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# 初始化 Flask 应用
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db.init_app(app)

# 创建数据库表
with app.app_context():
    db.create_all()
    print("数据库表已创建")




# 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 用户加载函数
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# 添加上下文处理器
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# 路由和视图函数
@app.route('/')
def index():
    print("访问了首页")
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 检查用户名是否为 'windy'
        if username != 'windy':
            flash('只允许 windy 用户登录', 'danger')
            return redirect(url_for('login'))
            
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 检查用户名是否为 'windy'
        if username != 'windy':
            flash('只允许注册用户名为 windy 的账户', 'danger')
            return redirect(url_for('register'))
            
        # 检查用户是否已存在
        if User.query.filter_by(username=username).first():
            flash('该用户名已被注册', 'danger')
            return redirect(url_for('register'))
            
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    print(f"用户 {current_user.username} 登出")
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    print(f"用户 {current_user.username} 访问了控制面板")
    channels = Channel.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', channels=channels)

@app.route('/add_channel', methods=['GET', 'POST'])
@login_required
def add_channel():
    if request.method == 'POST':
        channel_url = request.form.get('channel_url')
        channel_name = extract_channel_name(channel_url)
        channel_id = 获取channel_id(channel_url)
        
        if not channel_id:
            flash('无法获取频道ID', 'error')
            return render_template('add_channel.html')
            
        # 检查频道是否已存在
        existing_channel = Channel.query.filter_by(channel_url=channel_url).first()
        if existing_channel:
            flash('该频道已存在', 'warning')
            return redirect(url_for('dashboard'))
            
        # 获取视频数据
        playlist_id = 获取上传视频播放列表_id(channel_id)
        videos = 获取播放列表中的所有视频(playlist_id)
        
        # 创建新频道
        new_channel = Channel(
            channel_url=channel_url,
            channel_name=channel_name,
            channel_id=channel_id,
            user_id=current_user.id
        )
        db.session.add(new_channel)
        
        # 保存视频数据
        success, message = save_videos_to_db(channel_url, videos)
        if not success:
            flash(message, 'error')
            return render_template('add_channel.html')
            
        db.session.commit()
        flash('频道添加成功', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('add_channel.html')



# 获取上传视频的播放列表 ID
def 获取上传视频播放列表_id(channel_id):
    request = youtube.channels().list(
        part='contentDetails',
        id=channel_id
    )
    response = request.execute()

    # with open('response.json', 'w', encoding='utf-8') as f:
    #     json.dump(response, f, ensure_ascii=False, indent=4)

        
    uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    return uploads_playlist_id

# 获取播放列表中的所有视频信息（包括播放地址、标题、描述、缩略图、时长和发布时间）
def 获取播放列表中的所有视频(playlist_id):
    videos = []
    video_ids = []
    request = youtube.playlistItems().list(
        part='snippet',
        playlistId=playlist_id,
        maxResults=50
    )
    response = request.execute()

    # with open('response.json', 'w', encoding='utf-8') as f:
    #     json.dump(response, f, ensure_ascii=False, indent=4)


    while True:
        for item in response['items']:
            video_id = item['snippet']['resourceId']['videoId']
            video_ids.append(video_id)
            video_title = item['snippet']['title']
            video_description = item['snippet']['description']
            # 尝试获取最大分辨率的缩略图，如果不存在则回退到高清缩略图
            try:
                video_thumbnail = item['snippet']['thumbnails']['maxres']['url']
            except KeyError:
                # 如果没有maxres缩略图，尝试获取high缩略图
                try:
                    video_thumbnail = item['snippet']['thumbnails']['high']['url']
                except KeyError:
                    # 如果high也没有，尝试medium
                    try:
                        video_thumbnail = item['snippet']['thumbnails']['medium']['url']
                    except KeyError:
                        # 最后尝试default
                        try:
                            video_thumbnail = item['snippet']['thumbnails']['default']['url']
                        except KeyError:
                            # 如果所有缩略图都不存在，设置为空字符串或默认值
                            video_thumbnail = ''
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            video_publish_date = item['snippet']['publishedAt']

            videos.append({
                'id': video_id,
                'title': video_title,
                'description': video_description,
                'thumbnail': video_thumbnail,
                'url': video_url,
                'publish_date': video_publish_date,
                'duration': 'N/A'  # 默认值
            })

        if 'nextPageToken' in response:
            request = youtube.playlistItems().list(
                part='snippet',
                playlistId=playlist_id,
                maxResults=50,
                pageToken=response['nextPageToken']
            )
            response = request.execute()
        else:
            break

    # 批量获取视频的时长信息
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        videos_request = youtube.videos().list(
            part='contentDetails',
            id=','.join(batch_ids)
        )
        videos_response = videos_request.execute()

        # 将时长添加到对应的视频信息中
        for video_item in videos_response['items']:
            try:
                video_id = video_item['id']
                duration = video_item['contentDetails'].get('duration', 'N/A')

                # 找到对应的视频并添加时长信息
                for video in videos:
                    if video['id'] == video_id:
                        video['duration'] = duration
                        break
            except KeyError:
                continue

    return videos


def 获取channel_id(channel_url):
    """从频道URL获取channel ID"""
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=False)
            return info.get('channel_id')
        except Exception as e:
            print(f"获取channel ID时出错: {e}")
            return None



@app.route('/channel/<int:channel_id>')
@login_required
def view_channel(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    
    # 确保用户只能查看自己的频道
    if channel.user_id != current_user.id:
        flash('您没有权限查看该频道', 'error')
        return redirect(url_for('dashboard'))
    
    # 获取该频道的所有视频
    all_videos = Video.query.filter_by(channel_url=channel.channel_url).all()
    
    # 如果视频数量大于5，随机选择5个
    if len(all_videos) > 5:
        random_videos = sample(all_videos, 5)
    else:
        random_videos = all_videos  # 如果视频数量少于等于5，显示所有视频
    
    return render_template('channel.html', 
                         channel=channel, 
                         videos=random_videos,
                         total_videos=len(all_videos))

@app.route('/refresh_channel/<int:channel_id>')
@login_required
def refresh_channel(channel_id):
    print(f"用户 {current_user.username} 刷新频道 ID: {channel_id}")
    channel = Channel.query.filter_by(id=channel_id, user_id=current_user.id).first_or_404()
    fetch_channel_videos(channel.id)
    flash('频道视频已更新')
    return redirect(url_for('view_channel', channel_id=channel.id))

@app.route('/delete_channel/<int:channel_id>', methods=['POST'])
@login_required
def delete_channel(channel_id):
    print(f"用户 {current_user.username} 删除频道 ID: {channel_id}")
    channel = Channel.query.filter_by(id=channel_id, user_id=current_user.id).first_or_404()
    db.session.delete(channel)
    db.session.commit()
    flash('频道已删除')
    return redirect(url_for('dashboard'))


# 辅助函数
def extract_channel_name(url):
    """从YouTube URL中提取频道ID"""
    try:
        print(f"正在处理URL: {url}")
        
        if 'youtube.com/channel/' in url:
            channel_id = url.split('youtube.com/channel/')[1].split('/')[0]
            print(f"从channel URL提取的ID: {channel_id}")
            return channel_id
            
        elif 'youtube.com/@' in url:
            # 对于@格式的URL，直接提取用户名
            username = url.split('youtube.com/@')[1].split('/')[0]
            print(f"从@URL提取的用户名: {username}")
            return f"@{username}"
            
        elif 'youtube.com/c/' in url:
            # 提取自定义URL
            custom_name = url.split('youtube.com/c/')[1].split('/')[0]
            print(f"从c/URL提取的名称: {custom_name}")
            return f"c/{custom_name}"
            
        elif 'youtube.com/user/' in url:
            # 提取用户名
            username = url.split('youtube.com/user/')[1].split('/')[0]
            print(f"从user URL提取的用户名: {username}")
            return f"user/{username}"
            
        print(f"无法从URL提取频道ID: {url}")
        return None
    except Exception as e:
        logger.error(f"提取频道ID时出错: {e}")
        return None

def save_videos_to_db(channel_url, videos_json):
    """将视频数据保存到数据库"""

    try:
        for video_data in videos_json:
            # 检查视频是否已存在
            existing_video = Video.query.get(video_data['id'])
            if not existing_video:
                # 转换发布日期
                published_at = None
                if 'publish_date' in video_data:
                    try:
                        published_at = dateutil.parser.parse(video_data['publish_date'])
                    except Exception as e:
                        print(f"日期转换错误: {e}")

                # 创建新的视频记录
                video = Video(
                    id=video_data['id'],
                    channel_url=channel_url,
                    title=video_data['title'],
                    description=video_data.get('description', ''),
                    thumbnail_url=video_data.get('thumbnail', ''),
                    published_at=published_at,
                    duration=video_data.get('duration', '')
                )
                db.session.add(video)
        
        # 提交所有更改
        db.session.commit()
        return True, "视频数据保存成功"
    except Exception as e:
        db.session.rollback()
        return False, f"保存视频数据时出错: {str(e)}"



@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"500错误: {str(e)}")
    return render_template('500.html'), 500


# 直接运行应用
if __name__ == '__main__':
    print("应用启动")
    app.run(host='0.0.0.0', port=5002, debug=True)


