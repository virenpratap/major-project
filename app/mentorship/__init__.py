from flask import Blueprint

bp = Blueprint('mentorship', __name__, url_prefix='/mentorship')

from app.mentorship import routes  # noqa: F401
