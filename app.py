from flask import Flask, render_template, request, make_response, url_for, send_from_directory
import os
import PyPDF2
import docx
from xhtml2pdf import pisa
from io import BytesIO
import re
from markupsafe import Markup
from gtts import gTTS

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Filter to make links clickable (applied in result.html)
@app.template_filter('make_links_clickable')
def make_links_clickable(text):
    url_pattern = r'(https?://[^\s]+)'
    return Markup(re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', text))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('resumes')
    if not file or file.filename.strip() == '':
        return 'No file selected'

    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # === Extract resume text ===
    resume_text = ""
    ext = filename.split('.')[-1].lower()
    if ext == "pdf":
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                resume_text += page.extract_text() or ""
    elif ext == "docx":
        doc = docx.Document(filepath)
        for para in doc.paragraphs:
            resume_text += para.text + "\n"
    else:
        return "Unsupported file type. Only PDF or DOCX allowed."

    # === Normalize links (even without https) ===
    patterns = [
        (r'\b(www\.[^\s]+)', r'https://\1'),
        (r'\b(github\.com/[^\s]+)', r'https://\1'),
        (r'\b(linkedin\.com/[^\s]+)', r'https://\1'),
        (r'\b(bit\.ly/[^\s]+)', r'https://\1'),
        (r'\b(tinyurl\.com/[^\s]+)', r'https://\1'),
        (r'\b(\w+\.(com|in|org|net|tech|xyz)(/[^\s]*)?)', r'https://\1'),
    ]
    for pattern, repl in patterns:
        resume_text = re.sub(pattern, repl, resume_text)

    # === Skill analysis ===
    skills_list = ["python", "java", "c++", "sql", "html", "css", "flask", "django", "machine learning", "excel"]
    resume_lower = resume_text.lower()
    matched_skills = [skill for skill in skills_list if skill in resume_lower]
    match_score = int((len(matched_skills) / len(skills_list)) * 100)

    # === Generate AI voice feedback ===
    if match_score > 70:
        feedback = "Great job! Your resume shows strong technical skills."
    elif match_score > 40:
        feedback = "Good effort. Consider adding more relevant technical skills."
    else:
        feedback = "Try improving your resume by adding more core tech skills."

    # === Generate and save unique voice file ===
    voice_filename = f"{os.path.splitext(filename)[0]}_feedback.mp3"
    voice_path = os.path.join(app.config['UPLOAD_FOLDER'], voice_filename)
    tts = gTTS(text=feedback, lang='en')
    tts.save(voice_path)

    return render_template('result.html',
                           matched_skills=matched_skills,
                           match_score=match_score,
                           resume_text=resume_text,
                           feedback=feedback,
                           voice_file=voice_filename)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download_report', methods=['POST'])
def download_report():
    matched_skills = request.form.getlist('matched_skills')
    match_score = request.form.get('match_score')
    resume_text = request.form.get('resume_text')

    rendered = render_template('report.html',
                               matched_skills=matched_skills,
                               match_score=match_score,
                               resume_text=resume_text)

    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(rendered, dest=pdf)

    if pisa_status.err:
        return 'Error generating PDF', 500

    response = make_response(pdf.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=ResuScan_Report.pdf'
    return response

if __name__ == '__main__':
    app.run(debug=True)
