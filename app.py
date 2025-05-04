import random
import csv
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "your-secret-key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scores.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class AnswerRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    question = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

def load_questions(csv_file):
    questions = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append({
                "q": row["question"],
                "a": [row["option1"], row["option2"], row["option3"], row["option4"]],
                "correct": row["correct"],
                "category": row.get("category", "Uncategorized"),
                "hint": row.get("hint", "Article unknown")
            })
    return questions

questions = load_questions("questions.csv")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    num_questions = int(request.form.get('num_questions'))
    session['num_questions'] = num_questions
    session['selected_questions'] = random.sample(questions, num_questions)
    session['user_answers'] = [None] * num_questions
    session['marked_questions'] = [False] * num_questions
    session['answer_requests'] = []
    session['hints_used'] = [False] * num_questions
    session['score'] = 0
    session['username'] = request.form.get('username', 'Anonymous')
    session['start_time'] = datetime.utcnow().isoformat()
    session['current_question'] = 0
    if num_questions == 20:
        session['time_limit'] = 1 * 60 * 60  # 1 hour
    elif num_questions == 40:
        session['time_limit'] = 2 * 60 * 60  # 2 hours
    elif num_questions == 60:
        session['time_limit'] = 3 * 60 * 60  # 3 hours
    elif num_questions == 100:
        session['time_limit'] = 4.5 * 60 * 60  # 4.5 hours
    return redirect(url_for('quiz', question_num=1))

