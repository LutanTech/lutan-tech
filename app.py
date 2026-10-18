from datetime import datetime, timedelta
from functools import wraps
import ipaddress
import json
import math
import os
import re
import secrets
import string
from urllib.parse import urlencode

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    request,
    session,
    url_for,
)
from flask import Response
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import markdown2
from markupsafe import Markup
import requests
from slugify import slugify
from sqlalchemy import func
from sqlalchemy.sql.functions import user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from bots import detect_bot
from p import projects

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lutan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

RECAPTCHA_SECRET_KEY = os.environ.get('GOOGLE_KEY')
delta=3


db = SQLAlchemy(app)
migrate = Migrate(app, db)

def generate_id(suffix="ID", length=6):
    chars = string.ascii_letters + string.digits
    return suffix + ''.join(secrets.choice(chars) for _ in range(length))

def captcha_verify(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "POST":
            is_json = request.is_json
            is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

            token = (
                request.headers.get("G-Recaptcha-Response")
                if is_json or is_ajax
                else request.form.get("g-recaptcha-response")
            )

            def reject(message):
                if is_json:
                    return jsonify({"error": message}), 400
                flash(message, "error")
                return redirect(request.referrer or "/")

            print('-------------', RECAPTCHA_SECRET_KEY)
            if not token:
                return reject("Please complete the reCAPTCHA verification.")

            try:
                response = requests.post(
                    "https://www.google.com/recaptcha/api/siteverify",
                    data={
                        "secret": RECAPTCHA_SECRET_KEY,
                        "response": token,
                        "remoteip": request.remote_addr,
                    },
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()
            except (requests.RequestException, ValueError):
                return reject("reCAPTCHA verification failed. Please try again.")

            if not result.get("success"):
                return reject("Please complete the reCAPTCHA verification.[RESULT]")

        return f(*args, **kwargs)

    return wrapper

@app.context_processor
def inject_globals():
    return {'year': datetime.utcnow().year}

@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return [value] if value else []



def render_blog_content(content):
    pattern = r'<p>\s*\+\+\s*</p>(.*?)<p>\s*\+\+\s*</p>'

    def replace_takeaway(match):
        return f'<div class="blog-takeaway">{match.group(1).strip()}</div>'

    content = re.sub(pattern, replace_takeaway, content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<p>\s*\+\+\s*</p>', '', content, flags=re.IGNORECASE)
    return Markup(content)

app.jinja_env.globals["render_blog_content"] = render_blog_content

class Staff(db.Model):
    id = db.Column(db.String(50), primary_key=True, default=lambda: generate_id('SUB', 6))
    google_id = db.Column(db.String(500), index=True)
    email = db.Column(db.String(500), unique=True, index=True, nullable=False)
    username = db.Column(db.String(500), index=True, nullable=True)
    password = db.Column(db.String(2048), nullable=False)
    login_method = db.Column(db.String(50), nullable=False, default='email')
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow() + timedelta(hours=delta))
    is_admin = db.Column(db.Boolean, default=False)  
    is_active = db.Column(db.Boolean, default=False)  

class Log(db.Model):
    id = db.Column(db.String(50), primary_key=True, default=lambda: generate_id('LOG', 8))
    level = db.Column(db.String(20), nullable=False, default='info', index=True)
    code = db.Column(db.String(10))
    method = db.Column(db.String(10))
    route = db.Column(db.String(1000), nullable=False, index=True)
    ip_address = db.Column(db.String(45), index=True)
    message = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.Text)
    username = db.Column(db.String(500), nullable=True)
    is_bot = db.Column(db.Boolean, default=False)  
    bot_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta), index=True)
    deleted_at = db.Column(db.DateTime)
   
class BlockedIP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta), nullable=False)
 
class Message(db.Model):
    id = db.Column(db.String(50), primary_key=True, default=lambda: generate_id('MSG', 8))
    name = db.Column(db.String(200), nullable=False, index=True)
    email = db.Column(db.String(200), nullable=False,index=True)
    subject = db.Column(db.String(500), nullable=True)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))

