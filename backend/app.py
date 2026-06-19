"""
aOS Backend Server - A-Applications Integration
Main entry point for all backend services with Firebase authentication
"""

import os
import json
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from datetime import datetime, timedelta
import secrets

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///aos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Firebase configuration - A-Applications
FIREBASE_CONFIG = {
    "type": "service_account",
    "project_id": os.getenv('FIREBASE_PROJECT_ID', 'emojis-symbols-online'),
    "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
    "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
    "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
    "client_id": os.getenv('FIREBASE_CLIENT_ID'),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv('FIREBASE_CERT_URL')
}

# Initialize Firebase
try:
    cred = credentials.Certificate(FIREBASE_CONFIG)
    firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Firebase initialization warning: {e}")

# Database Models
class User(db.Model):
    """User model for aOS system - A-Applications Integration"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    firebase_uid = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    profile_picture = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    devices = db.relationship('Device', backref='user', lazy=True, cascade='all, delete-orphan')
    installed_apps = db.relationship('InstalledApp', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'firebase_uid': self.firebase_uid,
            'email': self.email,
            'name': self.name,
            'profile_picture': self.profile_picture,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }

class Device(db.Model):
    """Device model for multi-device support"""
    __tablename__ = 'devices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    device_id = db.Column(db.String(255), unique=True, nullable=False)
    device_name = db.Column(db.String(255))
    device_type = db.Column(db.String(50))
    os_version = db.Column(db.String(50))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'device_name': self.device_name,
            'device_type': self.device_type,
            'os_version': self.os_version,
            'last_seen': self.last_seen.isoformat()
        }

class InstalledApp(db.Model):
    """Track installed applications per user"""
    __tablename__ = 'installed_apps'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    package_name = db.Column(db.String(255), nullable=False)
    app_name = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(50))
    installed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'package_name'), )
    
    def to_dict(self):
        return {
            'package_name': self.package_name,
            'app_name': self.app_name,
            'version': self.version,
            'installed_at': self.installed_at.isoformat()
        }

class Permission(db.Model):
    """App permissions model"""
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    package_name = db.Column(db.String(255), nullable=False)
    permission_name = db.Column(db.String(255), nullable=False)
    permission_group = db.Column(db.String(50))
    granted = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'permission_name': self.permission_name,
            'permission_group': self.permission_group,
            'granted': self.granted
        }

# Authentication Routes - A-Applications Firebase Integration
@app.route('/auth/aapps/login', methods=['POST'])
def aapps_login():
    """Authenticate user with A-Applications Firebase credentials"""
    data = request.get_json()
    id_token = data.get('idToken')
    
    if not id_token:
        return jsonify({'error': 'Missing ID token'}), 400
    
    try:
        # Verify Firebase token
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name', email.split('@')[0] if email else 'User')
        picture = decoded_token.get('picture')
        
        # Create or update user
        user = User.query.filter_by(firebase_uid=uid).first()
        if not user:
            user = User(
                firebase_uid=uid,
                email=email,
                name=name,
                profile_picture=picture
            )
            db.session.add(user)
        else:
            user.name = name
            user.profile_picture = picture
            user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Create JWT token for aOS
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 401

@app.route('/auth/aapps/register', methods=['POST'])
def aapps_register():
    """Register new user via A-Applications"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    name = data.get('name', email.split('@')[0] if email else 'User')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    try:
        # Create Firebase user
        user_record = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=name
        )
        
        # Create aOS user record
        user = User(
            firebase_uid=user_record.uid,
            email=email,
            name=name
        )
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': user.to_dict()
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    user_id = get_jwt_identity()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/auth/refresh', methods=['POST'])
@jwt_required()
def refresh_token():
    """Refresh authentication token"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'error': 'User not found'}), 404
    
    new_token = create_access_token(identity=user.id)
    return jsonify({'access_token': new_token})

# User Routes
@app.route('/user/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(user.to_dict())

@app.route('/user/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    user.name = data.get('name', user.name)
    user.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify(user.to_dict())

# Device Management Routes
@app.route('/devices', methods=['GET'])
@jwt_required()
def get_devices():
    """Get user's devices"""
    user_id = get_jwt_identity()
    devices = Device.query.filter_by(user_id=user_id).all()
    return jsonify([device.to_dict() for device in devices])

@app.route('/devices', methods=['POST'])
@jwt_required()
def register_device():
    """Register a new device"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    device = Device(
        user_id=user_id,
        device_id=data.get('device_id'),
        device_name=data.get('device_name'),
        device_type=data.get('device_type', 'phone'),
        os_version=data.get('os_version', '1.0')
    )
    db.session.add(device)
    db.session.commit()
    
    return jsonify(device.to_dict()), 201

# App Management Routes
@app.route('/apps/installed', methods=['GET'])
@jwt_required()
def get_installed_apps():
    """Get user's installed apps"""
    user_id = get_jwt_identity()
    apps = InstalledApp.query.filter_by(user_id=user_id).all()
    return jsonify([app.to_dict() for app in apps])

@app.route('/apps/install', methods=['POST'])
@jwt_required()
def install_app():
    """Install an application"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    existing = InstalledApp.query.filter_by(
        user_id=user_id,
        package_name=data.get('package_name')
    ).first()
    
    if existing:
        return jsonify({'error': 'App already installed'}), 409
    
    app = InstalledApp(
        user_id=user_id,
        package_name=data.get('package_name'),
        app_name=data.get('app_name'),
        version=data.get('version', '1.0')
    )
    db.session.add(app)
    db.session.commit()
    
    return jsonify(app.to_dict()), 201

@app.route('/apps/uninstall/<package_name>', methods=['DELETE'])
@jwt_required()
def uninstall_app(package_name):
    """Uninstall an application"""
    user_id = get_jwt_identity()
    app = InstalledApp.query.filter_by(
        user_id=user_id,
        package_name=package_name
    ).first()
    
    if not app:
        return jsonify({'error': 'App not found'}), 404
    
    db.session.delete(app)
    db.session.commit()
    
    return jsonify({'message': 'App uninstalled'})

# Permission Routes
@app.route('/permissions/<package_name>', methods=['GET'])
@jwt_required()
def get_app_permissions(package_name):
    """Get permissions for an app"""
    permissions = Permission.query.filter_by(package_name=package_name).all()
    return jsonify([perm.to_dict() for perm in permissions])

@app.route('/permissions/<package_name>', methods=['POST'])
@jwt_required()
def grant_permission(package_name):
    """Grant permission to an app"""
    data = request.get_json()
    permission_name = data.get('permission_name')
    
    permission = Permission.query.filter_by(
        package_name=package_name,
        permission_name=permission_name
    ).first()
    
    if not permission:
        permission = Permission(
            package_name=package_name,
            permission_name=permission_name,
            permission_group=data.get('permission_group')
        )
        db.session.add(permission)
    
    permission.granted = True
    db.session.commit()
    
    return jsonify(permission.to_dict())

# System Routes
@app.route('/system/settings', methods=['GET'])
def get_system_settings():
    """Get system settings"""
    return jsonify({
        'os_name': 'aOS',
        'os_version': '1.0.0',
        'api_level': 30,
        'device_security_patch': '2024-06-01',
        'build_id': 'aOS.1.0.0.release',
        'build_type': 'release',
        'auth_provider': 'A-Applications (Firebase)'
    })

@app.route('/system/settings', methods=['PUT'])
@jwt_required()
def update_system_settings():
    """Update system settings"""
    data = request.get_json()
    return jsonify({'message': 'Settings updated'})

# Health check
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'auth_provider': 'A-Applications'
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_ENV') == 'development'
    )
