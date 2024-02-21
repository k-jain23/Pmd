# Import necessary modules
import json
import os
import logging
import base64
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_session import Session
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from openpyxl import load_workbook
import smtplib
import random

import cv2
import pytesseract
from flask_mail import *

# Create a Flask web application
app = Flask(__name__)
app.config['STATIC_FOLDER'] = 'static'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SECRET_KEY'] = 'your_secret_key'

# Configure flask-session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes (in seconds)
Session(app)

# Define the function to add cache control headers
@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Define a function to read data from an Excel file
def read_excel_data(file_path):
    try:
        # Read Excel data into a DataFrame
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        # Handle any errors that may occur during file reading
        return None

# Route for displaying the search form
@app.route('/')
def index():
    return render_template('search.html')

# Define a global variable to store the matching data
matching_data = []

# Route for handling the form submission and redirecting to results
@app.route('/submit-bform', methods=['POST'])
def submit_form():
    global matching_data  # Use the global variable

    # Get the selected activities from the form
    selected_activities = request.form.getlist('activities[]')

    # Read data from the Excel file (modify the file path as needed)
    excel_data = read_excel_data('check.xlsx')

    if excel_data is not None:
        # Filter rows where the "Interest" column matches selected activities
        matching_rows = excel_data[excel_data['Interest'].isin(selected_activities)]

        # Convert matching rows to a list of dictionaries
        matching_data = matching_rows.to_dict(orient='records')

        # Redirect to the results page
        return redirect('/results')
    else:
        # Handle the case where Excel data could not be loaded
        return render_template('results.html', data=[])

# Route for displaying results
@app.route('/results')
def results():
    global matching_data  # Use the global variable

    # Get the feedback data from the database
    feedback_df = get_feedback_data()

    if feedback_df is not None:
        # Calculate average ratings for each city
        city_ratings = feedback_df.groupby('city')['rating'].mean().reset_index()

        # Sort cities by average rating in descending order
        city_ratings = city_ratings.sort_values(by='rating', ascending=False)

        # Get the top N recommended cities (e.g., top 5)
        N = 3
        top_n_cities = city_ratings.head(N)

        # Debug: Print top recommended cities
        print(top_n_cities)

        # Modify the code to retrieve city names from the database instead of 'matching_data'
        # Retrieve city names from the database
        city_names = feedback_df['city'].tolist()

        # Filter top cities based on city names (case-insensitive)
        top_n_cities = top_n_cities[top_n_cities['city'].apply(lambda x: x.lower() in map(str.lower, city_names))]

        # Create a dictionary with image URLs for each city (replace with actual URLs)
        city_image_urls = {
            'Ajmer': 'https://www.tourmyindia.com/images/sharif-ajmer3.jpg',
            'Bharatpur': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQABVKw6v6nZTgwVdTu3VcMv3tkbR2-AGn9o4FBxTFJKg&s',
            'Bikaner': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSNJJzkJboLFrI7SDC18Ddc4kZm9GG56Fb2PPhFYGlLIxRFM8XR7GB0USn5L1xG0VBbiT0&usqp=CAU',
            # Add more city-image mappings as needed
        }

        # Add image URLs to the top cities data
        top_cities_data = top_n_cities.to_dict(orient='records')
        for city_data in top_cities_data:
            city_name = city_data['city']
            city_data['ImageURL'] = city_image_urls.get(city_name, 'Default_Image_URL')

        print(top_cities_data)  # Add this line for debugging

        return render_template('results.html', data=matching_data, top_cities=top_cities_data)
    else:
        # Handle the case where feedback data could not be retrieved or cleaned
        return render_template('results.html', data=[], top_cities=[])

# Define a function to establish a database connection
def get_db_connection():
    conn = pymysql.connect(
        host='localhost',   # Replace with your MySQL server host
        user='root',        # Replace with your MySQL username
        password='1234567',  # Replace with your MySQL password
        database='pmd',     # Replace with your MySQL database name
        cursorclass=pymysql.cursors.DictCursor  # Use DictCursor to fetch results as dictionaries
    )
    return conn

