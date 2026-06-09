from flask import Blueprint

bp = Blueprint('social', __name__, url_prefix='/social')

from app.social import routes  # noqa: E402, F401
