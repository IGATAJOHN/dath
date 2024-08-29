from flask import (
    Flask,
    render_template,
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
from datetime import datetime,timedelta
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI
import random
from bson.objectid import ObjectId
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

user_activity_collection = db.user_activity
# Define the collection
conversations_collection = db.conversations

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

        # Create user document
        user_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": hashed_password,
           
        }
        
        users_collection.insert_one(user_data)
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))
        
    return render_template("register.html")

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

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        data = request.json
        user_input = data.get('message', '')

        user_id = session.get('user_id')

        # Retrieve conversation history from the database
        conversation_history = conversations_collection.find_one({'user_id': user_id}, {'_id': 0, 'history': 1})
        conversation_history = conversation_history['history'] if conversation_history else []

        # Append the new user input to the conversation history
        conversation_history.append({"role": "user", "content": user_input})

        response = generate_response(conversation_history)

        # Append the bot response to the conversation history
        conversation_history.append({"role": "assistant", "content": response})

        # Update the conversation history in the database
        conversations_collection.update_one(
            {'user_id': user_id},
            {'$set': {'history': conversation_history}},
            upsert=True
        )

        return jsonify({'reply': response})
    except Exception as e:
        app.logger.error(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
def extract_skills(response_text):
    # This is a simple example. You might need more advanced NLP techniques.
    skills = []
    possible_skills = ["Python", "Data Science", "Web Development", "AI", "Cybersecurity"]  # Add relevant skills

    for skill in possible_skills:
        if skill.lower() in response_text.lower():
            skills.append(skill)

    return skills

def generate_response(conversation_history):
    try:
        # Call OpenAI to get the chatbot's response
        completion = openai_client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {
            "role": "system",
            "content": """
            Dathway is an engaging and friendly chatbot, providing guidance and counseling to people who want to get into technology. Dathway leads the conversation, asks relevant questions, and offers encouragement and resources based on the user's responses.

            - Start by introducing yourself: "Hello, I’m Dathway, may I meet you?"
            - Ask the user for their name: "(First name), How’s your day going?"
            - Encourage the user to share more about themselves: "Tell me a little about yourself."
            - Dive into specifics with questions like: "What’s your favorite time of the day? Morning, afternoon, or evening?"
            - Explore the user's hobbies or interests: "What are your hobbies or interests?"
            - Gauge their social preferences: "Do you prefer going out with friends or enjoying a quiet night alone at home?"
            - Transition to tech: "How comfortable are you with technology? A tech wiz or more on the casual user side?"
            - Inquire about education: "What’s your current level of education or area of study?"
            - Understand their life goals: "What are your life goals or aspirations?"
            - Discuss their interest in technology: "How do you feel about technology? Excited to see where it is going or more of a casual user?"
            - Assess their available time: "How many hours per week can you dedicate to exploring and learning tech?"
            - Ask about their preferred learning style: "Do you prefer working independently or collaborating with others?"
            - Identify specific tech interests: "Any specific tech skills or areas you’ve been curious about?"
            - Assure them if they are unsure: "No worries at all, if you don’t have any knowledge about this new interest."
            - Gather work experience details: "Do you have any prior work experience related or in another field?"
            - Understand their commitment: "How long do you want to be relevant in this industry?"
            - Clarify their motivation: "Are you learning this skill for passion or for profit?"

            After gathering all this information:
            - Summarize the user's tech profile: "It’s great to learn more about you! Here’s a summary of your tech profile:"
            - Provide a summary based on the conversation.
            - Guide them to the next step: "Please click on the skills for the next line of action."
            - End the conversation on a positive note.

            Throughout the conversation:
            - Offer encouragement and understanding of the user's interests and concerns.
            - Guide users to additional resources on the platform as needed, such as recommending courses based on their interests.
            - Maintain a balance between being conversational and professional.
            """
        },
    ] + conversation_history
)

        model_response = completion.choices[0].message.content.strip()

        # Extract skill sets from the response
        suggested_skills = extract_skills(model_response)

        # Store the skill sets in the user's document in the database
        user_id = session.get('user_id')
        if user_id:
            store_detected_skills(user_id, suggested_skills)

        return model_response
    except Exception as e:
        return str(e)

def store_detected_skills(user_id, detected_skills):
    # Update the user's document with the detected skills
    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"detected_skills": detected_skills}}
    )

@app.route('/')
def dashboard():
    return render_template('dashboard.html')
@app.route('/skills')
def skills():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    # Retrieve the detected skills from the user's document in the database
    user = users_collection.find_one({"_id": ObjectId(user_id)}, {"detected_skills": 1})
    detected_skills = user.get('detected_skills', []) if user else []

    return render_template('skills.html', detected_skills=detected_skills)

@app.route('/upload_course', methods=['GET', 'POST'])
def upload_course():
    if request.method == 'POST':
        course_title = request.form['course_title']
        course_description = request.form['course_description']
        course_link = request.form['course_link']
        course_thumbnail = request.files['course_thumbnail']

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
            "thumbnail": thumbnail_path
        }

        # Insert into the MongoDB collection
        courses_collection.insert_one(course_data)
        
        flash("Course added successfully!", "success")
        return redirect(url_for('courses'))

    return render_template('upload_course.html')
@app.route('/community')
def community():
    return render_template('community.html')
@app.route('/courses')
def courses():
    # Get the current user's detected skills
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in to view recommended courses.", "danger")
        return redirect(url_for("login"))

    # Retrieve the detected skills from the database
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    detected_skills = user_data.get('detected_skills', [])

    # Fetch courses related to the detected skills
    courses = []
    if detected_skills:
        # Query the database for courses matching any of the detected skills
        courses = courses_collection.find({"title": {"$in": detected_skills}}).sort("title")

    return render_template('courses.html', courses=courses)

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
    app.run(debug=True,host='0.0.0.0',port='5000')
