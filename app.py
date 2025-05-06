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
        for question_id, answer_values in answers_data.items():
            if question_id == "survey_id":
                continue
                
            try:
                # Convert question_id to ObjectId
                question = db.questions.find_one({"_id": ObjectId(question_id)})
                if question:
                    question_type = question.get("question_type", "unknown")
                    
                    # For each answer value in the list
                    for answer_value in answer_values:
                        answers.append({
                            "survey_id": survey_id,
                            "question_id": question_id,
                            "question_text": question["question_text"],
                            "answer": answer_value,
                            "answer_type": question_type,
                            "submission_date": submission_date,
                            "submission_time": submission_time
                        })
            except Exception as e:
                print(f"Error processing question_id {question_id}: {e}")

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

@app.route('/export_responses', methods=['GET'])
def export_all_responses():
    try:
        # Fetch all responses from the answers collection
        all_responses = list(db.answers.find())
        
        # Create a dictionary to group responses by survey_id, submission_date, submission_time
        grouped_responses = {}
        for response in all_responses:
            survey_id = response.get("survey_id", "Unknown Survey")
            submission_date = response.get("submission_date", "Unknown Date")
            submission_time = response.get("submission_time", "Unknown Time")
            
            # Create a unique key for each submission
            submission_key = f"{survey_id}_{submission_date}_{submission_time}"
            
            if submission_key not in grouped_responses:
                # Get survey details
                survey = None
                try:
                    survey = db.surveys.find_one({"_id": ObjectId(survey_id)})
                except:
                    pass
                
                survey_title = "Unknown Title"
                department = "Unknown Department"
                if survey:
                    survey_title = survey.get("title", "Unknown Title")
                    department = survey.get("department", "Unknown Department")
                
                grouped_responses[submission_key] = {
                    "survey_title": survey_title,
                    "department": department,
                    "submission_date": submission_date,
                    "submission_time": submission_time,
                    "questions_answers": []
                }
            
            # Add this question-answer pair to the submission
            grouped_responses[submission_key]["questions_answers"].append({
                "question": response.get("question_text", "Unknown Question"),
                "answer": response.get("answer", "No Answer")
            })

        # Create a CSV file in memory
        def generate_csv():
            # Find the maximum number of questions in any submission
            max_questions = 0
            for submission_data in grouped_responses.values():
                max_questions = max(max_questions, len(submission_data["questions_answers"]))
            
            # Write the CSV header according to the requested format
            header = "Survey Title,Department,Submission Date,Submission Time"
            
            # Add question/answer columns to the header
            for i in range(1, max_questions + 1):
                header += f",Question {i},Answer {i}"
            
            yield header + "\n"
            
            # Generate each row for the CSV
            for submission_data in grouped_responses.values():
                # Start building the row with the required fields
                row = [
                    f'"{submission_data["survey_title"]}"',
                    f'"{submission_data["department"]}"',
                    f'"{submission_data["submission_date"]}"',
                    f'"{submission_data["submission_time"]}"'
                ]
                
                # Add each question and answer
                questions_answers = submission_data["questions_answers"]
                for i in range(max_questions):
                    if i < len(questions_answers):
                        row.append(f'"{questions_answers[i]["question"]}"')
                        row.append(f'"{questions_answers[i]["answer"]}"')
                    else:
                        row.append('""')  # Empty question
                        row.append('""')  # Empty answer
                
                yield ",".join(row) + "\n"

        # Return the CSV file as a response
        return Response(
            generate_csv(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=all_responses.csv"}
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