# Route for fetching feedback data from the database
@app.route('/get-feedback-data')
def get_feedback_data():
    try:
        conn = get_db_connection()  # Establish a database connection
        cursor = conn.cursor()

        query = "SELECT city, rating FROM feedback"
        cursor.execute(query)

        # Fetch all rows as dictionaries
        feedback_data = cursor.fetchall()

        conn.close()

        # Convert the data to a Pandas DataFrame
        feedback_df = pd.DataFrame(feedback_data)

        # Convert the 'rating' column to numeric (if not already)
        feedback_df['rating'] = pd.to_numeric(feedback_df['rating'], errors='coerce')

        return feedback_df.dropna()  # Drop rows with NaN ratings
    except Exception as e:
        # Handle errors, such as database connection issues
        return None

# Define a function to establish a database connection
def get_db_connection():
    conn = pymysql.connect(
        host='localhost',   # Replace with your MySQL server host
        user='root',        # Replace with your MySQL username
        password='1234567',  # Replace with your MySQL password
        database='pmd',     # Replace with your MySQL database name
        cursorclass=pymysql.cursors.DictCursor  # Use DictCursor to fetch results as dictionaries
    )
    return conn

# Route for submitting feedback data to the database
@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    if request.method == 'POST':
        user_id = session.get('user_id')  # Get the user's ID from the session
        city_list = request.form.getlist('city[]')
        rating_list = request.form.getlist('rating[]')

        try:
            conn = get_db_connection()  # Establish a database connection
            cursor = conn.cursor()

            for city, rating in zip(city_list, rating_list):
                # Check if there is an existing record for this user and city
                cursor.execute("SELECT id FROM feedback WHERE user_id = %s AND city = %s", (user_id, city))
                existing_record = cursor.fetchone()

                if existing_record:
                    # Update the existing record for this user and city
                    cursor.execute("UPDATE feedback SET rating = %s WHERE user_id = %s AND city = %s", (rating, user_id, city))
                else:
                    # Insert a new record with the user_id
                    cursor.execute("INSERT INTO feedback (user_id, city, rating) VALUES (%s, %s, %s)", (user_id, city, rating))

            conn.commit()
            conn.close()

            # Set a flash message
            flash('Thank you for your feedback', 'info')

            # Render the search template with the flash message
            return render_template('search.html', flash_message='Thank you for your feedback')

        except Exception as e:
            # Handle errors, you can return an error page or message
            return render_template('error.html', error_message=str(e))


# Create a MySQL database connection
db = pymysql.connect(
    host="localhost",
    user="root",
    password="1234567",
    database="pmd",
    cursorclass=pymysql.cursors.DictCursor  # This line is important
)


# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    registered = False  # Initialize 'registered' flag

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Username already exists', 'danger')
        else:
            hashed_password = generate_password_hash(password, method='sha256')
            cursor.execute("INSERT INTO users (username, password, email) VALUES (%s, %s, %s)", (username, hashed_password, email))
            db.commit()
            registered = True  # Set 'registered' flag to True on successful registration
            flash('Registration successful. You can now log in.', 'success')

    return render_template('search.html', registered=registered)  # Pass 'registered' flag

# Logout route
@app.route('/logout')
def logout():
    if 'user_id' in session:
        session.pop('user_id', None)
        session.pop('username', None)
        flash('Logout successful.', 'success')
    
    # You can render the same page
    return render_template('search.html', logged_out=True)  # Pass 'logged_out' as True to indicate logout

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = db.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user is not None:  # Check if a user was found
            user_id = user.get('id')  # Safely get the 'id' value from the user dictionary
            hashed_password = user.get('password')  # Safely get the 'password' value

            if user_id is not None and hashed_password is not None and check_password_hash(hashed_password, password):
                session['user_id'] = user_id
                session['username'] = username  # Update the username in the session
                flash('Login successful.', 'success')
                return redirect('/search')
        
        flash('Invalid username or password.', 'danger')

    return redirect('/search')  # Redirect back to the search page

@app.route('/search')
def search():
    if 'user_id' in session:
        user_id = session['user_id']
        registered = request.args.get('registered', False)  # Get the 'registered' parameter
        logged_out = request.args.get('logged_out') == 'true'  # Check for the 'logged_out' query parameter

        return render_template('search.html', user_id=user_id, registered=registered, logged_out=logged_out)
    else:
        return redirect(url_for('login'))

# Route for logging the user out when the tab is closed
@app.route('/logout-on-tab-close')
def logout_on_tab_close():
    if 'user_id' in session:
        session.pop('user_id', None)
        session.pop('username', None)
        flash('You have been automatically logged out because the tab was closed.', 'info')
    
    # You can render the same page or redirect to another page
    return render_template('search.html', logged_out=True)  # Pass 'logged_out' as True to indicate logout

