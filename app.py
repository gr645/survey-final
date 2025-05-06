from flask import Flask, request, render_template, redirect, url_for, jsonify, session, flash, Response
from pymongo import MongoClient
import sys
from bson.objectid import ObjectId  # Import ObjectId for MongoDB
import bcrypt  # Import bcrypt for password hashing
import csv  # Import csv for exporting responses
from datetime import datetime  

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
    hardcoded_password = "pass123"

    # Check if the entered credentials match the hardcoded admin credentials
    if name == hardcoded_username and password == hardcoded_password:
        session['logged_in'] = True
        session['username'] = name
        session['role'] = 'user'
        # flash('Welcome, Admin! You have successfully logged in.', 'success')
        return redirect(url_for('survey_panel'))

    # Check if the entered credentials match an employee in the database
    employee = db.employee.find_one({"username": name})
    if employee and bcrypt.checkpw(password.encode('utf-8'), employee['password'].encode('utf-8')):
        session['logged_in'] = True
        session['username'] = name
        session['role'] = 'employee'
        session['department'] = employee['department']
        # flash('Welcome! You have successfully logged in.', 'success')
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
        answers_data = request.form.to_dict(flat=False)  # Use flat=False to handle multiple checkbox values
        print("Received answers data:", answers_data)  # Debugging

        if "survey_id" not in answers_data:
            flash('Survey ID is missing. Please try again.', 'error')
            return redirect(url_for('answer_questions'))

        survey_id = answers_data.pop("survey_id")[0]  
        # Get current date and time
        now = datetime.now()
        submission_date = now.strftime("%Y-%m-%d")
        submission_time = now.strftime("%H:%M:%S")

        # Prepare the answers to be saved
        answers = []
        for question_id, answer in answers_data.items():
            try:
                # Convert question_id to ObjectId
                question = db.questions.find_one({"_id": ObjectId(question_id)})
                if question:
                    question_type = question.get("question_type", "unknown")  # Get the question type
                    if isinstance(answer, list):  # Handle multiple checkbox answers
                        for single_answer in answer:
                            answers.append({
                                "survey_id": survey_id,
                                "question_text": question["question_text"],
                                "answer": single_answer,
                                "answer_type": question_type,  # Include the answer type
                                "submission_date": submission_date,
                                "submission_time": submission_time
                            })
                    else:  # Handle single answers (radio buttons, open-ended)
                        answers.append({
                            "survey_id": survey_id,
                            "question_text": question["question_text"],
                            "answer": answer,
                            "answer_type": question_type,  # Include the answer type
                            "submission_date": submission_date,
                            "submission_time": submission_time
                        })
                else:
                    print(f"Question with ID {question_id} not found.")  # Debugging
            except Exception as e:
                print(f"Error processing question_id {question_id}: {e}")  # Debugging

        print("Prepared answers for insertion:", answers)  # Debugging

        # Insert answers into the answers collection
        if answers:
            db.answers.insert_many(answers)
            print("Answers successfully inserted into the database.")  # Debugging
            return redirect(url_for('submission_confirmation'))  # Redirect to confirmation page
        else:
            print("No answers to insert.")  # Debugging
            flash('No answers to submit.', 'error')
            return redirect(url_for('answer_questions'))
    except Exception as e:
        print(f"Error: {e}")  # Debugging
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

            # Hash the password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

            # Insert employee into MongoDB
            db.employee.insert_one({
                "username": username,
                "email": email,
                "password": hashed_password.decode('utf-8'),  # Store as a string
                "department": department
            })
            # flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('login_form'))
        except Exception as e:
            print(f"Database error: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/submission_confirmation')
def submission_confirmation():
    return render_template('submission_confirmation.html')

@app.route('/export_responses/<survey_id>', methods=['GET'])
def export_responses(survey_id):
    try:
        # Fetch responses for the given survey_id
        responses = db.answers.find({"survey_id": survey_id})
        survey = db.surveys.find_one({"_id": ObjectId(survey_id)})

        if not survey:
            return jsonify({"message": "Survey not found."}), 404

        department = survey.get("department", "Unknown Department")

        # Create a CSV file in memory
        def generate_csv():
            # Write the header
            yield "Question,Answer,Department\n"
            for response in responses:
                question_text = response.get("question_text", "Unknown Question")
                answer = response.get("answer", "No Answer")
                yield f"{question_text},{answer},{department}\n"

        # Return the CSV file as a response
        return Response(
            generate_csv(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=survey_{survey_id}_responses.csv"}
        )
    except Exception as e:
        print(f"Error exporting responses: {e}")
        return jsonify({"message": "Failed to export responses."}), 500


if __name__ == '__main__':
    try:
        log("Starting Flask server...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        log(f"Server error: {e}")
