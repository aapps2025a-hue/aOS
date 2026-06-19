"""
aOS Backend Server - Google OAuth 2.0 Integration
Main entry point for all backend services
"""

import os
import json
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google.auth.transport.urllib3
from datetime import datetime, timedelta
import secrets
import hashlib

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

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', 'YOUR_CLIENT_ID.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', 'YOUR_CLIENT_SECRET')
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Database Models
class User(db.Model):
    """User model for aOS system"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    picture = db.Column(db.String(500))
    access_token = db.Column(db.Text)
    refresh_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    devices = db.relationship('Device', backref='user', lazy=True, cascade='all, delete-orphan')
    installed_apps = db.relationship('InstalledApp', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'google_id': self.google_id,
            'email': self.email,
            'name': self.name,
            'picture': self.picture,
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
    device_type = db.Column(db.String(50))  # phone, tablet, desktop, etc.
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

# Authentication Routes
@app.route('/auth/google/login', methods=['GET'])
def google_login():
    """Initiate Google OAuth 2.0 login flow"""
    flow = Flow.from_client_secrets_file(
        'google_oauth_secret.json',
        scopes=[
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ],
        redirect_uri=url_for('google_callback', _external=True)
    )
    
    authorization_url, state = flow.authorization_url()
    session['oauth_state'] = state
    
    return jsonify({'authorization_url': authorization_url})

@app.route('/auth/google/callback', methods=['GET'])
def google_callback():
    """Handle Google OAuth 2.0 callback"""
    state = session.get('oauth_state')
    if not state:
        return jsonify({'error': 'Missing OAuth state'}), 400
    
    flow = Flow.from_client_secrets_file(
        'google_oauth_secret.json',
        scopes=[
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ],
        state=state,
        redirect_uri=url_for('google_callback', _external=True)
    )
    
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Get user info
        user_info = {
            'id': credentials.id_token.get('sub'),
            'email': credentials.id_token.get('email'),
            'name': credentials.id_token.get('name'),
            'picture': credentials.id_token.get('picture')
        }
        
        # Create or update user
        user = User.query.filter_by(google_id=user_info['id']).first()
        if not user:
            user = User(
                google_id=user_info['id'],
                email=user_info['email'],
                name=user_info['name'],
                picture=user_info['picture'],
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expires_at=credentials.expiry
            )
            db.session.add(user)
        else:
            user.access_token = credentials.token
            user.refresh_token = credentials.refresh_token
            user.token_expires_at = credentials.expiry
            user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'access_token': access_token,
            'user': user.to_dict()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    user_id = get_jwt_identity()
    # Invalidate tokens in real implementation
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
    
    # Check if already installed
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
        'build_type': 'release'
    })

@app.route('/system/settings', methods=['PUT'])
@jwt_required()
def update_system_settings():
    """Update system settings"""
    data = request.get_json()
    # Implementation for settings persistence
    return jsonify({'message': 'Settings updated'})

# Health check
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
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
