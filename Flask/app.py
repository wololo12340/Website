from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import openai

# Create Flask application instance
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secure key for sessions

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Set rate limiting
limiter = Limiter(key_func=get_remote_address)

# Bind the Limiter to the Flask app
limiter.init_app(app)

# Weather API configuration
WEATHER_API_KEY = 'b89a912b6a7b8e776e27f10193b90cf7'  # Replace with your actual API key
WEATHER_BASE_URL = 'http://api.openweathermap.org/data/2.5/weather'

# Define User and Post models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)

# Create the database tables if they don't exist
with app.app_context():
    db.create_all()

@app.route("/")
def login():
    return render_template('Login.html')

@app.route("/login", methods=['POST'])
@limiter.limit("5 per minute")
def login_user():
    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()
    
    if user is None:
        flash('Username does not exist. Please try again.', 'error')
        return redirect(url_for('login'))

    if not check_password_hash(user.password, password):
        flash('Incorrect password. Please try again.', 'error')
        return redirect(url_for('login'))

    # If the username and password are correct
    session['username'] = username
    flash(f'Welcome back, {username}!', 'success')
    return redirect(url_for('home_page'))

@app.route("/home_page")
def home_page():
    if 'username' not in session:
        flash('Please log in to access the home page.', 'error')
        return redirect(url_for('login'))

    posts = Post.query.all()
    return render_template('HomePage.html', username=session['username'], posts=posts)

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if 'username' not in session:
        flash('Please log in to create a post.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')

        if title and content:
            post = Post(title=title, content=content, author=session['username'])
            db.session.add(post)
            db.session.commit()  # Ensure the session is committed
            flash('Post created successfully!', 'success')
            return redirect(url_for('home_page'))
        else:
            flash('Both title and content are required.', 'error')

    return render_template('CreatePost.html')

@app.route('/profile')
def profile():
    return render_template('Profile.html')

@app.route('/web_info')
def web_info():
    return render_template('WebInfo.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# Registration Route
@app.route("/register", methods=["GET", "POST"])
def register_user():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if the username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.', 'error')
            return redirect(url_for('register_user'))

        hashed_password = generate_password_hash(password)  # Hash the password
        new_user = User(username=username, password=hashed_password)  
        db.session.add(new_user)
        db.session.commit()  # Ensure the session is committed

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('Register.html')

@app.route('/weather', methods=['GET', 'POST'])
def weather():
    weather_info = None
    error = None
    
    if request.method == 'POST':
        city = request.form.get('city')
        if not city:
            error = 'City name is required'
        else:
            response = requests.get(WEATHER_BASE_URL, params={
                'q': city,
                'appid': WEATHER_API_KEY,
                'units': 'metric'  # Return temperature in Celsius
            })

            if response.status_code == 200:
                data = response.json()
                weather_info = {
                    'city': data['name'],
                    'temperature': data['main']['temp'],
                    'description': data['weather'][0]['description'],
                    'humidity': data['main']['humidity'],
                }
            else:
                error = 'Unable to fetch weather data. Please check the city name.'

    return render_template('weather.html', weather_info=weather_info, error=error)

@app.route('/nba', methods=['GET', 'POST'])
def nba():
    player_info = None
    error = None

    if request.method == 'POST':
        player_name = request.form.get('player_name')
        if not player_name:
            error = 'Player name is required'
        else:
            player_dict = players.find_players_by_full_name(player_name)
            if player_dict:
                player_id = player_dict[0]['id']
                career_stats = playercareerstats.PlayerCareerStats(player_id=player_id)
                stats_df = career_stats.get_data_frames()[0]
                player_info = stats_df.to_dict(orient='records')  # Convert DataFrame to dict
            else:
                error = 'Player not found. Please check the name.'

    return render_template('nba.html', player_info=player_info, error=error)

# OpenAI API for Blog Title Generation
OPENAI_API_KEY = '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'  # Replace with your actual API key
openai.api_key = OPENAI_API_KEY

@app.route('/generate_title', methods=['GET', 'POST'])
def generate_title():
    generated_title = None
    error = None

    if request.method == 'POST':
        article_topic = request.form.get('article_topic')
        if not article_topic:
            error = 'Article topic is required'
        else:
            try:
                response = openai.Completion.create(
                    model="text-davinci-003",  # Use the appropriate OpenAI model
                    prompt=f"Generate a creative blog title for the topic: {article_topic}",
                    max_tokens=20,
                    temperature=0.7
                )
                generated_title = response.choices[0].text.strip()
            except Exception as e:
                error = f"Error generating title: {str(e)}"

    return render_template('GenerateTitle.html', generated_title=generated_title, error=error)

if __name__ == '__main__':
    app.run(debug=True)
