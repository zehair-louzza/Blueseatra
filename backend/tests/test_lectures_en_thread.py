"""Les lectures de fichiers et le rendu PDF ne doivent pas bloquer la boucle d'événements
(06/10/2026 : un seul processus uvicorn ; un PDF lent figeait toute l'API)."""
import ast
import os

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server.py")
LOURDS = {"extract_pdf_text", "render_pdf_pages_to_images", "extract_docx_text",
          "extract_xlsx_text", "extract_csv_text", "generate_quote_pdf"}


def test_aucun_appel_direct_aux_fonctions_lourdes_dans_une_route_async():
    arbre = ast.parse(open(SERVER, encoding="utf-8").read())
    fautes = []
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, ast.AsyncFunctionDef):
            continue
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Call) and getattr(noeud.func, "attr", None) in LOURDS:
                fautes.append(f"{fonction.name}:{noeud.lineno} appelle {noeud.func.attr} sans asyncio.to_thread")
    assert not fautes, fautes


def test_les_fonctions_lourdes_sont_bien_passees_a_to_thread():
    source = open(SERVER, encoding="utf-8").read()
    for nom in LOURDS:
        assert f"asyncio.to_thread(ai_service.{nom}" in source or f"asyncio.to_thread(\n            pdf_service.{nom}" in source, nom
