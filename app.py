from flask import (
    Flask,
    render_template,
    render_template_string,
    session,
    redirect,
    request,
    url_for,
    flash,
    jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    UserMixin,
    current_user,
)
from flask_session import Session
from pymongo import MongoClient
import os
from datetime import datetime,timedelta, timezone
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
import random
from textblob import TextBlob 
from bson.objectid import ObjectId
from math import ceil
import spacy 
nlp=spacy.load('en_core_web_sm')
# nest_asyncio.apply()
load_dotenv()
app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
api_key = os.getenv("OPENAI_API_KEY")
app.config["MONGO_URI"] = os.getenv("MONGODB_URI")
client = MongoClient(app.config["MONGO_URI"])
openai_client=OpenAI(api_key=api_key)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Configuration for email
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'igatajohn15@gmail.com'
app.config['MAIL_PASSWORD'] = 'vqvq zdef tweu nytn'
app.config['MAIL_DEFAULT_SENDER'] = 'igatajohn15@gmail.com'
app.config['SECURITY_PASSWORD_SALT'] = 'e33f8aa37685ca765b9d5613c0e41c0b'
mail = Mail(app)
# Secret key for generating reset tokens
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
db = client.get_database('dathway')
# MongoDB collections
users_collection = db.users
courses_collection=db.courses_list
communities_collection=db.communities
user_activity_collection = db.user_activity
# Define the collection
conversations_collection = db.conversations
detected_skills_collection = db.detected_skills
# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.first_name = user_data.get('first_name')
        self.last_name = user_data.get('last_name')
        self.email = user_data.get('email')
        self.password = user_data.get('password')
        self.conversation_history = user_data.get('conversation_history', [])
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': f"{self.first_name} {self.last_name}",
            'email': self.email,
        
        }

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id
    
@login_manager.user_loader
def load_user(user_id):
    # Check both collections for the user
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None
def user_list():
    users_data = users_collection.find()
    users = [User(data).to_dict() for data in users_data]
    return render_template("users.html", users=users)
@app.route('/users')
def users():
    return render_template("users.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        password = request.form.get("password")
        
        # Validate form data
        if not first_name or not last_name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        # Hash the password
        hashed_password = generate_password_hash(password, method='scrypt')

        # Create user document, with email verification status as False
        user_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": hashed_password,
            "is_verified": False  # New field to track verification status
        }
        
        # Insert user data into MongoDB
        users_collection.insert_one(user_data)
        
        # Generate a confirmation token
        token = serializer.dumps(email, salt='email-confirm')

        # Send confirmation email with user’s first name and confirmation URL
        confirm_url = url_for('confirm_email', token=token, _external=True)
        subject = "Please confirm your email"
        send_email(email, subject, confirm_url, first_name)

        flash("A confirmation email has been sent. Please verify your account.", "info")
        return redirect(url_for("login"))
        
    return render_template("register.html")

