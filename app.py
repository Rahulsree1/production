from pathlib import Path
import firebase_admin
from firebase_admin import firestore, credentials
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
from datetime import datetime, timedelta, timezone
import cloudinary
import cloudinary.uploader
import cloudinary.api
import secrets
from dotenv import load_dotenv

app = Flask(__name__, static_folder='build', static_url_path='')
CORS(app)

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Initialize Firebase
cred = credentials.Certificate("./Secret-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize Cloudinary
cloudinary.config(
    cloud_name="dsirtlyyn",
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

sessions = {}  # session_token: {username, expiry}
ADMIN_SECRET = os.environ.get("ADMIN_SECRET")

@app.route('/upload-image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(file)
        
        return jsonify({
            'url': result['secure_url'],
            'public_id': result['public_id']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cards', methods=['GET'])
def get_cards():
    cards_ref = db.collection('Questcards')
    docs = cards_ref.stream()
    cards = []
    for doc in docs:
        card = doc.to_dict()
        card['id'] = doc.id
        cards.append(card)
    print(cards)
    return jsonify(cards)

@app.route('/cards', methods=['POST'])
def create_card():
    data = request.json
    data['lastModified'] = datetime.utcnow().isoformat()
    
    # Ensure category is not empty
    if not data.get('category'):
        data['category'] = 'Uncategorized'
    
    # If card has an ID, it's an update
    if 'id' in data and data['id']:
        card_id = data.pop('id')  # Remove id from data before saving
        db.collection('Questcards').document(card_id).set(data)
        return jsonify({'id': card_id}), 200
    else:
        # It's a new card
        doc_ref = db.collection('Questcards').add(data)
        return jsonify({'id': doc_ref[1].id}), 201

@app.route('/cards/<string:card_id>', methods=['PUT'])
def update_card(card_id):
    data = request.json
    data['lastModified'] = datetime.utcnow().isoformat()
    
    # Ensure category is not empty
    if not data.get('category'):
        data['category'] = 'Uncategorized'
    
    db.collection('Questcards').document(card_id).set(data, merge=True)
    return jsonify({'success': True})

@app.route('/cards/<string:card_id>', methods=['DELETE'])
def delete_card(card_id):
    db.collection('Questcards').document(card_id).delete()
    return jsonify({'success': True})

@app.route('/tags', methods=['GET'])
def get_tags():
    tags_ref = db.collection('QuestTags')
    docs = tags_ref.stream()
    tags = []
    for doc in docs:
        data = doc.to_dict()
        tags.append({'id': doc.id, 'displayName': data.get('displayName', ''), 'order': data.get('order', 0)})
    return jsonify(tags)

@app.route('/tags', methods=['POST'])
def set_tag():
    data = request.json
    tag_id = data.get('id')
    display_name = data.get('displayName')
    order = data.get('order', 0)
    if not display_name:
        return jsonify({'error': 'displayName is required'}), 400
    if tag_id:
        db.collection('QuestTags').document(tag_id).set({
            'displayName': display_name,
            'order': order,
        })
        return jsonify({'id': tag_id, 'displayName': display_name, 'order': order})
    else:
        doc_ref = db.collection('QuestTags').add({
            'displayName': display_name,
            'order': order,
        })
        return jsonify({'id': doc_ref[1].id, 'displayName': display_name, 'order': order})

@app.route('/queries', methods=['GET'])
def get_queries():
    queries_ref = db.collection('Queries')
    docs = queries_ref.stream()
    queries = []
    for doc in docs:
        data = doc.to_dict()
        queries.append({
            'id': doc.id,
            'query': data.get('query', ''),
            'tags': data.get('tags', []),
            'type': data.get('type', 'query'),
            'icon': data.get('icon', None),
            'status': data.get('status', 'published'),
            'order': data.get('order', 0),
            'timestamp': data.get('timestamp', None),
        })
    # Sort by order
    queries.sort(key=lambda x: x['order'])
    return jsonify(queries)

@app.route('/queries', methods=['POST'])
def add_query():
    data = request.json
    query_text = data.get('query')
    tags = data.get('tags', [])
    qtype = data.get('type', 'query')
    icon = data.get('icon', None)
    status = data.get('status', 'draft')
    order = data.get('order', 0)
    timestamp = datetime.utcnow().isoformat()
    if not query_text:
        return jsonify({'error': 'Query is required'}), 400
    doc_ref = db.collection('Queries').add({
        'query': query_text,
        'tags': tags,
        'type': qtype,
        'icon': icon,
        'status': status,
        'order': order,
        'timestamp': timestamp,
    })
    return jsonify({'id': doc_ref[1].id, 'query': query_text, 'tags': tags, 'type': qtype, 'icon': icon, 'status': status, 'order': order, 'timestamp': timestamp})

@app.route('/queries/<string:query_id>', methods=['PUT'])
def update_query(query_id):
    data = request.json
    data['timestamp'] = datetime.utcnow().isoformat()
    db.collection('Queries').document(query_id).set(data, merge=True)
    return jsonify({'success': True, 'timestamp': data['timestamp']})

@app.route('/queries/<string:query_id>', methods=['DELETE'])
def delete_query(query_id):
    db.collection('Queries').document(query_id).delete()
    return jsonify({'success': True})

@app.route('/users', methods=['GET'])
def get_users():
    users_ref = db.collection('Users')
    docs = users_ref.stream()
    users = []
    for doc in docs:
        data = doc.to_dict()
        users.append({'id': doc.id, 'username': data.get('username', '')})
    return jsonify(users)

@app.route('/users', methods=['POST'])
def add_user():
    admin_secret = request.headers.get('X-ADMIN-SECRET')
    if admin_secret != ADMIN_SECRET:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    # Check if username exists
    users_ref = db.collection('Users')
    existing = users_ref.where('username', '==', username).get()
    if existing:
        return jsonify({'error': 'Username already exists'}), 400
    doc_ref = users_ref.add({'username': username, 'password': password})
    return jsonify({'id': doc_ref[1].id, 'username': username})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'username and password required'}), 400
    users_ref = db.collection('Users')
    docs = users_ref.where('username', '==', username).get()
    if not docs:
        return jsonify({'error': 'Invalid username or password'}), 401
    user = docs[0].to_dict()
    if user.get('password') != password:
        return jsonify({'error': 'Invalid username or password'}), 401
    # Create session token
    token = secrets.token_urlsafe(32)
    # Always use UTC for expiry
    expiry = datetime.now(timezone.utc) + timedelta(minutes=30)  # UTC time
    sessions[token] = {'username': username, 'expiry': expiry}
    return jsonify({'token': token, 'expiry': expiry.isoformat() + 'Z'})  # Explicitly mark as UTC

@app.route('/validate-session', methods=['POST'])
def validate_session():
    data = request.json
    token = data.get('token')
    if not token or token not in sessions:
        return jsonify({'valid': False, 'reason': 'Invalid session'}), 401
    session = sessions[token]
    if datetime.utcnow() > session['expiry']:
        del sessions[token]
        return jsonify({'valid': False, 'reason': 'Session expired'}), 401
    return jsonify({'valid': True, 'username': session['username']})



@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    print("hi")
    target = os.path.join(app.static_folder, path)
    if path and os.path.exists(target):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def not_found(e):
    print("fallback to React from 404")
    return send_from_directory(app.static_folder, 'index.html')




#if __name__ == '__main__':
#    
#    app.run(debug=True) 

