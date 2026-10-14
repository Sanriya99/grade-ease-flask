import os
import re
from flask import Flask, render_template, request, flash
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer, util

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-for-local-development")
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB upload limit
ALLOWED_EXTENSIONS = {"pdf"}
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# The model is downloaded from Hugging Face on first launch and cached locally.
# This is a free, locally-run model; no API key is required.
model = None

def get_model():
    global model
    if model is None:
        model = SentenceTransformer(MODEL_NAME)
    return model

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_pdf_pages(file_storage):
    """Extract text page-by-page with pypdf. Scanned/image-only PDFs need OCR."""
    reader = PdfReader(file_storage.stream)
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        # Preserve extracted lines while cleaning excessive whitespace.
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        pages.append({"page": page_number, "text": "\n".join(lines), "lines": lines})
    return pages

def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()

def split_answer_blocks(text):
    """
    Split text into question/answer blocks using labels like:
    Q1: ... / 1. ... / Question 1 ... .
    If no labels are found, treat the whole document as one answer.
    """
    text = (text or "").replace("\r", "\n")
    pattern = re.compile(
        r"(?im)^\s*(?:question\s*)?(?:q\s*)?(\d{1,3})\s*[\).:\-]\s*"
    )
    matches = list(pattern.finditer(text))
    if len(matches) >= 2:
        blocks = []
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            block = text[match.end():end].strip()
            blocks.append((match.group(1), normalize(block)))
        return blocks
    return [("1", normalize(text))] if normalize(text) else []

def similarity_score(reference, student):
    if not reference or not student:
        return 0.0
    embeddings = get_model().encode(
        [reference, student], convert_to_tensor=True, normalize_embeddings=True
    )
    cosine = float(util.cos_sim(embeddings[0], embeddings[1]).item())
    # Convert cosine similarity to a bounded 0-100 score.
    return max(0.0, min(100.0, cosine * 100.0))

def keyword_score(reference, student):
    """Simple objective-style comparison: normalized exact match, otherwise token overlap."""
    ref = normalize(reference).lower()
    ans = normalize(student).lower()
    if not ref or not ans:
        return 0.0
    if ref == ans:
        return 100.0
    tokens = set(re.findall(r"\b[\w+-]+\b", ref))
    answer_tokens = set(re.findall(r"\b[\w+-]+\b", ans))
    if not tokens:
        return 0.0
    return 100.0 * len(tokens & answer_tokens) / len(tokens)

def parse_reference_key(text):
    """
    Optional key format:
    Q1 [objective]: Paris
    Q2 [subjective]: Photosynthesis is ...
    Q3 [objective,2]: A process that ...
    The optional number after the comma is the maximum mark; default is 1.
    """
    blocks = split_answer_blocks(text)
    parsed = []
    for number, block in blocks:
        kind = "subjective"
        marks = 1.0
        match = re.match(r"(?is)^\s*\[(objective|subjective)(?:\s*,\s*(\d+(?:\.\d+)?))?\]\s*", block)
        if match:
            kind = match.group(1).lower()
            if match.group(2):
                marks = float(match.group(2))
            block = block[match.end():].strip()
        parsed.append({"number": number, "reference": block, "kind": kind, "max_marks": marks})
    return parsed

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        key_file = request.files.get("answer_key")
        student_file = request.files.get("student_answers")
        if not key_file or not key_file.filename or not student_file or not student_file.filename:
            flash("Please upload both the answer key PDF and the student's answer-sheet PDF.")
            return render_template("index.html")
        if not allowed_file(key_file.filename) or not allowed_file(student_file.filename):
            flash("Only PDF files are supported.")
            return render_template("index.html")

        try:
            key_pages = extract_pdf_pages(key_file)
            student_pages = extract_pdf_pages(student_file)
            key_text = "\n".join(p["text"] for p in key_pages)
            student_text = "\n".join(p["text"] for p in student_pages)
            key_items = parse_reference_key(key_text)
            student_items = dict(split_answer_blocks(student_text))

            results = []
            total_awarded = 0.0
            total_possible = 0.0
            for item in key_items:
                number = item["number"]
                reference = item["reference"]
                student_answer = student_items.get(number, "")
                if item["kind"] == "objective":
                    score = keyword_score(reference, student_answer)
                else:
                    score = similarity_score(reference, student_answer)
                awarded = round(item["max_marks"] * score / 100.0, 2)
                total_awarded += awarded
                total_possible += item["max_marks"]
                results.append({
                    "number": number,
                    "kind": item["kind"],
                    "reference": reference,
                    "student": student_answer or "(No answer extracted for this question)",
                    "similarity": round(score, 1),
                    "awarded": awarded,
                    "max_marks": item["max_marks"],
                })
            percentage = round((total_awarded / total_possible) * 100, 1) if total_possible else 0
            return render_template(
                "result.html", results=results, total_awarded=round(total_awarded, 2),
                total_possible=round(total_possible, 2), percentage=percentage,
                key_pages=key_pages, student_pages=student_pages
            )
        except Exception as exc:
            app.logger.exception("Grading failed")
            flash(f"Could not process these PDFs: {exc}. Check that they contain selectable text.")
            return render_template("index.html")
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
