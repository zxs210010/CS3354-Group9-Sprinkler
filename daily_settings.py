from flask import Flask, render_template, request
import sqlite3
import json

app = Flask(__name__)
DB_NAME = 'aquathink.db'

@app.route('/daily_settings', methods=['GET', 'POST'])
def daily_settings():
    message = ''
    if request.method == 'POST':
        user_id = 1
        all_days_data = json.loads(request.form.get('all_days_data', '{}'))
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    day_of_week TEXT,
                    max_water_gallons INTEGER,
                    max_duration_min INTEGER
                )
            ''')
            
            for day, data in all_days_data.items():
                water = int(data.get('water') or 0)
                duration = int(data.get('duration') or 0)
                if water > 0 or duration > 0:
                    # Overwrite previous settings for this day and user
                    cursor.execute('DELETE FROM daily_settings WHERE user_id = ? AND day_of_week = ?', (user_id, day))
                    cursor.execute('INSERT INTO daily_settings (user_id, day_of_week, max_water_gallons, max_duration_min) VALUES (?, ?, ?, ?)', (user_id, day, water, duration))
            
            conn.commit()
            conn.close()
            message = "All daily settings successfully saved and updated!"
        except Exception as e:
            message = f"Database Error: {e}"
            
    return render_template('daily_settings.html', message=message)

if __name__ == '__main__':
    # Running on port 5001 so it can run concurrently with the account app if needed
    app.run(debug=True, port=5001)