# Route for adding a homestay
@app.route('/add-homestay')
def add_homestay():
    conn = get_db_connection()  # Establish a database connection
    cursor = conn.cursor()

    # Fetch all homestay data from the database
    cursor.execute("SELECT * FROM homestay")
    homestays = cursor.fetchall()
    # Modify the fetch operation for homestays to include image URLs
    for homestay in homestays:
        homestay['photo_url'] = f"data:image/jpeg;base64,{base64.b64encode(homestay['photo']).decode('utf-8')}"
   
    conn.close()

    return render_template('add-homestay.html', homestays=homestays,username=session.get('username'))


# Route for adding a guide
@app.route('/add-home')
def add_home():
    return render_template('search.html')


# Provide the path to the Tesseract executable and the Tesseract data directory
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
tessdata_dir_config = r'--tessdata-dir "C:\Program Files\Tesseract-OCR\tessdata"'

# Function to extract text from the Aadhar card image using OCR
def extract_text_from_image(uploaded_aadhar):
    # Save the uploaded Aadhar card image
    image_path = 'uploaded_aadhar.jpg'
    uploaded_aadhar.save(image_path)

    # Use OpenCV to read the image
    img = cv2.imread(image_path)

    # Convert the image to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply thresholding to preprocess the image
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    # Use pytesseract to perform OCR on the preprocessed image
    extracted_text = pytesseract.image_to_string(thresh, config=tessdata_dir_config)

    return extracted_text

# Route for submitting homestay data to the database
@app.route('/submit-homestay', methods=['POST'])
def submit_homestay():
    if request.method == 'POST':
        # Extract form data
        name = request.form['name']
        address = request.form['location']
        uploaded_aadhar = request.files['idProof']
        email = request.form['email']
        phone = request.form['phone']
        rooms = request.form['rooms']
        beds = request.form['beds']
        location = request.form['location']

        # Handle file uploads for ID proof and photo
        id_proof_file = request.files['idProof']
        photo_file = request.files['photo']

        extracted_text = extract_text_from_image(uploaded_aadhar).strip().lower()
        name_from_form = name.strip().lower()
        address_from_form = address.strip().lower()

        if name_from_form not in extracted_text or address_from_form not in extracted_text:
            flash('Aadhar card verification failed. Name or address does not match the provided input.', 'error')
            # Create a new ImmutableMultiDict without the 'idProof' key
            form_data = {key: value for key, value in request.form.items() if key != 'idProof'}
            request.form = form_data
            return redirect(url_for('add_homestay'))

        # If Aadhar card verification is successful, continue with the homestay submission
        try:
            conn = get_db_connection()  # Establish a database connection
            cursor = conn.cursor()
            user_id = session['user_id']

            # Insert the form data into the 'homestay' table
            cursor.execute(
                "INSERT INTO homestay (user_id, name, email, phone, rooms, beds, location, id_proof, photo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, name, email, phone, rooms, beds, location, id_proof_file.read(), photo_file.read())
            )
            conn.commit()
            conn.close()

            # Optionally, you can redirect to a success page or render a success message
            flash('Homestay added successfully', 'success')
            return redirect(url_for('add_homestay'))

        except Exception as e:
            # Handle errors, you can return an error page or message
            return render_template('error.html', error_message=str(e))


@app.route('/delete-homestay', methods=['POST'])
def delete_homestay():
    if request.method == 'POST':
        homestay_id = request.form['homestay_id']

        try:
            conn = get_db_connection()  # Establish a database connection
            cursor = conn.cursor()

            # Delete the homestay from the 'homestay' table
            cursor.execute("DELETE FROM homestay WHERE id = %s", (homestay_id,))
            conn.commit()
            conn.close()

            # Optionally, you can redirect to a success page or render a success message
            flash('Homestay deleted successfully', 'success')
            return redirect('/add-homestay')

        except Exception as e:
            # Handle errors, you can return an error page or message
            return render_template('error.html', error_message=str(e))

# Route for adding a guide
@app.route('/add-guide')
def add_guide():
    conn = get_db_connection()  # Establish a database connection
    cursor = conn.cursor()

    # Fetch all homestay data from the database
    cursor.execute("SELECT * FROM guides")
    guides = cursor.fetchall()
    # Modify the fetch operation for homestays to include image URLs
    for guide in guides:
        guide['photo'] = f"data:image/jpeg;base64,{base64.b64encode(guide['photo']).decode('utf-8')}"
   
    conn.close()

    return render_template('add-guide.html', guides=guides,username=session.get('username'))

