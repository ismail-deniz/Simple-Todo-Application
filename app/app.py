
import datetime
import re  
import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__) 

app.secret_key = 'abcdefgh'
  
app.config['MYSQL_HOST'] = 'db'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'cs353hw4db'
  
mysql = MySQL(app)  

@app.route('/')

@app.route('/login', methods =['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM User WHERE username = % s AND password = % s', (username, password, ))
        user = cursor.fetchone()
        if user:              
            session['loggedin'] = True
            session['userid'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            message = 'Logged in successfully!'
            return redirect(url_for('tasks'))
        else:
            message = 'Please enter correct email / password !'
    return render_template('login.html', message = message)


@app.route('/register', methods =['GET', 'POST'])
def register():
    message = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form :
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM User WHERE username = % s', (username, ))
        account = cursor.fetchone()
        if account:
            message = 'Choose a different username!'
  
        elif not username or not password or not email:
            message = 'Please fill out the form!'

        else:
            cursor.execute('INSERT INTO User (id, username, email, password) VALUES (NULL, % s, % s, % s)', (username, email, password,))
            mysql.connection.commit()
            message = 'User successfully created!'

    elif request.method == 'POST':

        message = 'Please fill all the fields!'
    return render_template('register.html', message = message)

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    message = ''
    selected_task = None
    if 'loggedin' in session and session['loggedin']:
        user_id = session['userid']
    else:
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if request.method == 'POST':  
        if 'edit_task' in request.form:
            task_id = request.form['edit_task']
            cursor.execute("SELECT * FROM Task WHERE id = %s", (task_id,))
            selected_task = cursor.fetchone()
            selected_task['deadline'] = selected_task['deadline'].strftime('%Y-%m-%dT%H:%M')

        # Check if the request is for adding a new task
        elif 'title' in request.form:
            title = request.form['title']
            description = request.form['description']
            deadline = request.form['deadline']
            task_type = request.form['task_type']
            status = 'Todo'
            cursor.execute('INSERT INTO Task (title, description, status, deadline, user_id, task_type, creation_time) VALUES (%s, %s, %s, %s, %s, %s, CONVERT_TZ(now(), "UTC", "Europe/Istanbul"))', (title, description, status, deadline, user_id, task_type))
            mysql.connection.commit()
            message = 'Task added successfully'
            return redirect(url_for('tasks'))

    cursor.execute('SELECT * FROM Task WHERE user_id = %s AND status = %s ORDER BY deadline ASC', (user_id, "Todo"))
    tasks = cursor.fetchall()
    cursor.execute('SELECT * FROM Task WHERE user_id = %s AND status = %s ORDER BY deadline ASC', (user_id, "Done"))
    completed_tasks = cursor.fetchall()
    cursor.execute('SELECT * FROM TaskType')
    task_types = cursor.fetchall()
    cursor.close()
    return render_template('tasks.html', tasks=tasks, 
                           completed_tasks=completed_tasks, 
                           task_types=task_types, 
                           message=message, 
                           selected_task=selected_task,
                           user_id = user_id)

@app.route('/logout', methods =['GET', 'POST'])
def logout():
    session['loggedin'] = False
    return redirect(url_for('login'))

@app.route('/tasks/<int:id>/edit', methods =['GET', 'POST'])
def edit(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    title = request.form['title']
    description = request.form['description']
    deadline = request.form['deadline']
    task_type = request.form['task_type']
    status = 'Todo'
    cursor.execute('UPDATE Task SET title = %s, description = %s, status = %s, deadline = %s, task_type = %s WHERE id = %s', (title, description, status, deadline, task_type, id))
    mysql.connection.commit()
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:id>/delete', methods =['GET', 'POST'])
def delete(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('DELETE FROM Task WHERE id = %s', (id,))
    mysql.connection.commit()
    return redirect(url_for('tasks'))

@app.route('/tasks/<int:id>/mark', methods =['GET', 'POST'])
def mark(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    done_time = datetime.datetime.now()
    cursor.execute('UPDATE Task SET status = "Done", done_time = %s WHERE id = %s', (done_time ,id))
    mysql.connection.commit()
    return redirect(url_for('tasks'))

@app.route('/analysis', methods =['GET', 'POST'])
def analysis():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    if 'loggedin' in session and session['loggedin']:
        id = session['userid']
    else:
        return redirect(url_for('login'))
    # Query 1: List the title and latency of the tasks that were completed after their deadlines (for the user)
    cursor.execute("SELECT title, done_time - deadline AS latency FROM Task WHERE status = 'Done' AND done_time > deadline AND user_id = %s", (id,))
    overdue_tasks = cursor.fetchall()
    
    # Query 2: Give the average task completion time of the user
    cursor.execute("SELECT AVG(done_time - creation_time) AS avg_time FROM Task WHERE status = 'Done' AND user_id = %s", (id,))
    avg_completion_time = cursor.fetchone()['avg_time']
    
    # Query 3: List the number of the completed tasks per task type, in descending order (for the user)
    cursor.execute("SELECT task_type, COUNT(*) AS count FROM Task WHERE status = 'Done' AND user_id = %s GROUP BY task_type ORDER BY count DESC", (id,))
    completed_tasks_by_type = cursor.fetchall()
    
    # Query 4: List the title and deadline of uncompleted tasks in increasing order of deadlines (for the user)
    cursor.execute("SELECT title, deadline FROM Task WHERE status = 'Todo' AND user_id = %s ORDER BY deadline ASC", (id,))
    uncompleted_tasks = cursor.fetchall()
    
    # Query 5: List the title and task completion time of the top 2 completed tasks that took the most time, in descending order (for the user)
    cursor.execute("SELECT title, done_time - creation_time AS completion_time FROM Task WHERE status = 'Done' AND user_id = %s ORDER BY completion_time DESC LIMIT 2", (id,))
    top_longest_tasks = cursor.fetchall()

    
    return render_template('analysis.html', overdue_tasks=overdue_tasks, 
                           avg_completion_time=avg_completion_time, 
                           completed_tasks_by_type=completed_tasks_by_type, 
                           uncompleted_tasks=uncompleted_tasks, 
                           top_longest_tasks=top_longest_tasks)


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
