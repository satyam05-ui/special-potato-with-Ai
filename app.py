from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from functools import wraps

app = Flask(__name__)
# Enable CORS for the frontend
CORS(app)

app.config['SECRET_KEY'] = 'dev-secret-key-carbonwise-123'
DB_FILE = 'carbonwise.db'

# Constants for calculations
TRANSPORT_FACTORS = {'ev': 0.05, 'ice': 0.21, 'transit': 0.08, 'walking': 0.0, 'cycling': 0.0, 'flight': 0.28}
ENERGY_FACTORS = {'mixed': 0.4, 'renewable': 0.05, 'coal': 0.8, 'nuclear': 0.02, 'biomass': 0.2}
DIET_BASE_KG = {'omnivore': 150, 'vegetarian': 90, 'vegan': 60, 'pescatarian': 110, 'carnivore': 200}

# Static Challenges
CHALLENGES = [
    {"code": "LED_SWAP", "title": "LED Retrofit", "description": "Upgrade primary facility lighting to High-Efficiency LEDs.", "points": 50},
    {"code": "RENEWABLE_OPT", "title": "Renewable Sourcing", "description": "Opt-in to a 100% renewable grid mix with your energy provider.", "points": 150},
    {"code": "MEAT_REDUCTION", "title": "Supply Chain Diet", "description": "Reduce high-impact meat consumption in operational catering by 50%.", "points": 100}
]

