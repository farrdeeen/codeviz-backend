# app/services/graph.py
from typing import List, Dict, Any

def make_language_nodes(langs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"id": f"lang:{l['name']}", "type": "language", "label": l["name"], "size": max(1, int(l["files"]))}
        for l in langs
    ]

def make_route_nodes(routes: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    return [
        {"id": f"route:{r['verb']} {r['path']}", "type": "route", "label": f"{r['verb']} {r['path']}"}
        for r in routes
    ]

def connect_languages_to_routes(langs: List[Dict[str, Any]], routes: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    top_lang = langs[0]["name"] if langs else "Unknown"
    src = f"lang:{top_lang}"
    for r in routes:
        dst = f"route:{r['verb']} {r['path']}"
        edges.append({"source": src, "target": dst, "type": "uses"})
    return edges

def build_graph(langs: List[Dict[str, Any]], routes: List[Dict[str, str]]) -> Dict[str, Any]:
    lang_nodes = make_language_nodes(langs)
    route_nodes = make_route_nodes(routes)
    edges = connect_languages_to_routes(langs, routes)
    return {"nodes": lang_nodes + route_nodes, "edges": edges}
