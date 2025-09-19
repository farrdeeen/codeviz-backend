from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Tuple
import os, tempfile, subprocess, re
from app.services.graph import build_graph

router = APIRouter(prefix="/api", tags=["analyze"])

class AnalyzeRequest(BaseModel):
    repo_url: str

# ---- Language detection (by extension) ----
EXT_TO_LANG: Dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript", ".java": "Java", ".go": "Go", ".rb": "Ruby", ".cs": "C#",
    ".php": "PHP", ".rs": "Rust", ".kt": "Kotlin", ".c": "C", ".cpp": "C++",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON",
}

def detect_languages(root: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for dirpath, _, filenames in os.walk(root):
        # skip heavy/irrelevant dirs
        parts = set(os.path.relpath(dirpath, root).split(os.sep))
        if parts & {".git", ".github", "docs", "docs_src", "tests"}:
            continue
        for f in filenames:
            _, ext = os.path.splitext(f)
            lang = EXT_TO_LANG.get(ext.lower())
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    return counts

# ---- FastAPI route extraction (regex MVP) ----
ROUTE_DECORATOR_RE = re.compile(
    r"""@(?P<prefix>\w+)\.(?P<verb>get|post|put|delete|patch|options|head)\(\s*["'](?P<path>[^"']*)["']""",
    re.IGNORECASE,
)

SKIP_DIRS = {".git", ".github", "docs", "docs_src", "tests"}

def extract_routes(root: str) -> List[Dict[str, str]]:
    routes: List[Dict[str, str]] = []
    for dirpath, _, filenames in os.walk(root):
        parts = set(os.path.relpath(dirpath, root).split(os.sep))
        if parts & SKIP_DIRS:
            continue
        for f in filenames:
            if not f.endswith(".py"):
                continue
            fp = os.path.join(dirpath, f)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
                for m in ROUTE_DECORATOR_RE.finditer(text):
                    verb = m.group("verb").upper()
                    path = m.group("path")
                    prefix = m.group("prefix")
                    routes.append({
                        "file": os.path.relpath(fp, root).replace("\\", "/"),
                        "verb": verb,
                        "path": path,
                        "via": prefix,
                    })
            except Exception:
                continue
    return routes

def unique_routes(routes: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[Tuple[str, str]] = set()
    uniq: List[Dict[str, str]] = []
    for r in routes:
        key = (r["verb"], r["path"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq

@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    repo_url = req.repo_url.strip()
    if not (repo_url.startswith("https://github.com/") or repo_url.startswith("http://github.com/")):
        raise HTTPException(status_code=400, detail="Provide a public GitHub HTTPS URL")
    try:
        with tempfile.TemporaryDirectory(prefix="codeviz_") as tmpdir:
            # Shallow & partial clone for speed/low bandwidth
            cmd = ["git", "clone", "--depth", "1", "--no-tags", "--filter=blob:none", repo_url, tmpdir]
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            entries: List[str] = sorted(os.listdir(tmpdir))[:50]

            # Language summary
            langs = detect_languages(tmpdir)
            top = sorted(langs.items(), key=lambda x: (-x[1], x[0]))[:5]

            # Route extraction with filtering and de-dup
            routes = extract_routes(tmpdir)
            routes = unique_routes(routes)
            routes = sorted(routes, key=lambda r: (r["path"], r["verb"]))[:200]

            graph = build_graph([{"name": k, "files": v} for k, v in top], routes)
            return {
                "cloned": True,
                "entries": entries,
                "languages": [{"name": k, "files": v} for k, v in top],
                "routes": routes,
                "counts": {"routes": len(routes)},
                "graph": graph,
            }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Git clone timed out after 60s")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="git not found on PATH; install Git and restart the server")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or str(e)).strip()
        raise HTTPException(status_code=400, detail=f"Git clone failed: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
