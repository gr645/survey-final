from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash
from pymongo import MongoClient
import sys
from bson.objectid import ObjectId  # Import ObjectId for MongoDB

# Initialize Flask app
app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

def log(message):
    print(message, file=sys.stderr, flush=True)

# MongoDB configuration
MONGO_URI = "mongodb://localhost:27017/gr"
client = MongoClient(MONGO_URI)
db = client['gr']  # Database name

@app.route('/')
def login_form():
    return render_template('form.html')  

@app.route('/login', methods=['POST'])
def login():
    name = request.form['logemail']
    password = request.form['logpass']

    # Hardcoded admin credentials
    hardcoded_username = "admin"
    hardcoded_password = "password123"

    # Check if the entered credentials match the hardcoded admin credentials
    if name == hardcoded_username and password == hardcoded_password:
        session['logged_in'] = True
        session['username'] = name
        session['role'] = 'user'
        flash('Welcome, Admin! You have successfully logged in.', 'success')
        return redirect(url_for('survey_panel'))

    # Check if the entered credentials match an employee in the database
    employee = db.employee.find_one({"username": name})
    if employee and employee['password'] == password:
        session['logged_in'] = True
        session['username'] = name
        session['role'] = 'employee'
        session['department'] = employee['department']
        flash('Welcome! You have successfully logged in.', 'success')
        return redirect(url_for('answer_questions'))

    # If credentials do not match, show an error
    flash('Invalid username or password.', 'error')
    return redirect(url_for('login_form'))

@app.route('/survey')
def survey_panel():
    if not session.get('logged_in') or session.get('role') != 'user':
        return redirect(url_for('login_form'))
    return render_template('survey.html')

@app.route('/submit_survey', methods=['POST'])
def submit_survey():
    if not session.get('logged_in') or session.get('role') != 'user':
        return jsonify({'message': 'Unauthorized'}), 401

    try:
        # Parse JSON data from the request
        survey_data = request.json
        print("Received survey data:", survey_data)  # Debugging

        survey_title = survey_data['surveyTitle']
        department = survey_data['department']
        questions = survey_data['questions']

        # Insert survey into the surveys collection
        survey = {
            "title": survey_title,
            "department": department,
        }
        survey_id = db.surveys.insert_one(survey).inserted_id
        print("Survey created with ID:", survey_id)  # Debugging

        # Insert questions into the questions collection
        for question in questions:
            question_entry = {
                "survey_id": survey_id,
                "question_text": question['text'],
                "question_type": question['type'],
                "options": question.get('options', []),
            }
            db.questions.insert_one(question_entry)
            print("Inserted question:", question_entry)  # Debugging

        return jsonify({'message': 'Survey and questions created successfully!'}), 200
    except Exception as e:
        print(f"Error: {e}")  # Debugging
        return jsonify({'message': 'Failed to create survey.'}), 500

@app.route('/questions')
def answer_questions():
    if not session.get('logged_in') or session.get('role') != 'employee':
        flash('Please login as an employee to access this page.', 'error')
        return redirect(url_for('login_form'))

    department = session.get('department')

    # Fetch surveys for the employee's department
    surveys = db.surveys.find({"department": department})
    surveys_list = []
    for survey in surveys:
        # Fetch questions for the current survey using ObjectId
        questions = db.questions.find({"survey_id": ObjectId(survey["_id"])})
        questions_list = []
        for question in questions:
            questions_list.append({
                "question_id": str(question["_id"]),
                "question_text": question["question_text"],
                "question_type": question["question_type"],
                "options": question.get("options", [])
            })

        surveys_list.append({
            "survey_id": str(survey["_id"]),
            "title": survey["title"],
            "questions": questions_list
        })

    return render_template('questions.html', surveys=surveys_list)

@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    if not session.get('logged_in') or session.get('role') != 'employee':
        flash('Please login as an employee to submit answers.', 'error')
        return redirect(url_for('login_form'))

    try:
        # Parse the submitted answers
        answers_data = request.form.to_dict()
        survey_id = answers_data.pop("survey_id")
        employee_name = session.get('username')

        # Prepare the answers to be saved
        answers = []
        for key, value in answers_data.items():
            answers.append({
                "question_id": key,
                "answer": value
            })

        # Update the survey with the employee's answers
        db.surveys.update_one(
            {"_id": ObjectId(survey_id)},
            {"$push": {"responses": {"employee_name": employee_name, "answers": answers}}}
        )

        flash('Your answers have been submitted successfully!', 'success')
        return redirect(url_for('answer_questions'))
    except Exception as e:
        print(f"Error: {e}")
        flash('Failed to submit answers. Please try again.', 'error')
        return redirect(url_for('answer_questions'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_form'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            department = request.form['department']

            # Insert employee into MongoDB
            db.employee.insert_one({
                "username": username,
                "email": email,
                "password": password,
                "department": department
            })
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login_form'))
        except Exception as e:
            print(f"Database error: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('signup'))

    return render_template('signup.html')

if __name__ == '__main__':
    try:
        log("Starting Flask server...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        log(f"Server error: {e}")