class VisitorCampaign(db.Model):
    id = db.Column(db.String(50), primary_key=True, default=lambda: generate_id('UTM', 8))
    source = db.Column(db.String(255), index=True)
    medium = db.Column(db.String(255), index=True)
    campaign = db.Column(db.String(255), index=True)
    term = db.Column(db.String(255))
    content = db.Column(db.String(255))
    landing_page = db.Column(db.String(1000), nullable=False)
    referrer = db.Column(db.String(1000))
    ip_address = db.Column(db.String(45), index=True)
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta), index=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    date = db.Column(db.String(50))
    type = db.Column(db.String(100), nullable=False)
    desc = db.Column(db.Text, nullable=False)
    img = db.Column(db.String(500))
    site = db.Column(db.String(500), nullable=False)
    code = db.Column(db.String(500))
    tech = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))

class Blog(db.Model):
    id = db.Column(db.String(), primary_key=True, default=lambda:generate_id('BLOG', 6))
    title = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(500))
    summary = db.Column(db.String(5000))
    slug = db.Column(db.String(5000))
    icon = db.Column(db.String(50), nullable=False, default="fas fa-code")
    markdown = db.Column(db.Text, nullable=False)
    html = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(500))
    by = db.Column(db.String(500), default="Lutan Tech Editorial")
    tags = db.Column(db.JSON, nullable=False, default=list)
    reading_time = db.Column(db.Integer, default=1)
    date = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))
    deleted_at = db.Column(db.DateTime)
    
    
    def compute_reading_time(self):
        words = len(self.markdown.split())
        self.reading_time = max(1, math.ceil(words / 200))

