from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy.exc import IntegrityError
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from datetime import datetime, timedelta
from final_recommender import Recommender  # Import your Recommender class
import pandas as pd
from supabase import create_client, Client
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from PIL import Image
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Google Generative AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


app = Flask(__name__)

# Database URI for Supabase PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.nkculiajetxhofngayca:Sdpysy24ysy@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres'

app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

url = "https://nkculiajetxhofngayca.supabase.co"  
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5rY3VsaWFqZXR4aG9mbmdheWNhIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczMDkwMjQ1OSwiZXhwIjoyMDQ2NDc4NDU5fQ.itjwX6V6OUTMjwmbOa5JVCHzYUX02ogAKsoTK7q5aSg"  
supabase: Client = create_client(url, key)

# Models
def load_data():
    profiles_data = supabase.table("user_profile").select("*").execute()
    recent_activity_data = supabase.table("recent_Activity").select("*").execute()
    dataset_data = supabase.table("dataset").select("*").execute()

    profiles = pd.DataFrame(profiles_data.data)
    recent_activity = pd.DataFrame(recent_activity_data.data)
    dataset = pd.DataFrame(dataset_data.data)

    return profiles, recent_activity, dataset


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
            print(session['user_id'])
            session['username'] = user.username
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for('dashboard'))

        flash("Invalid username or password!", "error")
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    # Fetch user and profile information (existing functionality)
    user = UserSignup.query.get_or_404(session['user_id'])
    profile = UserProfile.query.filter_by(User_Id=user.id).first()

    # Fetch recommendation logs grouped by date
    recent_activity = supabase.table("recent_Activity").select("*").eq("User_Id", user.id).execute().data
    activity_by_date = {}

    for entry in recent_activity:
        date = entry['Timestamp'][:10]  # Extract date from timestamp (YYYY-MM-DD format)
        if date not in activity_by_date:
            activity_by_date[date] = []
        activity_by_date[date].append(entry)

    # Render the template with additional data
    return render_template('dashboard.html', user=user, profile=profile, activity_by_date=activity_by_date)

@app.route('/recommendations')
@login_required
def recommendations():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    profiles, recent_activity, dataset = load_data()

    # Initialize the recommender and generate recommendations
    recommender = Recommender(profiles, recent_activity, dataset)
    recommended_meals = recommender.recommend(user_id)
    print(recommended_meals)
    # Check today's date
    today_date = datetime.now().date().isoformat()

    # Fetch existing recommendations for the user and date
    existing_recommendations = (
        supabase.table("recommendations")
        .select("Meal_Id")
        .eq("User_Id", user_id)
        .eq("created_at", today_date)
        .execute()
        .data
    )
    
    # Extract meal_ids from existing recommendations to avoid duplicates
    existing_meal_ids = {rec['Meal_Id'] for rec in existing_recommendations}

    # Insert new recommendations only if they are not already stored
    new_recommendations = []
    for category, meals in recommended_meals.items():  # Iterate through breakfast, lunch, dinner
        for meal in meals:
            if meal['Meal_Id'] not in existing_meal_ids:
                new_recommendations.append({
                "User_Id": user_id,
                "Meal_Id": meal['Meal_Id'],
                "created_at": today_date
            })

    if new_recommendations:
        supabase.table("recommendations").insert(new_recommendations).execute()
    return render_template('recommendations.html', recommendations=recommended_meals)

