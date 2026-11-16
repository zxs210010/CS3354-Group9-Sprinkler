from flask import Flask, render_template, request
import sqlite3

app = Flask(__name__)
DB_NAME = 'aquathink.db'

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    message = ''
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if email and password:
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL
                    )
                ''')
                cursor.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password))
                conn.commit()
                conn.close()
                message = f"Account successfully created for {email}!"
            except sqlite3.IntegrityError:
                message = "Error: Email already exists."
        else:
            message = "Error: Fields cannot be blank."
    return render_template('create_account.html', message=message)

if __name__ == '__main__':
    app.run(debug=True, port=5000)