def log(level='info', code=None, method=None, route=None, ip_address=None, message='', user_agent=None, is_bot=None, bot_name=None, username=None):
    try:
        db.session.add(Log(
            level=level,
            code=str(code) if code is not None else None,
            method=method,
            route=route or '/',
            ip_address=ip_address,
            message=message or 'No message provided',
            user_agent=user_agent,
            is_bot=is_bot,
            bot_name=bot_name,
            username = username or session.get('username') or "GUEST"
            
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('Failed to save log')

def log_campaign():
    params = request.args
    keys = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content')

    if not any(params.get(key) for key in keys):
        return

    try:
        db.session.add(VisitorCampaign(
            source=params.get('utm_source'),
            medium=params.get('utm_medium'),
            campaign=params.get('utm_campaign'),
            term=params.get('utm_term'),
            content=params.get('utm_content'),
            landing_page=request.path + (
                '?' + urlencode(params.to_dict(flat=False), doseq=True)
                if request.query_string else ''
            ),
            referrer=request.referrer,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception('Failed to save visitor campaign')

@app.before_request
def track_campaign():
    if not request.path.startswith('/static/') and not request.path.startswith('/.well-known'):
        log_campaign()
        
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = Staff.query.filter_by(id=session.get('admin_id')).first()

        if not user or not user.is_admin or not user.is_active:
            session.pop('admin_id', None)
            return redirect(url_for('admin_login'))

        return view(*args, **kwargs)
    return wrapped

@app.before_request
def protect_admin():
    if request.path.startswith('/cp') and request.endpoint not in ('admin_login', 'admin_register'):
        user = Staff.query.filter_by(id=session.get('admin_id')).first()

        if not user or not user.is_admin or not user.is_active:
            session.pop('admin_id', None)
            return redirect(url_for('admin_login'))

@app.before_request
def enforce_blocked_ips():
    if request.endpoint == 'static':
        return

    client_ip = request.remote_addr

    if not client_ip:
        return

    try:
        client_ip = str(ipaddress.ip_address(client_ip))
    except ValueError:
        return

    if BlockedIP.query.filter_by(ip_address=client_ip).first():
        abort(403)

@app.after_request
def log_request(response):
    if not request.path.startswith('/static/') and not request.path.startswith('/.well-known'):
        user_agent = request.headers.get('User-Agent', '')
        is_bot, bot_name = detect_bot(user_agent)
        
        log(
            level='success' if response.status_code < 400 else 'error',
            code=response.status_code,
            method=request.method,
            route=request.full_path.rstrip('?'),
            ip_address=request.remote_addr,
            message=f'{request.method} {request.full_path.rstrip("?")} returned {response.status_code}',
            user_agent=request.user_agent.string,
            is_bot=is_bot,
            bot_name=bot_name,
            username=session.get('username') or "GUEST"
        )
    return response

@app.route('/')
def index():
    blogs = Blog.query.limit(2).all()
    return render_template('index.html', blogs=blogs)

@app.route('/projects/graphic-designing')
def graphics():
    return render_template('graphics.html')


@app.route('/blogs/blog/<string:slug>')
def blog(slug):
    blog = Blog.query.filter_by(slug=slug).first_or_404()
    more_blogs = Blog.query.filter(Blog.id != blog.id).limit(2).all()
    return render_template('blog.html', blog=blog, more_blogs=more_blogs)

@app.route('/blogs')
def blogs():
    blogs = Blog.query.order_by(Blog.date.desc()).all()
    categories = db.session.query(Blog.category).distinct().filter(Blog.category.isnot(None)).all()
    categories = [category[0] for category in categories]
    return render_template('blogs.html', blogs=blogs, categories=categories)

@app.route('/cp/blogs')
def admin_blogs():
    blogs = Blog.query.order_by(Blog.id.desc()).all()
    return render_template('admin/blogs.html', blogs=blogs)

@app.route('/cp/blogs/add', methods=['GET', 'POST'])
def admin_add_blog():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        summary = request.form.get('summary', '').strip()
        content_markdown = request.form.get('content_markdown', '')
        category = request.form.get('category', '').strip()
        icon = request.form.get('icon', '').strip()
        tags = [tag.strip() for tag in request.form.get('tags', '').split(',') if tag.strip()]
        date = request.form.get('date')

        if not title:
            flash('Blog title is required!', 'error')
            return render_template('admin/edit_blog.html', blog=None)

        content_html = markdown2.markdown(
            content_markdown,
            extras=['fenced-code-blocks', 'tables']
        )

        content_html = re.sub(
            r'<p>\s*\+\+\s*</p>(.*?)<p>\s*\+\+\s*</p>',
            lambda match: f'<div class="blog-takeaway">{match.group(1).strip()}</div>',
            content_html,
            flags=re.DOTALL | re.IGNORECASE
        )

        content_html = re.sub(
            r'<a\s+href=',
            '<a target="_blank" rel="noopener noreferrer" href=',
            content_html,
            flags=re.IGNORECASE
        )

        base_slug = slugify(title.split('<span')[0])
        slug = base_slug
        counter = 1

        while Blog.query.filter_by(slug=slug).first():
            slug = f'{base_slug}-{counter}'
            counter += 1

        image = None
        file = request.files.get('blog-image')

        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(upload_path)
            image = f'/static/uploads/{filename}'

        blog = Blog(
            title=title,
            slug=slug,
            summary=summary,
            markdown=content_markdown,
            html=content_html,
            category=category,
            image=image,
            tags=json.dumps(tags),
            icon=icon,
            date=date
        )

        blog.compute_reading_time()
        db.session.add(blog)
        db.session.commit()

        flash('Blog created successfully!', 'success')
        return redirect(url_for('admin_edit_blog', slug=blog.slug))

    return render_template('admin/edit_blog.html', blog=None)

@app.route('/cp/blogs/delete/<slug>', methods=['POST'])
def admin_delete_blog(slug):
    blog = Blog.query.filter_by(slug=slug).first_or_404()

    db.session.delete(blog)
    db.session.commit()

    flash('Blog deleted successfully!', 'success')
    return redirect(url_for('admin_blogs'))

@app.route('/cp/blogs/edit/<string:slug>', methods=['GET', 'POST'])
def admin_edit_blog(slug):
    blog = Blog.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        summary = request.form.get('summary', '').strip()
        content_markdown = request.form.get('content_markdown', '')
        category = request.form.get('category', '')
        icon = request.form.get('icon', '')
        tags = [
            tag.strip()
            for tag in request.form.get('tags', '').split(',')
            if tag.strip()
        ]
        date = request.form.get('date', blog.date)

        content_html = re.sub(
            r'<a\s+href=',
            '<a target="_blank" rel="noopener noreferrer" href=',
            markdown2.markdown(content_markdown, extras=['fenced-code-blocks', 'tables'])
        )

        file = request.files.get('blog-image')

        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(upload_path)
            blog.image = f"/static/uploads/{filename}"

        blog.title = markdown2.markdown(title, extras=['fenced-code-blocks', 'tables'])
        blog.summary = markdown2.markdown(summary, extras=['fenced-code-blocks', 'tables'])
        blog.markdown = content_markdown
        blog.html = content_html
        blog.category = category
        blog.tags = json.dumps(tags)
        blog.icon = icon
        blog.date = date

        blog.compute_reading_time()

        db.session.commit()
        flash('Blog edited successfully!', 'success')

        return redirect(url_for('admin_edit_blog', slug=blog.slug))

    return render_template('admin/edit_blog.html', blog=blog, slug=blog.slug)

@app.errorhandler(404)
def page_not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('errors/500.html'), 500

@app.errorhandler(401)
def unauthorized(error):
    return render_template('errors/401.html'), 401

@app.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403

@app.route('/api/contact', methods=['POST'])
@captcha_verify
def contact_api():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    subject = data.get('subject')
    message = data.get('message')
    
    if not email or not message:
        return jsonify({'error':'Email and message are required'}), 400
    
    new_message = Message(
        name=name or '',
        email=email or '',
        subject=subject or '',
        message=message or ''
    )
    try:
        db.session.add(new_message)
        db.session.commit()
        return jsonify({'success':True, "msg":"Your message has been received successfully"}), 200
    except Exception as e:
        
        return jsonify({'error':'An error occured on our end. Please try again later'}), 500

@app.route('/projects')
def get_projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('projects.html', projects=projects)

@app.route('/cp/projects')
@admin_required
def admin_projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('admin/projects.html', projects=projects)

@app.route('/cp/projects/add', methods=['GET', 'POST'])
@admin_required
def admin_add_project():
    if request.method == 'POST':
        tech_input = request.form.get('tech', '')
        tech_list = [t.strip() for t in tech_input.split(',') if t.strip()]
        
        project = Project(
            name=request.form.get('name'),
            date=request.form.get('date'),
            type=request.form.get('type'),
            desc=request.form.get('desc'),
            img=request.form.get('img'),
            site=request.form.get('site'),
            code=request.form.get('code'),
            tech=tech_list
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully!', 'success')
        return redirect(url_for('admin_projects'))
    return render_template('admin/project_edit.html', project=None)

@app.route('/cp/projects/edit/<int:project_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST':
        tech_input = request.form.get('tech', '')
        tech_list = [t.strip() for t in tech_input.split(',') if t.strip()]
        
        project.name = request.form.get('name')
        project.date = request.form.get('date')
        project.type = request.form.get('type')
        project.desc = request.form.get('desc')
        project.img = request.form.get('img')
        project.site = request.form.get('site')
        project.code = request.form.get('code')
        project.tech = tech_list
        
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('admin_projects'))
    return render_template('admin/project_edit.html', project=project)

@app.route('/cp/projects/delete/<int:project_id>', methods=['POST'])
@admin_required
def admin_delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('admin_projects'))

@app.route('/cp')
def admin_dashboard():
    active_logs = Log.query.filter(Log.deleted_at.is_(None))

    page_views = active_logs.filter(
        Log.method == 'GET',
        ~Log.route.like('/static/%'),
        ~Log.route.like('/api/%')
    )

    total_requests = active_logs.count()
    total_page_views = page_views.count()

    unique_visitors = db.session.query(
        func.count(func.distinct(Log.ip_address))
    ).filter(
        Log.deleted_at.is_(None),
        Log.ip_address.isnot(None),
        Log.method == 'GET',
        ~Log.route.like('/static/%'),
        ~Log.route.like('/api/%')
    ).scalar() or 0

    bot_requests = active_logs.filter_by(is_bot=True).count()
    human_requests = total_requests - bot_requests

    total_errors = active_logs.filter(
        Log.code.cast(db.String).like('4%') |
        Log.code.cast(db.String).like('5%')
    ).count()

    total_campaign_visits = VisitorCampaign.query.count()

    total_sources = db.session.query(
        func.count(func.distinct(VisitorCampaign.source))
    ).filter(
        VisitorCampaign.source.isnot(None),
        VisitorCampaign.source != ''
    ).scalar() or 0

    top_sources = db.session.query(
        VisitorCampaign.source,
        func.count(VisitorCampaign.id).label('visits')
    ).filter(
        VisitorCampaign.source.isnot(None),
        VisitorCampaign.source != ''
    ).group_by(
        VisitorCampaign.source
    ).order_by(
        func.count(VisitorCampaign.id).desc()
    ).limit(5).all()

    recent_logs = active_logs.order_by(
        Log.created_at.desc()
    ).limit(5).all()

    recent_campaigns = VisitorCampaign.query.order_by(
        VisitorCampaign.created_at.desc()
    ).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        total_requests=total_requests,
        total_page_views=total_page_views,
        unique_visitors=unique_visitors,
        total_errors=total_errors,
        total_campaign_visits=total_campaign_visits,
        total_sources=total_sources,
        top_sources=top_sources,
        recent_logs=recent_logs,
        recent_campaigns=recent_campaigns,
        bot_requests=bot_requests,
        human_requests=human_requests
    )

@app.route('/cp/logs')
def admin_logs():
    code = request.args.get('code', '').strip()
    route = request.args.get('route', '').strip()
    ip = request.args.get('ip', '').strip()
    level = request.args.get('level', '').strip()
    traffic_type = request.args.get('traffic_type', '').strip()

    query = Log.query.filter(Log.deleted_at.is_(None))

    if code:
        query = query.filter(Log.code == code)

    if route:
        query = query.filter(Log.route.ilike(f'%{route}%'))

    if ip:
        query = query.filter(Log.ip_address.ilike(f'%{ip}%'))

    if level:
        query = query.filter(Log.level == level)

    if traffic_type:
        query = query.filter(Log.traffic_type == traffic_type)

    logs = query.order_by(Log.created_at.desc()).limit(500).all()
    blocked_ips = BlockedIP.query.order_by(BlockedIP.created_at.desc()).all()

    return render_template(
        'admin/logs.html',
        logs=logs,
        code=code,
        route=route,
        ip=ip,
        level=level,
        traffic_type=traffic_type,
        blocked_ips=blocked_ips
    )

@app.route('/cp/logs/delete', methods=['POST'])
def admin_delete_logs():
    Log.query.filter(Log.deleted_at.is_(None)).update(
        {Log.deleted_at: datetime.utcnow() + timedelta(hours=delta)},
        synchronize_session=False
    )
    db.session.commit()
    flash('All logs deleted successfully.', 'success')
    return redirect(url_for('admin_logs'))

@app.route('/cp/api/logs/delete-selected', methods=['POST'])
def admin_delete_selected_logs():
    ids = (request.get_json(silent=True) or {}).get('ids', [])
    if not isinstance(ids, list) or not ids:
        return jsonify({'error': 'No logs selected.'}), 400

    ids = [str(i).strip() for i in ids if str(i).strip()]
    if not ids:
        return jsonify({'error': 'No valid log IDs.'}), 400

    count = Log.query.filter(Log.id.in_(ids), Log.deleted_at.is_(None)).update(
        {Log.deleted_at: datetime.utcnow() + timedelta(hours=delta)}, synchronize_session=False
    )
    db.session.commit()
    return jsonify({'success': True, 'deleted': count})


@app.route('/cp/api/logs/delete-all', methods=['POST'])
def admin_delete_all_logs():
    count = Log.query.filter(Log.deleted_at.is_(None)).update(
        {Log.deleted_at: datetime.utcnow() + timedelta(hours=delta)}, synchronize_session=False
    )
    db.session.commit()
    return jsonify({'success': True, 'deleted': count})


@app.route('/cp/api/block-ip', methods=['POST'])
def admin_block_ip():
    data = request.get_json(silent=True) or {}
    ip = (data.get('ip') or '').strip()

    try:
        ip = str(ipaddress.ip_address(ip))
    except ValueError:
        return jsonify({'error': 'Invalid IP address.'}), 400

    if ip == request.remote_addr:
        return jsonify({'error': 'You cannot block your current IP address.'}), 400

    if BlockedIP.query.filter_by(ip_address=ip).first():
        return jsonify({'success': True, 'message': 'This IP address is already blocked.'})

    db.session.add(BlockedIP(ip_address=ip))
    db.session.commit()

    return jsonify({'success': True, 'message': f'IP address {ip} blocked successfully.'})

@app.route('/cp/blocked-ips/<int:ip_id>/delete', methods=['POST'])
def admin_unblock_ip(ip_id):
    blocked_ip = db.session.get(BlockedIP, ip_id)

    if not blocked_ip:
        flash('Blocked IP address not found.', 'error')
        return redirect(url_for('admin_logs'))

    db.session.delete(blocked_ip)
    db.session.commit()

    flash('IP address unblocked successfully.', 'success')
    return redirect(url_for('admin_logs'))

@app.route('/cp/campaigns')
def admin_campaigns():
    source = request.args.get('source', '').strip()
    medium = request.args.get('medium', '').strip()
    campaign = request.args.get('campaign', '').strip()

    query = VisitorCampaign.query

    if source:
        query = query.filter(VisitorCampaign.source.ilike(f'%{source}%'))
    if medium:
        query = query.filter(VisitorCampaign.medium.ilike(f'%{medium}%'))
    if campaign:
        query = query.filter(VisitorCampaign.campaign.ilike(f'%{campaign}%'))

    campaigns = query.order_by(VisitorCampaign.created_at.desc()).limit(500).all()

    return render_template(
        'admin/campaigns.html',
        campaigns=campaigns,
        source=source,
        medium=medium,
        campaign=campaign
    )

@app.route('/cp/messages')
def admin_messages():
    messages = Message.query.order_by(Message.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages)

@app.route('/cp/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'error')
        elif Staff.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            staff = Staff(email=email, password=generate_password_hash(password))
            db.session.add(staff)
            db.session.commit()
            session['admin_id'] = staff.id
            return redirect(url_for('admin_dashboard'))

    return render_template('admin/register.html')

@app.route('/cp/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        staff = Staff.query.filter_by(email=email).first()

        if not staff:
            flash('Invalid account.', 'error')
            log(level='error', code=400, method=request.method, route=request.path, ip_address=request.remote_addr, message='Invalid account accessed.', user_agent=request.user_agent.string)
            return redirect(url_for('admin_login'))

        if not staff.is_active:
            flash('Your account is inactive. Please contact support.', 'error')
            log(level='error', code=403, method=request.method, route=request.path, ip_address=request.remote_addr, message='Inactive account accessed.', user_agent=request.user_agent.string)
            return redirect(url_for('admin_login'))

        if not staff.is_admin:
            flash('Unauthorized entry.', 'error')
            log(level='error', code=403, method=request.method, route=request.path, ip_address=request.remote_addr, message='Admin access denied.', user_agent=request.user_agent.string)
            return redirect(url_for('admin_login'))

        if not check_password_hash(staff.password, password):
            flash('Invalid email or password.', 'error')
            log(level='error', code=401, method=request.method, route=request.path, ip_address=request.remote_addr, message=f'Invalid password for {email}.', user_agent=request.user_agent.string)
            return redirect(url_for('admin_login'))

        session.clear()
        session['admin_id'] = staff.id
        session['username'] = staff.username
        log(level='success', code=200, method=request.method, route=request.path, ip_address=request.remote_addr, message=f'Admin login successful: {email}', user_agent=request.user_agent.string)
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/login.html')

@app.route('/cp/staff')
@admin_required
def admin_staff():
    staff = Staff.query.order_by(Staff.created_at.desc()).all()
    return render_template('admin/staff.html', staff=staff)

@app.route('/cp/staff/<staff_id>/toggle', methods=['POST'])
def admin_toggle_staff(staff_id):
    staff = Staff.query.filter_by(id=staff_id).first_or_404()

    if staff.id == session.get('admin_id'):
        flash('You cannot deactivate your own account.', 'error')
    else:
        staff.is_active = not staff.is_active
        db.session.commit()
        flash(f"Staff account {'activated' if staff.is_active else 'deactivated'}.", 'success')

    return redirect(url_for('admin_staff'))

@app.route('/cp/staff/<staff_id>/delete', methods=['POST'])
def admin_delete_staff(staff_id):
    staff = Staff.query.filter_by(id=staff_id).first_or_404()

    if staff.id == session.get('admin_id'):
        flash('You cannot delete your own account.', 'error')
    else:
        db.session.delete(staff)
        db.session.commit()
        flash('Staff account deleted.', 'success')

    return redirect(url_for('admin_staff'))

@app.route('/cp/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/cp/init')
def add_projects():
    for p in reversed(projects):
        if not Project.query.filter_by(name=p['name']).first():
            db.session.add(Project(**p))
    db.session.commit()
    return jsonify({'sucess':f'added {len(projects)}'})



@app.route('/sitemap.xml')
def sitemap():
    urls = [
        url_for(rule.endpoint, _external=True)
        for rule in app.url_map.iter_rules()
        if '/cp/' not in rule.rule
        and rule.endpoint != 'static'
        and rule.methods.intersection({'GET', 'HEAD'})
        and '<' not in rule.rule
    ]

    urls.extend(
        url_for('blog', slug=blog.slug, _external=True)
        for blog in Blog.query.filter_by(deleted_at=None).all()
    )

    return Response(
        render_template('sitemap.xml', pages=list(dict.fromkeys(urls))),
        mimetype='application/xml'
    )
    
@app.route('/rss.xml')
def rss():
    from html import unescape
    from re import sub
    from xml.sax.saxutils import escape
    from email.utils import format_datetime
    from datetime import timezone

    blogs = Blog.query.filter_by(deleted_at=None).order_by(Blog.created_at.desc()).limit(50).all()
    base_url = request.url_root.rstrip('/')

    def clean(value):
        value = unescape(str(value or ''))
        return sub(r'\s+', ' ', sub(r'<[^>]+>', ' ', value)).strip()

    items = []

    for blog in blogs:
        link = base_url + url_for('blog', slug=blog.slug)
        pub_date = ''

        if blog.created_at:
            date = blog.created_at.replace(tzinfo=timezone.utc)
            pub_date = f'<pubDate>{format_datetime(date, usegmt=True)}</pubDate>'

        description = clean(getattr(blog, 'excerpt', None) or getattr(blog, 'content', None))

        items.append(
            f'<item>'
            f'<title>{escape(clean(blog.title))}</title>'
            f'<link>{escape(link)}</link>'
            f'<guid isPermaLink="true">{escape(link)}</guid>'
            f'<description>{escape(description)}</description>'
            f'{pub_date}'
            f'</item>'
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f'<title>{escape("Lutan Tech Blog")}</title>'
        f'<link>{escape(base_url)}</link>'
        f'<description>{escape("Latest blog posts")}</description>'
        f'{"".join(items)}'
        '</channel></rss>'
    )

    return Response(xml, mimetype='application/rss+xml; charset=utf-8')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True, port=5000)