from fastapi import FastAPI

app = FastAPI(title="이가격 맞아요? API")

@app.get("/health")
def health_check():
    return {"ok": True, "data": {"status": "alive"}, "error": None}