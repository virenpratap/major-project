from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_login import LoginManager

# Initialize extensions (bound to app in create_app)
db = SQLAlchemy()
socketio = SocketIO()
login_manager = LoginManager()

login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