@app.route('/recommended_meals/<date>', methods=['GET', 'POST'])
@login_required
def recommended_meals(date):
    user_id = session['user_id']

    # Fetch meals for the user from recommendations table for the selected date
    recommendations = supabase.table("recommendations").select("*").eq("User_Id", user_id).execute().data
    
    recommended_meals = [
        rec for rec in recommendations
        if rec['created_at'][:10] == date
    ]
    
    
    # Fetch meal details from dataset table using Meal_Id
    if recommended_meals:
        meal_ids = [meal['Meal_Id'] for meal in recommended_meals]
        dataset_query = supabase.table("dataset").select("*").in_("Meal_Id", meal_ids).execute()
        dataset_meals = {meal['Meal_Id']: meal for meal in dataset_query.data}  # Map Meal_Id to details
    else:
        dataset_meals = {}
    print(dataset_meals)
    # Combine recommendations with dataset details
    categorized_meals = {'breakfast': [], 'lunch': [], 'dinner': []}
    
    for rec in recommended_meals:
        if rec['Meal_Id'] in dataset_meals:
            meal_details = dataset_meals[rec['Meal_Id']]
            combined_entry = {
                'Meal_Id': rec['Meal_Id'],
                'Name': meal_details.get('Name', 'Unknown'),
                'Nutrient': meal_details.get('Nutrient', 'Unknown'),
                'Timestamp': rec['created_at'],
                'Meal_type': meal_details.get('Meal_type', '')
            }
            
            # Split Meal_type into individual categories and add to each
            meal_types = [meal_type.strip().lower() for meal_type in combined_entry['Meal_type'].split(' ')]
            for meal_type in meal_types:
                if meal_type in categorized_meals:
                    # Avoid duplicates
                    if not any(meal['Meal_Id'] == combined_entry['Meal_Id'] for meal in categorized_meals[meal_type]):
                        categorized_meals[meal_type].append(combined_entry)

    print(categorized_meals)
    
    # Handle POST request for saving user selections
    if request.method == 'POST':
        selected_meals = request.form.getlist('selected_meals')  # Selected meal IDs
        ratings = request.form  # Retrieve all form data for ratings
        likes = request.form  # Retrieve all form data for likes

        for meal_id in selected_meals:
            rating = ratings.get(f"rating_{meal_id}", None)
            liked = likes.get(f"like_{meal_id}", None)

            # Prepare the entry
            recent_entry = {
                'User_Id': user_id,
                'Meal_Id': meal_id,
                'Rated': 1 if rating else 0,
                'Liked': 1 if liked == '1' else 0,
                'Timestamp': datetime.now().isoformat()
            }

            # Save to Supabase
            supabase.table("recent_Activity").insert(recent_entry).execute()

        flash("Your selections have been saved!", "success")
        return redirect(url_for('dashboard'))

    return render_template('recommended_meals.html', categorized_meals=categorized_meals, date=date)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('home'))


# Create tables
def init_db():
    with app.app_context():
        db.create_all()


# Update get_gemini_response function to accept prompt and image_parts in correct order
def get_gemini_response(prompt, image_parts):
    model = genai.GenerativeModel('gemini-1.5-flash')  # Example model loading
    # Assuming model.generate_content() expects the following inputs
    response = model.generate_content([prompt, image_parts[0]])  # Pass prompt first, then image parts
    return response.text

# Process the uploaded image
def process_image(file):
    if file:
        return [{
            "mime_type": file.content_type,
            "data": file.read()
        }]
    else:
        raise ValueError("No file uploaded")

# Route to render the image upload page
@app.route("/image")
def index():
    return render_template("image.html")

# Route to process the image and text inputs
@app.route("/process", methods=["POST"])
def process():
    # Get form data
    language = request.form.get("language", "English")
    image = request.files.get("image")
    action = request.form.get("action")
    
    # Define prompts based on language and action
    if language == "English":
        input_prompt3 = """
        In your role as a nutritional advisor, present a comprehensive overview of the dish's nutritional value:
        1. Display a table showcasing nutritional values in descending order, covering calories, protein, fat, and carbohydrates.
        2. Create a second table illustrating the nutritional contribution of each ingredient, unraveling the dietary secrets within.
        """
        input_prompt4 = """
        Act as a dietitian and nutritionist:
        1. Your task is to provide 2 vegetarian dish alternatives to the dish uploaded in the image which have the same nutritional value.
        2. Your task is to provide 2 non-vegetarian dish alternatives to the dish uploaded in the image which have the same nutritional value.
        """
    else:
        input_prompt3 = """
        एक पोषण सलाहकार के रूप में, डिश के पोषण सम्बंधी सम्पूर्ण अवलोकन प्रस्तुत करें:
        1. कैलोरी, प्रोटीन, वसा और कार्बोहाइड्रेट की घटाई गई पोषण मूल्यों को दिखाने वाला एक तालिका प्रदर्शित करें।
        2. हर आइटम के पोषण योगदान को बताने वाली दूसरी तालिका बनाएं, जिसमें आहार रहस्य हैं।
        """
        input_prompt4 = """
        एक रसोई समाचार पत्र के रूप में, समर्थन और पोषण में समानता के साथ एक शाकाहारी वैकल्पिक डिश की विस्तृत सूची बनाएं:
        1. प्राकृतिक और ताजगी को बढ़ावा देने के लिए एक शाकाहारी वैकल्पिक डिश के रूप में सूक्ष्मता से स्पष्टीकृत करें।
        2. मौजूदा के पोषण मूल्यों के साथ समर्थन और पोषण में समानता के लिए एक सूची बनाएं, नॉन-वेज वैकल्पिक के लिए एक लिस्ट।
        """
    
    # Select prompt based on action
    selected_prompt = input_prompt3 if action == "nutrition" else input_prompt4
    print(f"Selected Prompt: {selected_prompt}")
    
    try:
        # Process the image and get image parts
        image_parts = process_image(image)
        # Ensure the image parts and selected prompt are passed in the correct order
        response_text = get_gemini_response(selected_prompt, image_parts)
        return jsonify({"response": response_text})

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True, port=5002)