# --- Database Setup ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_FILE):
        conn = get_db()
        c = conn.cursor()
        c.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, password TEXT, points INTEGER DEFAULT 0, created_at TEXT)''')
        c.execute('''CREATE TABLE calculations (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, transport_kg REAL, energy_kg REAL, diet_kg REAL, total_kg REAL, timestamp TEXT)''')
        c.execute('''CREATE TABLE user_challenges (user_id INTEGER, challenge_code TEXT, timestamp TEXT)''')
        c.execute('''CREATE TABLE actions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action_type TEXT, ref_code TEXT, points_awarded INTEGER, timestamp TEXT)''')
        conn.commit()
        conn.close()
        print("Database initialized.")

# --- Authentication Middleware ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'detail': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            conn = get_db()
            current_user = conn.execute('SELECT * FROM users WHERE id = ?', (data['user_id'],)).fetchone()
            conn.close()
            if not current_user:
                raise Exception()
        except:
            return jsonify({'detail': 'Token is invalid or expired'}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated

# --- Routes ---
@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password or len(password) < 8:
        return jsonify({'detail': 'Invalid inputs. Password must be at least 8 characters.'}), 400

    hashed_password = generate_password_hash(password)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (name, email, password, created_at) VALUES (?, ?, ?, ?)', 
                       (name, email, hashed_password, datetime.now().isoformat()))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        token = jwt.encode({'user_id': user_id, 'exp': datetime.utcnow() + timedelta(days=7)}, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({'access_token': token}), 201
    except sqlite3.IntegrityError:
        return jsonify({'detail': 'Email already registered.'}), 400

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (data.get('email'),)).fetchone()
    conn.close()

    if not user or not check_password_hash(user['password'], data.get('password')):
        return jsonify({'detail': 'Invalid email or password'}), 401

    token = jwt.encode({'user_id': user['id'], 'exp': datetime.utcnow() + timedelta(days=7)}, app.config['SECRET_KEY'], algorithm="HS256")
    return jsonify({'access_token': token}), 200

@app.route('/auth/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify({
        'id': current_user['id'],
        'name': current_user['name'],
        'email': current_user['email'],
        'points': current_user['points'],
        'created_at': current_user['created_at']
    }), 200

@app.route('/calculations', methods=['POST'])
@token_required
def calculate(current_user):
    data = request.json
    
    # Process Matrix
    transport_kg = data.get('distance_km', 0) * TRANSPORT_FACTORS.get(data.get('transport_type', 'ev'), 0.05) * 30 # monthly approx
    energy_kg = data.get('energy_kwh', 0) * ENERGY_FACTORS.get(data.get('grid_type', 'mixed'), 0.4)
    diet_kg = DIET_BASE_KG.get(data.get('diet_type', 'omnivore'), 150)
    
    total_kg = round(transport_kg + energy_kg + diet_kg, 2)
    
    conn = get_db()
    conn.execute('''INSERT INTO calculations (user_id, transport_kg, energy_kg, diet_kg, total_kg, timestamp) 
                    VALUES (?, ?, ?, ?, ?, ?)''', 
                 (current_user['id'], transport_kg, energy_kg, diet_kg, total_kg, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    return jsonify({
        'total_kg': total_kg,
        'breakdown': {
            'transport': round(transport_kg, 2),
            'energy': round(energy_kg, 2),
            'diet': round(diet_kg, 2)
        }
    }), 201

@app.route('/calculations/latest', methods=['GET'])
@token_required
def get_latest_calculation(current_user):
    conn = get_db()
    calc = conn.execute('SELECT * FROM calculations WHERE user_id = ? ORDER BY id DESC LIMIT 1', (current_user['id'],)).fetchone()
    conn.close()

    if not calc:
        return jsonify({'detail': 'No calculations found'}), 404

    return jsonify({
        'total_kg': calc['total_kg'],
        'breakdown': {
            'transport': calc['transport_kg'],
            'energy': calc['energy_kg'],
            'diet': calc['diet_kg']
        }
    }), 200

@app.route('/challenges', methods=['GET'])
@token_required
def get_challenges(current_user):
    conn = get_db()
    completed = [row['challenge_code'] for row in conn.execute('SELECT challenge_code FROM user_challenges WHERE user_id = ?', (current_user['id'],)).fetchall()]
    conn.close()

    result = []
    for ch in CHALLENGES:
        challenge_data = ch.copy()
        challenge_data['completed'] = ch['code'] in completed
        result.append(challenge_data)

    return jsonify(result), 200

@app.route('/challenges/<code_id>/complete', methods=['POST'])
@token_required
def complete_challenge(current_user, code_id):
    challenge = next((c for c in CHALLENGES if c['code'] == code_id), None)
    if not challenge:
        return jsonify({'detail': 'Challenge not found'}), 404

    conn = get_db()
    cursor = conn.cursor()
    
    # Check if already completed
    existing = cursor.execute('SELECT * FROM user_challenges WHERE user_id = ? AND challenge_code = ?', (current_user['id'], code_id)).fetchone()
    if existing:
        conn.close()
        return jsonify({'detail': 'Protocol already executed.'}), 400

    # Award points & log action
    new_points = current_user['points'] + challenge['points']
    cursor.execute('UPDATE users SET points = ? WHERE id = ?', (new_points, current_user['id']))
    cursor.execute('INSERT INTO user_challenges (user_id, challenge_code, timestamp) VALUES (?, ?, ?)', (current_user['id'], code_id, datetime.now().isoformat()))
    cursor.execute('INSERT INTO actions (user_id, action_type, ref_code, points_awarded, timestamp) VALUES (?, ?, ?, ?, ?)', 
                   (current_user['id'], 'CHALLENGE', code_id, challenge['points'], datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

    return jsonify({
        'total_points': new_points,
        'points_awarded': challenge['points']
    }), 200

@app.route('/actions/undo', methods=['POST'])
@token_required
def undo_action(current_user):
    conn = get_db()
    cursor = conn.cursor()
    
    # Grab the last completed challenge
    last_action = cursor.execute('SELECT * FROM actions WHERE user_id = ? ORDER BY id DESC LIMIT 1', (current_user['id'],)).fetchone()
    
    if not last_action:
        conn.close()
        return jsonify({'detail': 'No recent actions to revert.'}), 400

    # Reverse points
    new_points = max(0, current_user['points'] - last_action['points_awarded'])
    cursor.execute('UPDATE users SET points = ? WHERE id = ?', (new_points, current_user['id']))
    
    # Remove from completions and delete the action log
    if last_action['action_type'] == 'CHALLENGE':
        cursor.execute('DELETE FROM user_challenges WHERE user_id = ? AND challenge_code = ?', (current_user['id'], last_action['ref_code']))
    
    cursor.execute('DELETE FROM actions WHERE id = ?', (last_action['id'],))
    
    conn.commit()
    conn.close()

    return jsonify({
        'total_points': new_points,
        'reverted_action': f"Challenge {last_action['ref_code']}"
    }), 200

if __name__ == '__main__':
    init_db()
    app.run(port=8000, debug=True)