# Route for submitting guide data to the database
@app.route('/submit-guide', methods=['POST'])
def submit_guide():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        experience = request.form['experience']       
        references = request.form['references']

        photo = request.files['photo']
        id_proof_file = request.files['idProof']

       # Handling multiple languages
        languages = ", ".join(request.form.getlist('languages'))
        try:
            conn = get_db_connection()  # Establish a database connection
            cursor = conn.cursor()
            user_id = session['user_id']

            # Insert the form data into the 'guides' table
            cursor.execute(
                "INSERT INTO guides (user_id, name, email, phone, languages, experience, ref, photo, id_proof) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, name, email, phone, languages, experience, references, photo.read(), id_proof_file.read())
            )
            conn.commit()
            conn.close()

            # Optionally, you can redirect to a success page or render a success message
            flash('Tour guide details added successfully', 'success')
            return render_template('add-guide.html')

        except Exception as e:
            # Handle errors, you can return an error page or message
            return render_template('error.html', error_message=str(e))

@app.route('/delete-guide', methods=['POST'])
def delete_guide():
    if request.method == 'POST':
        guide_id = request.form['guide_id']

        try:
            conn = get_db_connection()  # Establish a database connection
            cursor = conn.cursor()

            # Delete the homestay from the 'homestay' table
            cursor.execute("DELETE FROM guides WHERE id = %s", (guide_id,))
            conn.commit()
            conn.close()

            # Optionally, you can redirect to a success page or render a success message
            flash('Guide details deleted successfully', 'success')
            return redirect('/add-guide')

        except Exception as e:
            # Handle errors, you can return an error page or message
            return render_template('error.html', error_message=str(e))


# Define a function to check if the email exists in the users table
def checkEmailInDatabase(email):
    try:
        conn = get_db_connection()  # Establish a database connection
        cursor = conn.cursor()

        # Query to check if the email exists in the users table
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()

        conn.close()

        # Return True if the email is found, otherwise return False
        if result:
            return True
        else:
            return False
    except Exception as e:
        # Handle errors, such as database connection issues
        print(f"Error: {e}")
        return False

# Define a function to update the password for the specified email
def updatePassword(email, new_password):
    try:
        conn = get_db_connection()  # Establish a database connection
        cursor = conn.cursor()

        # Hash the new password
        hashed_password = generate_password_hash(new_password, method='sha256')

        # Update the password for the specified email in the users table
        cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))
        conn.commit()

        conn.close()

        return True  # Return True if the password is updated successfully
    except Exception as e:
        # Handle errors, such as database connection issues
        print(f"Error: {e}")
        return False

# Generate a random OTP
def generateOTP():
    digits = "0123456789"
    OTP = ""

    for i in range(6):
        OTP += digits[random.randint(0, 9)]

    return OTP

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = '465'
app.config['MAIL_USERNAME'] = '  '
app.config['MAIL_PASSWORD'] = '   '
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)
# Define a function to send an OTP to the user's email
def sendOTP(email, otp):
    try:
        msg = Message('OTP' , sender = 'kratikajain230103@gmail.com' ,reciepients = [email])
        msg.body=str(otp)
        mail.send(msg)

        return True
    except Exception as e:
        # Handle errors, such as SMTP authentication issues or email sending errors
        print(f"Error sending email: {e}")
        return False


# Update the verifyOTP function to include OTP generation and email sending
def verifyOTP():
    # Retrieve the entered email
    email = request.form['reset-email']

    # Generate an OTP
    generatedOTP = generateOTP()

    # Send the OTP to the user's email
    if sendOTP(email, generatedOTP):
        # Store the generated OTP in a session or database for verification later
        session['generated_otp'] = generatedOTP
        # Redirect to the page where the user can enter the OTP
    else:
        flash('Error sending OTP. Please try again.', 'danger')


# Define a route to handle the password update
@app.route('/update-password', methods=['POST'])
def handle_password_update():
    email = request.form['email']
    new_password = request.form['password']

    if updatePassword(email, new_password):
        return 'Password updated successfully'
    else:
        return 'Error updating password. Please try again.'



# Run the Flask app if this script is executed
if __name__ == '__main__':
    app.run(debug=True)

