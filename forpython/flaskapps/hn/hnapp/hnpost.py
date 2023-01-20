
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from hnapp.auth import login_required
from hnapp.db import get_db
from urllib.parse import urlparse
from datetime import *

bp = Blueprint('hnpost', __name__)

@bp.route('/')
def index():
    db = get_db()
    posts = db.execute(
        'SELECT p.id, p.user_id, p.title, p.url, p.body, p.points,'
        ' p.created, p.comment_count, u.username'
        ' FROM post p JOIN huser u ON p.user_id = u.id'
        ' ORDER BY p.points DESC'
    ).fetchall()
    return render_template('post/index.html',
                           posts=posts,
                           urlparse=urlparse)


def format_date(datestr):
    #datetime.strptime(datestr, '%y-%m-%d %H:%M:%S')
    dt = datetime.fromisoformat(datestr)
    return dt.strftime('%B %d, %Y')


@bp.route('/user', methods=['GET'])
def user():
    if request.method == 'GET':
        username = request.args.get('id', '')
        db = get_db()
        user = db.execute(
            'SELECT id, username, email, created_at, about, karma'
            ' from huser where username = ?',
            (username,)
        ).fetchone()
        return render_template('user/profile.html',
                               huser = user,
                               dateformatter=format_date)


@bp.route('/new', methods=['GET'])
def new():
    db = get_db()
    posts = db.execute(
        'SELECT p.id, p.user_id, p.title, p.url, p.body, p.points,'
        ' p.created, u.username'
        ' FROM post p JOIN huser u ON p.user_id = u.id'
        ' ORDER BY p.created DESC'
    ).fetchall()
    return render_template('post/new.html',
                           posts=posts,
                           urlparse=urlparse)


@bp.route('/vote/<int:id>', methods=['GET'])
@login_required
def vote(id):
    print(id)
    db = get_db()
    posts = db.execute(
        'UPDATE post SET points = points + 1 WHERE id = ?',
        (id,)
    )
    db.commit()
    return redirect(url_for('hnpost.index'))


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        url = request.form['url']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO post (title, url, body, user_id)'
                ' VALUES (?, ?, ?, ?)',
                (title, url, body, g.user['id'])
            )
            db.commit()
            return redirect(url_for('hnpost.index'))

    return render_template('post/create.html')


def get_post(id, check_author=True):
    post = get_db().execute(
        'SELECT p.id, title, url, body, created, user_id, username'
        ' FROM post p JOIN huser u ON p.user_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post['user_id'] != g.user['id']:
        abort(403)

    return post


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE post SET title = ?, body = ?'
                ' WHERE id = ?',
                (title, body, id)
            )
            db.commit()
            return redirect(url_for('hnpost.index'))

    return render_template('post/update.html', post=post)

def get_comments(post_id):
    comments = get_db().execute(
        'SELECT id, body, created, points, post_id, parent_id,'
        ' user_id, username'
        ' FROM comment c'
        ' WHERE c.parent_id = ?',
        (post_id,)
    ).fetchall()

    if comments is None:
        comments = []
        
    return comments    

def show_nice_duration(d_time):
    delta = datetime.now() - d_time
    
    if delta.days != 0:
        return f"{delta.days} days ago"
    elif delta.seconds is not None and delta.seconds >= 3600:
        return f"{int(delta.seconds / 3600)} hour ago"
    elif delta.seconds is not None and delta.seconds >= 60:
        return f"{int(delta.seconds / 60)} minutes ago"
    elif delta.seconds != 0:
        return f"{delta.seconds} second ago"

    return d_time


def get_comment_children(comment_id):
    children = get_db().execute(
         'SELECT id, body, created, points, post_id, parent_id,'
        ' user_id, username'
        ' FROM comment c'
        ' WHERE c.parent_id = ?',
        (int(comment_id),)
    ).fetchall()
    return children


@bp.route("/item/<int:id>", methods=('GET',))
def get_item(id):
    post = get_post(id, check_author=False)
    comments = get_comments(id)
    return render_template('post/comment.html',
                           post=post,
                           comments=comments,
                           urlparse=urlparse,
                           dtformatter=show_nice_duration,
                           get_comment_children=get_comment_children)


def get_comment(comment_id):
    comment = get_db().execute(
        'SELECT id, body, created, points, post_id, parent_id,'
        ' user_id, username'
        ' FROM comment c'
        ' WHERE c.id = ?',
        (int(comment_id),)
    ).fetchone()
        
    return comment


@bp.route("/reply", methods=('GET',))
@login_required
def reply():
    if request.method == 'GET':
        post_id = request.args.get('item', '')
        comment_id = request.args.get('id', '')
        post = get_post(post_id, check_author=False)
        comment = get_comment(comment_id)
    return render_template('post/reply.html',
                           post=post,
                           comment=comment,
                           urlparse=urlparse,
                           dtformatter=show_nice_duration)


@bp.route("/comment", methods=('POST',))
@login_required
def add_comment():
    if request.method == 'POST':
        text = request.form['text']
        post_id = request.form['post_id']
        parent = request.form['parent']
        error = None
        
        if not text:
            error = 'Comment is required.'

        if not post_id:
            error = 'Post ID is required.'
        
        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute('INSERT INTO comment '
                       '(body, post_id, parent_id, user_id, username) '
                       'VALUES (?, ?, ?, ?, ?) ',
                       (text, int(post_id), int(parent), int(g.user['id']),
                        g.user['username'])
            )
            db.execute('UPDATE post'
                       ' SET comment_count = comment_count + 1'
                       ' WHERE id = ?',
                       (int(post_id),)
            )
            db.commit()
            
            return redirect(url_for('hnpost.get_item',id=post_id))

    post = get_post(id, check_author=False)    
    return render_template('post/comment.html', post=post,
                           urlparse=urlparse)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_post(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('post.index'))
