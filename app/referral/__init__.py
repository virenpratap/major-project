from flask import Blueprint

bp = Blueprint('referral', __name__, url_prefix='/referral')

from app.referral import routes  # noqa: E402, F401
