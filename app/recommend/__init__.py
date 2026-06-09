from flask import Blueprint

bp = Blueprint('recommend', __name__, url_prefix='/recommend')

from app.recommend import routes  # noqa: E402, F401