@app.route('/quiz/<int:question_num>', methods=['GET', 'POST'])
def quiz(question_num):
    num_questions = session.get('num_questions', 20)
    selected_questions = session.get('selected_questions', [])
    user_answers = session.get('user_answers', [None] * num_questions)
    marked_questions = session.get('marked_questions', [False] * num_questions)
    answer_requests = session.get('answer_requests', [])
    hints_used = session.get('hints_used', [False] * num_questions)
    score = session.get('score', 0)

    # Timer logic
    start_time = session.get('start_time')
    time_limit = session.get('time_limit', 1 * 60 * 60)
    if start_time:
        start_time = datetime.fromisoformat(start_time)
        elapsed_time = (datetime.utcnow() - start_time).total_seconds()
        remaining_time = max(0, time_limit - elapsed_time)
        if remaining_time <= 0:
            return redirect(url_for('end_test'))
    else:
        elapsed_time = 0
        remaining_time = time_limit

    if question_num < 1 or question_num > num_questions:
        return redirect(url_for('quiz', question_num=1 if question_num < 1 else num_questions))

    if request.method == 'POST':
        action = request.form.get('next_action')
        if action == 'hint':
            hints_used[question_num-1] = True
            session['hints_used'] = hints_used
            question = selected_questions[question_num-1]
            hint = question["hint"]
            return render_template('quiz.html', question=question, question_num=question_num, num_questions=num_questions, user_answer=user_answers[question_num-1], marked=marked_questions[question_num-1], answer_requests=answer_requests, show_time=False, show_hint=True, hint=hint)
        if action == 'check_time':
            current_question = session.get('current_question', 0)
            answered_questions = sum(1 for answer in user_answers[:question_num] if answer is not None)
            if answered_questions > 0:
                avg_time_per_question = elapsed_time / answered_questions
                avg_min_per_question = int(avg_time_per_question // 60)
                avg_sec_per_question = int(avg_time_per_question % 60)
            else:
                avg_min_per_question = 0
                avg_sec_per_question = 0
            questions_left = num_questions - answered_questions
            if questions_left > 0:
                avg_time_per_question_left = remaining_time / questions_left
                avg_min_per_question_left = int(avg_time_per_question_left // 60)
                avg_sec_per_question_left = int(avg_time_per_question_left % 60)
            else:
                avg_min_per_question_left = 0
                avg_sec_per_question_left = 0
            elapsed_min = int(elapsed_time // 60)
            elapsed_sec = int(elapsed_time % 60)
            remaining_min = int(remaining_time // 60)
            remaining_sec = int(remaining_time % 60)
            return render_template('quiz.html', question=selected_questions[question_num-1], question_num=question_num, num_questions=num_questions, user_answer=user_answers[question_num-1], marked=marked_questions[question_num-1], answer_requests=answer_requests, show_time=True, avg_min_per_question=avg_min_per_question, avg_sec_per_question=avg_sec_per_question, avg_min_per_question_left=avg_min_per_question_left, avg_sec_per_question_left=avg_sec_per_question_left, elapsed_min=elapsed_min, elapsed_sec=elapsed_sec, remaining_min=remaining_min, remaining_sec=remaining_sec, show_hint=False)
        if action == 'review_marked':
            marked_indices = [i for i, marked in enumerate(marked_questions) if marked]
            if marked_indices:
                return redirect(url_for('quiz', question_num=marked_indices[0] + 1))
            else:
                return redirect(url_for('quiz', question_num=question_num))
        user_answer = request.form.get('answer')
        mark = 'mark' in request.form
        request_answer = 'request_answer' in request.form
        user_answers[question_num-1] = user_answer
        marked_questions[question_num-1] = mark
        if request_answer:
            answer_requests.append(selected_questions[question_num-1]["q"])
            session['answer_requests'] = answer_requests
        if user_answer and user_answer == selected_questions[question_num-1]["correct"]:
            score += 1
        session['user_answers'] = user_answers
        session['marked_questions'] = marked_questions
        session['score'] = score
        session['current_question'] = question_num
        if action == 'previous':
            return redirect(url_for('quiz', question_num=question_num-1))
        elif action == 'next':
            if question_num == num_questions:
                return redirect(url_for('review_or_end'))
            return redirect(url_for('quiz', question_num=question_num+1))
        elif action == 'finish':
            return redirect(url_for('review_or_end'))

    question = selected_questions[question_num-1]
    return render_template('quiz.html', question=question, question_num=question_num, num_questions=num_questions, user_answer=user_answers[question_num-1], marked=marked_questions[question_num-1], answer_requests=answer_requests, show_time=False, show_hint=False)

@app.route('/review_or_end')
def review_or_end():
    num_questions = session.get('num_questions', 20)
    user_answers = session.get('user_answers', [None] * num_questions)
    has_unanswered = any(answer is None for answer in user_answers)
    return render_template('review_or_end.html', has_unanswered=has_unanswered)

@app.route('/review_unanswered/<int:index>', methods=['GET', 'POST'])
def review_unanswered(index):
    num_questions = session.get('num_questions', 20)
    user_answers = session.get('user_answers', [None] * num_questions)
    unanswered_indices = [i for i, answer in enumerate(user_answers) if answer is None]
    if not unanswered_indices:
        return redirect(url_for('review_or_end'))
    if index >= len(unanswered_indices):
        return redirect(url_for('review_or_end'))
    question_num = unanswered_indices[index] + 1
    return redirect(url_for('quiz', question_num=question_num))

@app.route('/end_test', methods=['POST', 'GET'])
def end_test():
    num_questions = session.get('num_questions', 20)
    selected_questions = session.get('selected_questions', [])
    user_answers = session.get('user_answers', [None] * num_questions)
    answer_requests = session.get('answer_requests', [])
    hints_used = session.get('hints_used', [False] * num_questions)
    score = 0
    # Calculate score
    for i in range(num_questions):
        if user_answers[i] and user_answers[i] == selected_questions[i]["correct"]:
            score += 1
    # Deduct points for hints (2.5% per hint, or half a point per question)
    hint_deductions = sum(0.5 for used in hints_used if used)
    score = max(0, score - hint_deductions)
    # Calculate category percentages
    category_scores = {}
    category_totals = {}
    for i in range(num_questions):
        category = selected_questions[i]["category"]
        category_scores[category] = category_scores.get(category, 0) + (1 if user_answers[i] and user_answers[i] == selected_questions[i]["correct"] else 0)
        category_totals[category] = category_totals.get(category, 0) + 1
    category_percentages = {cat: (category_scores[cat] / category_totals[cat]) * 100 for cat in category_scores}
    total_percentage = (score / num_questions) * 100
    # Save score to database
    new_score = Score(username=session['username'], score=score, percentage=total_percentage)
    db.session.add(new_score)
    db.session.commit()

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        email_answers = 'email_answers' in request.form
        opt_in_text = 'opt_in_text' in request.form
        if answer_requests and username and email:
            for question in answer_requests:
                new_request = AnswerRequest(username=username, email=email, question=question)
                db.session.add(new_request)
            db.session.commit()
        session['user_info'] = {
            'username': username,
            'email': email,
            'phone': phone,
            'email_answers': email_answers,
            'opt_in_text': opt_in_text
        }
        session['final_score'] = {
            'score': score,
            'total': num_questions,
            'category_percentages': category_percentages,
            'total_percentage': total_percentage
        }
        return redirect(url_for('leaderboard'))
    return render_template('result.html', answer_requests=answer_requests)

@app.route('/review_marked/<int:index>', methods=['GET', 'POST'])
def review_marked(index):
    num_questions = session.get('num_questions', 20)
    marked_questions = session.get('marked_questions', [False] * num_questions)
    marked_indices = [i for i, marked in enumerate(marked_questions) if marked]
    if not marked_indices:
        return redirect(url_for('review_or_end'))
    if index >= len(marked_indices):
        return redirect(url_for('review_or_end'))
    question_num = marked_indices[index] + 1
    return redirect(url_for('quiz', question_num=question_num))

@app.route('/leaderboard')
def leaderboard():
    scores = Score.query.order_by(Score.percentage.desc()).limit(10).all()
    final_score = session.get('final_score', None)
    return render_template('leaderboard.html', scores=scores, final_score=final_score)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=8000, debug=True)