def send_email(to, subject, confirm_url, first_name):
    # The URL for the logo
    logo_url = url_for('static', filename='assets/img/dathway_logo.png', _external=True)
    
    # HTML email template with placeholders
    email_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Email Confirmation</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f4f4; color: #333333; margin: 0; padding: 20px; }
            .container { max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1); }
            .header { background-color: #002366; padding: 20px; text-align: center; color: white; }
            .header img { max-width: 100px; margin-bottom: 10px; }
            .header h1 { margin: 0; font-size: 24px; }
            .content { padding: 20px; }
            .content h2 { color: #002366; }
            .content p { font-size: 16px; line-height: 1.5; }
            .content a { display: inline-block; padding: 10px 20px; margin-top: 20px; background-color: #00b0cc; color: white; text-decoration: none; border-radius: 5px; }
            .content a:hover { background-color: #0096b3; }
            .footer { background-color: #f4f4f4; text-align: center; padding: 10px; font-size: 12px; color: #888888; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{{ logo_url }}" alt="Dathway Logo">
                <h1>Welcome to Dathway</h1>
            </div>
            <div class="content">
                <h2>Email Confirmation</h2>
                <p>Hi {{ first_name }},</p>
                <p>Thank you for registering with Dathway. To complete your registration, please confirm your email address by clicking the link below:</p>
                <a href="{{ confirm_url }}">Confirm Email</a>
                <p>If you didn’t create an account, you can safely ignore this email.</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 Dathway. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Render the template with the dynamic data
    html_content = render_template_string(
        email_html, 
        first_name=first_name, 
        confirm_url=confirm_url, 
        logo_url=logo_url
    )
    
    # Create the email message
    msg = Message(subject, recipients=[to], sender='noreply@dathway.com')
    msg.html = html_content  # Set the HTML content
    mail.send(msg)
@app.route("/confirm/<token>")
def confirm_email(token):
    try:
        # Verify the token (valid for 1 hour)
        email = serializer.loads(token, salt="email-confirm", max_age=3600)
        
        # Find the user by email and mark as verified
        user = users_collection.find_one({"email": email})
        if user:
            if user.get("is_verified"):
                flash("Account already verified. Please log in.", "info")
            else:
                users_collection.update_one({"email": email}, {"$set": {"is_verified": True}})
                flash("Your account has been verified. You can now log in.", "success")
        else:
            flash("Invalid or expired token.", "danger")
    except:
        flash("The confirmation link is invalid or has expired.", "danger")
    
    return redirect(url_for("login"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = None

        # If not found, try to find a normal user
        if not user:
            normal_user = users_collection.find_one({"email": email})
            if normal_user and check_password_hash(normal_user['password'], password):
                user = User(normal_user)
                session['user_id'] = str(normal_user['_id'])

        if user:
            login_user(user)
          
           
            return redirect(url_for('chat'))
        else:
            flash('Login failed. Check your email and password.')

    return render_template('login.html')
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = users_collection.find_one({"email": email})
        
        if user:
            # Generate a secure token
            token = serializer.dumps(user['email'], salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            
            # Send email with reset link
            msg = Message('Password Reset Request', sender='your-email@gmail.com', recipients=[email])
            msg.body = f'Please click the following link to reset your password: {reset_url}'
            mail.send(msg)
            
            flash('A password reset link has been sent to your email.', 'info')
            return redirect(url_for('password_reset_mail_sent'))
        else:
            flash('Email address not found', 'danger')
    
    return render_template('forgot_password.html')
@app.route('/password_reset_mail_sent')
def password_reset_mail_sent():
    return render_template('password_reset_mail_sent.html')
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        # Update the user's password in MongoDB
        users_collection.update_one(
            {"email": email},
            {"$set": {"password": hashed_password}}
        )
        flash('Your password has been reset successfully!', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html')
def log_user_activity(user_id, event, details=None):
    log_entry = {
        "user_id": user_id,
        "timestamp": datetime.utcnow(),
        "event": event,
        "details": details
    }
    user_activity_collection.insert_one(log_entry)
@app.route('/get-response', methods=['POST'])
def get_response():
    try:
        data = request.json
        user_input = data.get('input', '')
        if not user_input:
            raise ValueError("No input provided")

        user_id = session.get('user_id')

        # Retrieve conversation history from the database
        conversation_history = conversations_collection.find_one({'user_id': user_id}, {'_id': 0, 'history': 1})
        conversation_history = conversation_history['history'] if conversation_history else []

        # Append the new user input to the conversation history
        conversation_history.append({"role": "user", "content": user_input})

        response_text = generate_response(conversation_history)

        # Append the bot response to the conversation history
        conversation_history.append({"role": "assistant", "content": response_text})

        # Update the conversation history in the database
        conversations_collection.update_one(
            {'user_id': user_id},
            {'$set': {'history': conversation_history}},
            upsert=True
        )

        log_user_activity(user_id, "chat_interaction", {"user_input": user_input, "response": response_text})

        return jsonify({'response': response_text})
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500 
@app.route('/get-conversation-history', methods=['GET'])
def get_conversation_history():
    try:
        user_id = session.get('user_id')

        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401

        # Retrieve conversation history from the database
        conversation_history = conversations_collection.find_one({'user_id': user_id}, {'_id': 0, 'history': 1})
        conversation_history = conversation_history['history'] if conversation_history else []

        return jsonify({'conversation_history': conversation_history})
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
from flask import jsonify

@app.route('/get-skills')
def get_skills():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401
    
    user_skills = detected_skills_collection.find_one({"user_id": user_id}, {"_id": 0, "skills": 1})
    print("Fetched user skills:", user_skills)  # Debugging statement

    if not user_skills or 'skills' not in user_skills:
        return jsonify({"error": "No skills found for user"}), 404

    return jsonify(user_skills)

@app.route('/chat')
def chat():
    # This route renders the chat page and can include pre-existing detected skills
    detected_skills = session.get('detected_skills', [])
    return render_template('chat.html', detected_skills=detected_skills)
@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        data = request.json
        user_input = data.get('message', '')
        user_id = session.get('user_id')

        # Retrieve and update conversation history
        conversation_history = conversations_collection.find_one({'user_id': user_id}, {'_id': 0, 'history': 1})
        conversation_history = conversation_history['history'] if conversation_history else []
        conversation_history.append({"role": "user", "content": user_input})

        # Generate response and detect skills at conversation end
        response = generate_response(conversation_history)
        conversation_history.append({"role": "assistant", "content": response})

        # Update conversation history
        conversations_collection.update_one(
            {'user_id': user_id},
            {'$set': {'history': conversation_history}},
            upsert=True
        )

        return jsonify({'reply': response})
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def store_or_update_skills(user_id, new_skills):
    # Find the user's document by user_id
    user_skills = detected_skills_collection.find_one({"user_id": ObjectId(user_id)})

    # Update or create the document
    if user_skills:
        # Update existing skills list
        for skill in new_skills:
            if skill not in [item['name'] for item in user_skills['skills']]:
                user_skills['skills'].append({"name": skill, "timestamp": datetime.utcnow()})
        user_skills['last_updated'] = datetime.utcnow()
        detected_skills_collection.update_one(
            {"user_id": ObjectId(user_id)},
            {"$set": {"skills": user_skills['skills'], "last_updated": user_skills['last_updated']}}
        )
    else:
        # Create a new document for the user with the detected skills
        detected_skills_collection.insert_one({
            "user_id": ObjectId(user_id),
            "skills": [{"name": skill, "timestamp": datetime.utcnow()} for skill in new_skills],
            "last_updated": datetime.utcnow()
        })
def map_themes_to_skills(themes):
    theme_skill_mapping = {
        "problem-solving": ["Python", "Data Science", "Algorithms"],
        "web": ["Web Development", "JavaScript", "HTML", "CSS"],
        "AI": ["AI", "Machine Learning", "Deep Learning"],
        "security": ["Cybersecurity", "Network Security"],
        "data": ["Data Science", "SQL", "Data Analysis"],
        "coding": ["Python", "JavaScript", "C++", "Java"],
        "technology": ["Tech", "IT", "Software Development"],
        "business": ["Business Analysis", "Project Management"],
        "beginner": ["Basic Programming", "Intro to Computers", "Digital Literacy"],
        "entrepreneurship": ["Startup Skills", "Business Strategy"]
    }

    inferred_skills = []
    for theme in themes:
        if theme in theme_skill_mapping:
            inferred_skills.extend(theme_skill_mapping[theme])

    return list(set(inferred_skills))

def extract_themes_and_skills(user_responses):
    responses_text = " ".join(user_responses).lower()
    print("Aggregated responses text:", responses_text)  # Debugging statement
    doc = nlp(responses_text)
    
    possible_themes = [
        "problem-solving", "web", "AI", "security", "data", "coding", 
        "technology", "business", "beginner", "entrepreneurship", 
        "python", "javascript", "machine learning"
    ]
    
    themes = [token.text.lower() for token in doc if token.text.lower() in possible_themes]
    inferred_skills = map_themes_to_skills(themes)
    
    print("Extracted themes:", themes)  # Debugging statement
    print("Inferred skills:", inferred_skills)  # Debugging statement
    return inferred_skills

def store_detected_skills(user_id, detected_skills):
    try:
        if detected_skills:
            update_result = users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$addToSet": {"detected_skills": {"$each": detected_skills}}}
            )
            print("Database update result:", update_result.modified_count)
    except Exception as e:
        print(f"Error updating database: {e}")
    if detected_skills:
        update_result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$addToSet": {"detected_skills": {"$each": detected_skills}}}
        )
        # Check if update was successful
        print("Database update result:", update_result.modified_count)

def generate_response(conversation_history):
    try:
        # Print conversation history for debugging
        print("Conversation history:", conversation_history)

        # Request a response from the model with a structured conversational flow
        completion = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """
                    Dathway is a warm, engaging chatbot, here to learn about the user's background, interests, and goals to recommend the best tech skills for them. Dathway keeps the conversation light and welcoming, asking **one question at a time**.

                    Guidelines:
                    - Ask one question per message.
                    - Use a friendly, supportive tone that encourages sharing.
                    - Gather background details, interests, passions, and goals to understand the user's personality better.

                    Flow of Conversation:
                    - Start with a warm welcome and an invitation to chat: "Hi there! I'm Dathway, your friendly tech guide! I'd love to get to know you a bit. 😊 Mind if I ask a few questions?"
                    - Ask for the user's name in a friendly way: "What’s your name?"
                    - Check in with the user's mood, keeping it light: "How’s your day going so far?"
                    - Begin exploring their personality and interests:
                        - "What are some of your biggest passions?"
                        - "How would your friends describe your personality in a few words?"
                        - "Do you have any hobbies you’re really into?"
                        - "What kinds of activities do you enjoy during your free time?"
                        - "What are your favorite ways to learn new things?"
                    - Once personality is established, gently shift to tech-related questions:
                        - "Are you new to technology, or do you already have some experience?"
                        - "If you’ve got experience, how long have you been exploring tech?"
                        - "Would you say you’re a beginner, intermediate, or an expert?"

                    Building Curiosity:
                    - Invite users to explore recommended skills on the Skills route: "I have some tech paths in mind that I think you'd enjoy! Tap on the Skills route when you’re ready to explore them."

                    Appreciation Message:
                    - Wrap up with a friendly and encouraging note:
                      "Thanks for chatting with me! I hope you found this helpful in your tech journey. There's so much to explore, and I know you're going to do amazing things. 😊 For personalized skill recommendations, tap on the Skills route to see what’s next!"

                    Final Notes:
                    - Ensure **only one question per message** with no follow-up or combined questions.
                    """
                }
            ] + conversation_history
        )

        model_response = completion.choices[0].message.content.strip()

        # Extract content from conversation history for skill extraction
        responses_content = [msg["content"] for msg in conversation_history if "content" in msg]
        print("Responses content for skill extraction:", responses_content)  # Debugging statement

        # Extract skill sets from the response
        suggested_skills = extract_themes_and_skills(responses_content)
        print("Skills to store:", suggested_skills)  # Debugging output

        # Store the skill sets in the user's document in the database
        user_id = session.get('user_id')
        if user_id:
            # Update skills in MongoDB with upsert
            result = detected_skills_collection.update_one(
                {"user_id": user_id},
                {"$set": {"skills": suggested_skills, "timestamp": datetime.now(timezone.utc)}},
                upsert=True
            )
            print("Matched count:", result.matched_count)  # Debugging statement
            print("Modified count:", result.modified_count)  # Debugging statement

        return model_response
    except Exception as e:
        print("Error in generate_response:", e)
        return str(e)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload_course', methods=['GET', 'POST'])
def upload_course():
    if request.method == 'POST':
        course_title = request.form['course_title']
        course_description = request.form['course_description']
        course_link = request.form['course_link']
        course_thumbnail = request.files['course_thumbnail']
        course_skills = request.form.getlist('course_skills')  # List of relevant skills

        print("Course skills:", course_skills)  # Debugging statement

        # Save the thumbnail image to the server
        if course_thumbnail:
            filename = secure_filename(course_thumbnail.filename)
            thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            course_thumbnail.save(thumbnail_path)

        # Create the course document
        course_data = {
            "title": course_title,
            "description": course_description,
            "link": course_link,
            "thumbnail": thumbnail_path,
            "skills": course_skills  # Add skills field
        }
        print("Course data:", course_data)  # Debugging statement

        # Insert into the MongoDB collection
        courses_collection.insert_one(course_data)
        
        flash("Course added successfully!", "success")
        return redirect(url_for('courses'))

    return render_template('upload_course.html')

@app.route('/skills')
def skills():
    return render_template('skills.html')


@app.route('/add_community', methods=['GET', 'POST'])
@login_required  # Make sure the user is logged in
def add_community():
    # # Only allow access to authorized users (e.g., admins)
    # if not session.get("is_admin"):
    #     flash("You do not have permission to upload a community.", "danger")
    #     return redirect(url_for("community"))

    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        description = request.form.get('description')
        category = request.form.get('category')
        
        # Validate form data
        if not name or not description or not category:
            flash("All fields are required.", "warning")
            return redirect(url_for('add_community'))

        # Insert new community into the database
        new_community = {
            "name": name,
            "description": description,
            "category": category
        }
        communities_collection.insert_one(new_community)
        
        flash("Community uploaded successfully!", "success")
        return redirect(url_for('community'))

    return render_template('add_community.html')

@app.route('/community')
@login_required
def community():
    # Get the current page number from the URL query string (default is 1)
    page = int(request.args.get('page', 1))
    per_page = 5  # Number of communities per page
    
    # Calculate the total number of communities for pagination
    total_communities = communities_collection.count_documents({})
    total_pages = ceil(total_communities / per_page)

    # Calculate the number of communities to skip based on the current page
    skip = (page - 1) * per_page

    # Fetch the communities for the current page with sorting and limit
    communities = list(
        communities_collection.find()
        .sort("name")
        .skip(skip)
        .limit(per_page)
    )

    # Render the template with pagination details
    return render_template(
        'community.html',
        communities=communities,
        page=page,
        total_pages=total_pages
    )

course_mapping = {
    "Software Development": ["HTML & CSS for Beginners", "JavaScript Fundamentals", "Advanced Web Development"],
    "IT": ["Python for Everybody", "Data Science with Python", "Machine Learning with Python"],
    "Tech": ["Introduction to Data Science", "Data Analysis with Python", "Machine Learning Basics"],
    # Add more skills and courses as needed
}


@app.route('/courses', methods=['GET'])
def courses():
    try:
        # Hardcoded skills for testing
        skill_names = ["Web Development", "Python", "Data Science"]
        print(f"Testing with skills: {skill_names}")
        
        # Use MongoDB's find method to fetch courses matching the hardcoded skills
        recommended_courses = list(courses_collection.find({"skills": {"$in": skill_names}}))
        
        print(f"Recommended courses: {recommended_courses}")
        return render_template('courses.html', courses=recommended_courses)

    except Exception as e:
        print(f"Error fetching courses, error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


@app.route('/account')
def account():
    return render_template('account.html')
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))
@app.route('/api/weekly-active-users')
def weekly_active_users():
    end_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start_of_week = end_of_day - timedelta(days=7)

    weekly_active_users = user_activity_collection.aggregate([
        {
            "$match": {
                "timestamp": {"$gte": start_of_week, "$lt": end_of_day}
            }
        },
        {
            "$group": {
                "_id": {
                    "day": {"$dayOfMonth": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "year": {"$year": "$timestamp"}
                },
                "unique_users": {"$addToSet": "$user_id"}
            }
        },
        {
            "$project": {
                "date": {"$dateFromParts": {"year": "$_id.year", "month": "$_id.month", "day": "$_id.day"}},
                "unique_users_count": {"$size": "$unique_users"}
            }
        },
        {
            "$sort": {"date": 1}
        }
    ])

    data = [{"date": str(day["date"].date()), "count": day["unique_users_count"]} for day in weekly_active_users]
    return jsonify(data)
@app.route('/api/daily-active-users')
def daily_active_users():
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    daily_active_users = user_activity_collection.aggregate([
        {
            "$match": {
                "timestamp": {"$gte": start_of_day, "$lt": end_of_day}
            }
        },
        {
            "$group": {
                "_id": "$user_id"
            }
        },
        {
            "$count": "daily_active_users"
        }
    ])

    count = list(daily_active_users)[0]['daily_active_users'] if daily_active_users else 0
    return jsonify({'count': count})    
if __name__ == '__main__':
    app.run(debug=True)
