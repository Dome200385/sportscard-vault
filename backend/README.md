# Backend V0.1

## Local start
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/docs`.

V0.1 is intentionally safe: image upload works, but the recognition adapter does **not** guess unseen card details yet. Locked Fast-Scan context is trusted; unknown critical fields are returned for confirmation. This prevents the LUDEX-style failure mode while the real recognition adapter is implemented.
