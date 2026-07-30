from fastapi import FastAPI

app = FastAPI(title="이가격 맞아요? API")


@app.get("/health")
def health_check():
    return {"ok": True, "data": {"status": "alive"}, "error": None}


# TODO: 라우터 등록 (API/스키마 확정 후)
# from app.routers import listing, bookmark, history, comparison, transaction, mypage
# app.include_router(listing.router)
# app.include_router(bookmark.router)
# app.include_router(history.router)
# app.include_router(comparison.router)
# app.include_router(transaction.router)
# app.include_router(mypage.router)
