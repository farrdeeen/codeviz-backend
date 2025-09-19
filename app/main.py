from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import analyze

app = FastAPI(title="CodeViz API", version="0.1.0")

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

# mount routers
app.include_router(analyze.router)

@app.get("/")
def root():
    return {"service": "codeviz", "version": "0.1.0"}

@app.get("/favicon.ico")
def favicon():
    return {}
