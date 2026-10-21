"""Gera o PDF de um relatório em Markdown (Markdown -> HTML -> PDF via navegador headless).

Uso:
  pip install markdown
  python relatorios/gerar_pdf.py relatorios/relatorio_sprint4.md

Usa o Microsoft Edge ou o Google Chrome instalado na máquina; o HTML intermediário
fica em relatorios/*.html (ignorado pelo Git).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import markdown

CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45;
       max-width: 46em; margin: 0 auto; color: #222; }
h1 { font-size: 20pt; border-bottom: 2px solid #2b6cb0; padding-bottom: 4px; }
h2 { font-size: 14pt; color: #2b6cb0; margin-top: 1.4em; }
table { border-collapse: collapse; width: 100%; margin: 0.6em 0; font-size: 9pt; }
th, td { border: 1px solid #bbb; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #edf2f7; }
code { background: #f4f4f4; padding: 0 3px; font-size: 9pt; }
pre { background: #f4f4f4; padding: 8px; font-size: 8.5pt; overflow-x: auto; }
blockquote { color: #555; border-left: 3px solid #ccc; margin-left: 0; padding-left: 10px; }
@page { size: A4; margin: 18mm 16mm; }
"""

NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge", "google-chrome", "chromium", "chrome",
]


def navegador() -> str:
    for candidato in NAVEGADORES:
        caminho = shutil.which(candidato) or (candidato if Path(candidato).exists() else None)
        if caminho:
            return caminho
    raise SystemExit("Nenhum navegador Edge/Chrome encontrado para gerar o PDF.")


def main():
    origem = Path(sys.argv[1] if len(sys.argv) > 1 else "relatorios/relatorio_sprint4.md").resolve()
    corpo = markdown.markdown(origem.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])
    html = origem.with_suffix(".html")
    html.write_text(f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
                    f"<style>{CSS}</style></head><body>{corpo}</body></html>", encoding="utf-8")
    pdf = origem.with_suffix(".pdf")
    subprocess.run([navegador(), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.as_uri()], check=True, capture_output=True)
    print(f"PDF gerado: {pdf}")


if __name__ == "__main__":
    main()
