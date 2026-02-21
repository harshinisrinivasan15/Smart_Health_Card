from flask import Flask
import mysql.connector

app = Flask(__name__)

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  # Your password change this
    database="smart_health_card"
)

@app.route('/')
def home():
    return "Database Connected Successfully!"

if __name__ == '__main__':
    app.run(debug=True)
    