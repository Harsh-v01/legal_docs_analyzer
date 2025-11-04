from flask import Flask, render_template, request, redirect, url_for
from pathlib import Path
import os
from contract_analyzer import analyze_contract

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED = {'.txt', '.docx'}

def allowed_file(filename):
    return '.' in filename and Path(filename).suffix.lower() in ALLOWED

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f:
            return render_template('index.html', error="No file uploaded")
        if not allowed_file(f.filename):
            return render_template('index.html', error="File type not allowed. Use .txt or .docx")
        save_path = Path(app.config['UPLOAD_FOLDER']) / f.filename
        f.save(save_path)
        result = analyze_contract(str(save_path))
        return render_template('index.html', result=result)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
