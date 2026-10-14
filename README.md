# Grade-Ease — Flask answer-sheet evaluator

A local prototype that accepts:
1. a teacher answer-key PDF
2. a student's answer-sheet PDF

It uses `pypdf` to extract text page-by-page and a free Hugging Face Sentence Transformers model (`sentence-transformers/all-MiniLM-L6-v2`) to estimate semantic similarity for subjective answers. Objective answers use a basic exact-match/token-overlap comparison.

## Requirements

- Python 3.10 or 3.11 recommended
- VS Code with the Python extension
- Internet for the first model download only (after download, the model is cached locally)
- Text-based PDFs. Scanned/handwritten PDFs need OCR and are not supported in this starter version.

## Run on Windows in VS Code (PowerShell)

1. Extract the ZIP file and open the `grade_ease_flask` folder in VS Code.
2. Open **Terminal → New Terminal**.
3. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

4. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this for the current terminal only, then activate again:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

5. Install dependencies:

   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open the local URL printed in the terminal, usually `http://127.0.0.1:5000`.
8. Upload both PDFs and click **Evaluate answers**. The first run downloads the model and may take several minutes.

Stop the server with `Ctrl+C`.

## Answer-key format

Use one numbered answer block per question. The question number must match the student's answer number.

```text
Q1: [objective] Paris
Q2: [subjective,5] Photosynthesis is the process by which green plants use sunlight to make food from carbon dioxide and water.
Q3: [objective,2] Mitochondria
```

- `[objective]` selects simple exact/token-overlap scoring.
- `[subjective]` selects semantic similarity scoring.
- A number after the comma sets the maximum mark.
- If the type is omitted, it defaults to subjective and 1 mark.

For best results, the student PDF should use labels such as `Q1: answer text`, `Q2: answer text`, etc. If question numbering is absent or formatted differently, automatic matching may fail.

## How it works

1. Flask receives both PDF uploads.
2. `pypdf.PdfReader` extracts selectable text from every page, then normalizes each line.
3. The app splits text into numbered answer blocks.
4. Objective answers are scored with exact match or token overlap.
5. Subjective answers are embedded by the Hugging Face sentence-transformer model and compared with cosine similarity.
6. The score is scaled to the question's maximum marks and shown in the results page.

## Important scoring caveat

This is a prototype, not a validated grading system. Semantic similarity does not prove factual correctness, and raw cosine similarity is not a calibrated mark. For a stronger version, define a rubric per question (required concepts, partial-credit rules, accepted alternatives) and have a teacher review the suggested score. Do not use the output as the sole basis for high-stakes grades.

## Troubleshooting

- **`py` is not recognized:** install Python from python.org and select “Add Python to PATH”, then reopen VS Code.
- **Model download fails:** check internet/proxy/firewall access to Hugging Face and retry `python app.py`.
- **`No module named ...`:** activate `.venv` and run `pip install -r requirements.txt` again.
- **No text extracted:** the PDF may be scanned or image-only. OCR is needed; pypdf does not perform OCR.
- **Question numbers do not match:** make sure both PDFs contain numbered answer blocks in a supported format.
