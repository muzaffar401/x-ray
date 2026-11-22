# XRay Report AI - Project Rules
## What this product is
A web app where a doctor uploads a chest X-ray image. The system creates a DRAFT radiology report (Findings + Impression). The doctor edits and approves it. The AI never gives a final diagnosis.
## Tech stack (do not change without asking me)
- Python 3.11+, FastAPI, SQLite with SQLAlchemy, pytest
- Frontend: plain HTML, CSS and JavaScript inside app/static (no React, no build step, no CDN)
- Image tools: Pillow and pydicom. PDF: reportlab.
## Working rules
1. Do ONE task at a time. Never build features that I did not ask for in the current prompt.
2. Before writing code, tell me your plan in 5 lines or less.
3. After writing code, run the tests and run the app. Show me the real output. If something fails, fix it. Never say "done" if you did not run it.
4. Never guess the API of a library or a model. If you are not sure, read the official documentation first, or ask me.
5. Keep code simple, with short comments. Use small files and clear names.
6. Never hardcode secrets. Use a .env file and keep .env.example updated.
7. After each finished task, make a git commit with a clear message.
## Safety rules (very important)
- Every screen and every PDF that shows an AI report must show this text: "AI-generated DRAFT. Must be reviewed and approved by a qualified radiologist. Not a final diagnosis."
- Never use real patient data in this project folder. Use only fake or synthetic sample data.
- Never add medical claims such as "accurate", "FDA approved" or "diagnoses disease".
## After every task, reply with (1) what you changed, (2) how to run it, (3) how I can test it, (4) what is still not done.
