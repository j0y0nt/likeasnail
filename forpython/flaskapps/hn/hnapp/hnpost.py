from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from hnapp.auth import login_required
from hnapp.db import get_db
from urllib.parse import urlparse

bp = Blueprint('hnpost', __name__)

@bp.route('/')
def index():
    db = get_db()
    posts = db.execute(
        'SELECT p.id, p.user_id, p.title, p.url, p.body, p.points, p.created, u.username'
        ' FROM post p JOIN huser u ON p.user_id = u.id'
        ' ORDER BY p.points DESC'
    ).fetchall()
    return render_template('post/index.html', posts=posts, urlparse=urlparse)


@bp.route('/new', methods=['GET'])
def new():
    db = get_db()
    posts = db.execute(
        'SELECT p.id, p.user_id, p.title, p.url, p.body, p.points, p.created, u.username'
        ' FROM post p JOIN huser u ON p.user_id = u.id'
        ' ORDER BY p.created DESC'
    ).fetchall()
    return render_template('post/new.html', posts=posts,urlparse=urlparse)


@bp.route('/vote/<int:id>', methods=['GET'])
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

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_post(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('post.index'))
