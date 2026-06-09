from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.recommend import bp
from core.recommendation_engine import get_recommendations


@bp.route('/')
@login_required
def index():
    return render_template('recommend/suggestions.html')


@bp.route('/api/suggestions')
@login_required
def suggestions():
    rec_type = request.args.get('type', 'all')
    limit = request.args.get('limit', 10, type=int)

    results = get_recommendations(current_user.id, rec_type, limit)
    return jsonify(results)
@bp.route('/api/connect', methods=['POST'])
@login_required
def connect():
    data = request.get_json()
    target_id = data.get('target_id')
    
    if not target_id:
        return jsonify({'error': 'Target user ID is required'}), 400
        
    if target_id == current_user.id:
        return jsonify({'error': 'You cannot connect with yourself'}), 400

    from app.models import Connection, User
    from app.extensions import db
    from core.notifications import notify_connection_request
    
    # Check for existing connection
    existing = Connection.query.filter(
        ((Connection.user_id == current_user.id) & (Connection.target_id == target_id)) |
        ((Connection.user_id == target_id) & (Connection.target_id == current_user.id))
    ).first()
    
    if existing:
        return jsonify({'error': f'Connection already exists (Status: {existing.status})'}), 400

    conn = Connection(user_id=current_user.id, target_id=target_id, status='pending')
    db.session.add(conn)
    db.session.commit()
    
    # Notify target
    sender_name = current_user.profile.full_name if current_user.profile else current_user.username
    notify_connection_request(target_id, sender_name)
    
    return jsonify({'message': 'Connection request sent successfully'})
