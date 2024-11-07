from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy.exc import IntegrityError
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Database URI for Supabase PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.nkculiajetxhofngayca:Sdpysy24ysy@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres'

app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Models


class UserSignup(db.Model):
    """User authentication and basic info model"""
    __tablename__ = 'user_signups'

    id = db.Column(db.Text, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           nullable=True, server_default=db.func.now())

    # Define relationship using the matching IDs
    profile = db.relationship(
        'UserProfile',
        primaryjoin="UserSignup.id == foreign(UserProfile.User_Id)",
        uselist=False,
        backref='user'
    )

    def __init__(self, username, email, password):
        # Get the highest User_Id using proper numerical ordering
        last_profile = db.session.query(
            UserProfile.User_Id,
            db.cast(
                db.func.regexp_replace(UserProfile.User_Id, 'User_', ''),
                db.Integer
            ).label('id_num')
        ).order_by(
            db.desc('id_num')
        ).first()

        if last_profile:
            try:
                last_num = int(last_profile.User_Id.split('_')[1])
                self.id = f"User_{last_num + 1}"
            except (IndexError, ValueError):
                self.id = "User_1"
        else:
            self.id = "User_1"

        self.username = username
        self.email = email
        self.password = password

    @classmethod
    def authenticate(cls, username, password):
        """Authenticate a user by username and password."""
        try:
            # First, get the user and print debug info
            user = cls.query.filter_by(username=username).first()
            if not user:
                print(f"No user found with username: {username}")
                return None

            # Check if password matches and print debug info
            is_match = user.password == password
            print(f"Password check result for {username}: {is_match}")

            if is_match:
                return user
            return None

        except Exception as e:
            print(f"Authentication error: {str(e)}")
            return None

    @classmethod
    def user_exists(cls, username, email):
        return cls.query.filter(
            db.or_(
                cls.username == username,
                cls.email == email
            )
        ).first() is not None


class UserProfile(db.Model):
    """User profile information model"""
    __tablename__ = 'user_profile'

    User_Id = db.Column(db.Text, primary_key=True)
    Name = db.Column(db.Text, nullable=True)
    Email = db.Column(db.Text, nullable=True)
    Age = db.Column(db.BigInteger, nullable=True)
    Gender = db.Column(db.Text, nullable=True)
    Height = db.Column(db.BigInteger, nullable=True)
    Weight = db.Column(db.BigInteger, nullable=True)
    BMI = db.Column(db.Float(precision=53), nullable=True)
    Nutrient = db.Column(db.Text, nullable=True)
    Disease = db.Column(db.Text, nullable=True)
    Diet = db.Column(db.Text, nullable=True)
    Veg_Non = db.Column(db.Text, nullable=True)

    def __init__(self, user_signup):
        """Initialize profile with user signup reference"""
        self.User_Id = user_signup.id
        self.Email = user_signup.email

    def calculate_bmi(self):
        """Calculate BMI if height and weight are available"""
        if self.Height and self.Weight:
            height_m = self.Height / 100  # Convert cm to m
            self.BMI = round(self.Weight / (height_m ** 2), 2)
        return self.BMI

    def update_profile(self, form_data):
        """Update profile with form data"""
        try:
            # Basic information
            self.Name = form_data.get('name')
            self.Email = form_data.get('email')
            self.Age = int(form_data.get('age')) if form_data.get(
                'age') else None
            self.Gender = form_data.get('gender')
            self.Height = int(form_data.get('height')
                              ) if form_data.get('height') else None
            self.Weight = int(form_data.get('weight')
                              ) if form_data.get('weight') else None

            # Calculate BMI from form data
            self.BMI = float(form_data.get('bmi')) if form_data.get(
                'bmi') else self.calculate_bmi()

            # Handle health conditions (checkboxes)
            health_conditions = form_data.getlist('health[]')
            self.Disease = ', '.join(
                health_conditions) if health_conditions else None

            # Handle diet preferences (checkboxes)
            diet_preferences = form_data.getlist('diet[]')
            self.Diet = ', '.join(
                diet_preferences) if diet_preferences else None

            # Food preference (vegetarian/non-vegetarian)
            self.Veg_Non = form_data.get('food_preference')

            # Set Nutrient to None as it's not in the form
            self.Nutrient = None

            return True
        except ValueError as e:
            print(f"Error updating profile: {e}")
            return False


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def home():
    return render_template('landing.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        email = request.form.get('email', '').strip().lower()

        if not all([username, password, email]):
            flash("All fields are required!", "error")
            return redirect(url_for('signup'))

        # if len(password) < 8:
        #     flash("Password must be at least 8 characters long!", "error")
        #     return redirect(url_for('signup'))

        if UserSignup.user_exists(username, email):
            flash("Username or Email already exists!", "error")
            return redirect(url_for('signup'))

        try:
            new_user = UserSignup(
                username=username,
                password=password,
                email=email
            )
            db.session.add(new_user)
            db.session.commit()

            session['user_id'] = new_user.id
            session['username'] = new_user.username

            print(f"User created successfully: {new_user.id}")

            flash("Registration successful! Please complete your profile.", "success")
            return redirect(url_for('user_details_form'))

        except IntegrityError as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "error")
            return redirect(url_for('signup'))

    return render_template('signup.html')


@app.route('/details', methods=['GET', 'POST'])
@login_required
def user_details_form():
    if request.method == 'POST':
        try:
            # Get user from session
            user = UserSignup.query.get(session['user_id'])
            if not user:
                flash("User session expired. Please login again.", "error")
                return redirect(url_for('login'))

            # Get or create profile
            profile = UserProfile.query.filter_by(User_Id=user.id).first()
            if not profile:
                profile = UserProfile(user)

            # Update profile with form data
            if profile.update_profile(request.form):
                try:
                    if not UserProfile.query.get(profile.User_Id):
                        db.session.add(profile)
                    db.session.commit()
                    flash("Profile updated successfully!", "success")
                    return redirect(url_for('dashboard'))
                except IntegrityError as e:
                    db.session.rollback()
                    print(f"Database error updating profile: {str(e)}")
                    flash("An error occurred while saving profile.", "error")
            else:
                flash("Invalid data provided. Please check your inputs.", "error")

        except Exception as e:
            print(f"Unexpected error in profile update: {str(e)}")
            flash("An unexpected error occurred. Please try again.", "error")
            db.session.rollback()

    # For both GET and failed POST
    try:
        user = UserSignup.query.get(session['user_id'])
        profile = UserProfile.query.filter_by(
            User_Id=user.id).first() if user else None
        return render_template('forms.html', user=user, profile=profile)
    except Exception as e:
        print(f"Error loading form: {str(e)}")
        flash("Error loading form. Please login again.", "error")
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash("Both username and password are required!", "error")
            return redirect(url_for('login'))

        user = UserSignup.authenticate(username, password)
        print(user)
        if user:
            # Check if user has completed profile
            if not user.profile:
                session['user_id'] = user.id
                flash("Please complete your profile first.", "warning")
                return redirect(url_for('user_details_form'))

            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for('dashboard'))

        flash("Invalid username or password!", "error")
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    user = UserSignup.query.get_or_404(session['user_id'])
    profile = UserProfile.query.filter_by(User_Id=user.id).first()
    return render_template('dashboard.html', user=user, profile=profile)


@app.route('/recommendation')
@login_required
def recommendation():
    user = UserSignup.query.get_or_404(session['user_id'])
    profile = UserProfile.query.filter_by(User_Id=user.id).first()
    
    return render_template('recommendations.html', user=user, profile=profile)


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('home'))


# Create tables
def init_db():
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5002)
