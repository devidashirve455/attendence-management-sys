from flask import Flask, render_template, request, redirect, url_for
import os
from PyPDF2 import PdfReader
from twilio.rest import Client  # Import Twilio Client
import re  # Add regex for phone number validation

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Twilio configuration
TWILIO_SID = 'AC37f6b17e0582eb52e519c3e794ade054'  # Replace with your Account SID
TWILIO_AUTH_TOKEN = 'fd7394adf947975b4ca785bba2bce9ad'  # Replace with your Auth Token
TWILIO_PHONE_NUMBER = '+12088377457'  # Replace with your Twilio phone number
twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)  # Initialize Twilio client

# Helper function to validate phone number format (E.164)
def is_valid_phone_number(phone_number):
    return re.match(r"^\+?[1-9]\d{1,14}$", phone_number)

# Helper function to format Indian phone numbers
def format_indian_number(contact):
    if not contact.startswith('+'):
        # Assuming it's an Indian phone number if it doesn't have a country code
        contact = '+91' + contact
    return contact

@app.route('/')
def home():
    return "Welcome to the Student Attendance System!"

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file part"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"
        if file and file.filename.endswith('.pdf'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            with open(filepath, 'rb') as f:
                reader = PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""

            students = []
            lines = text.split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[0]
                    attendance = parts[1]
                    contact = parts[-1]
                    if attendance.endswith('%'):
                        try:
                            attendance_percentage = int(attendance[:-1])
                            # Format the contact number for Indian numbers
                            contact = format_indian_number(contact)
                            students.append((name, attendance_percentage, contact))
                        except ValueError:
                            continue

            low_attendance_students = [s for s in students if s[1] < 75]

            response = '''
            <!doctype html>
            <html>
            <head>
                <title>Students with Attendance Below 75%</title>
                <link rel="stylesheet" type="text/css" href="styles.css">  <!-- Link to your CSS file -->
            </head>
            <body>
                <h1>Students with Attendance Below 75%</h1>
                <table border='1'>
                    <tr><th>Name</th><th>Attendance</th><th>Contact</th><th>Action</th></tr>
            '''

            for student in low_attendance_students:
                response += f"<tr><td>{student[0]}</td><td>{student[1]}%</td><td>{student[2]}</td>"
                response += f'<td><a href="/send_sms/{student[2]}/{student[0]}/{student[1]}" style="color: blue; text-decoration: underline;">Send SMS</a></td></tr>'

            response += "</table>"
            if low_attendance_students:
                response += '<button onclick="sendSmsToAll()">Send SMS to All</button>'
            else:
                response += "<p>No students with attendance below 75%.</p>"

            response += '''
            <script>
            function sendSmsToAll() {
                fetch('/send_sms_all', {method: 'POST'})
                .then(response => response.text())
                .then(data => alert(data))
                .catch(error => alert('Error: ' + error));
            }
            </script>
            </body>
            </html>
            '''

            return response

    return '''
    <!doctype html>
    <html>
    <head><title>Upload PDF</title></head>
    <body>
        <h1>Upload a PDF</h1>
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="file" accept="application/pdf">
            <input type="submit" value="Upload">
        </form>
    </body>
    </html>
    '''

@app.route('/send_sms/<contact>/<name>/<attendance>', methods=['GET'])
def send_sms(contact, name, attendance):
    message = f"Dear {name}, your attendance is below 75%. You fall under the attendance criteria, and now your attendance is {attendance}%. So, please be regular in classes."
    
    if not is_valid_phone_number(contact):
        return f"Invalid phone number format for {contact}. Please ensure it's in E.164 format."
    
    try:
        print(f"Sending SMS from {TWILIO_PHONE_NUMBER} to {contact}")
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=contact
        )
        return f"SMS sent to {name} at {contact}!"
    except Exception as e:
        error_message = str(e)
        print(f"Error sending SMS: {error_message}")
        return f"Failed to send SMS to {contact}: {error_message}"

@app.route('/send_sms_all', methods=['POST'])
def send_sms_all():
    # Assuming the last uploaded PDF is used for the low attendance check
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], os.listdir(app.config['UPLOAD_FOLDER'])[-1])
    with open(filepath, 'rb') as f:
        reader = PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

    students = []
    lines = text.split('\n')
    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            name = parts[0]
            attendance = parts[1]
            contact = parts[-1]
            if attendance.endswith('%'):
                try:
                    attendance_percentage = int(attendance[:-1])
                    contact = format_indian_number(contact)
                    students.append((name, attendance_percentage, contact))
                except ValueError:
                    continue

    low_attendance_students = [s for s in students if s[1] < 75]

    messages_sent = []
    for student in low_attendance_students:
        name, attendance, contact = student
        message = f"Dear {name}, your attendance is below 75%. You fall under the attendance criteria, and now your attendance is {attendance}%. So, please be regular in classes."
        
        if is_valid_phone_number(contact):
            try:
                twilio_client.messages.create(
                    body=message,
                    from_=TWILIO_PHONE_NUMBER,
                    to=contact
                )
                messages_sent.append(f"SMS sent to {name} at {contact}!")
            except Exception as e:
                messages_sent.append(f"Failed to send SMS to {name} at {contact}: {str(e)}")
    
    return "<br>".join(messages_sent) if messages_sent else "No SMS sent."

if __name__ == '__main__':
    app.run(debug=True)
