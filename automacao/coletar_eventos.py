#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEIRA ACONTECE — Coletor de eventos públicos.

Fontes:
- Google News RSS para sites, jornais e páginas públicas indexadas.
- Consultas específicas por Instagram (site:instagram.com).
Importante:
- Não faz login nem scraping de páginas privadas do Instagram.
- O Google News pode não indexar todos os posts públicos.
- Fontes não oficiais entram em aprovacao/pendentes.json.
- Só a Prefeitura (domínio oficial) pode publicar automaticamente, e apenas
  quando data e horário futuros forem identificados com segurança.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse


# O arquivo fica em /automacao/coletar_eventos.py dentro do repositório.
ROOT = Path(__file__).resolve().parents[1]
OUT_JS = ROOT / "eventos-auto.js"
PENDING_JSON = ROOT / "aprovacao" / "pendentes.json"
APPROVED_JSON = ROOT / "aprovacao" / "aprovados.json"

CITY_RE = re.compile(r"\bfeira\s+de\s+santana\b", re.I)

# Consultas gerais + consultas explícitas para publicações públicas indexadas
# do Instagram. A busca é feita pelo RSS do Google News, não pela API privada.
QUERIES = [
    '"eventos" "Feira de Santana" Bahia',
    '"agenda cultural" "Feira de Santana"',
    'show OR shows OR concerto "Feira de Santana" Bahia',
    'festival OR festa OR micareta "Feira de Santana"',
    'corrida OR campeonato OR torneio "Feira de Santana" evento',
    'teatro OR exposição OR feira gastronômica "Feira de Santana"',
    'site:instagram.com "Feira de Santana" (show OR evento OR festa)',
    'site:instagram.com "Feira de Santana" (festival OR micareta OR São João)',
    'site:instagram.com "Feira de Santana" (ingressos OR programação OR atrações)',
]

# Apenas esse domínio é considerado oficial para publicação automática.
# Instagram, G1, jornais e demais fontes sempre vão para revisão manual.
TRUSTED_DOMAINS = {"feiradesantana.ba.gov.br"}

EVENT_RE = re.compile(
    r"\b(micareta|carnaval|s[aã]o jo[aã]o|s[aã]o pedro|arrai[aá]|"
    r"festival|show|shows|concerto|espet[aá]culo|pe[cç]a teatral|teatro|"
    r"corrida|campeonato|torneio|jogo|sarau|exposi[cç][aã]o|"
    r"feira gastron[oô]mica|feira de artesanato|festa|baile|"
    r"encontro|congresso|conven[cç][aã]o|mostra cultural|"
    r"programa[cç][aã]o|agenda cultural|apresenta[cç][aã]o|"
    r"atra[cç][oõ]es|ingressos?|inscri[cç][oõ]es?)\b",
    re.I,
)
ADMIN_ONLY_RE = re.compile(
    r"\b(licita[cç][aã]o|contrato administrativo|emenda parlamentar|"
    r"presta[cç][aã]o de contas|cr[eé]dito especial|or[cç]amento municipal)\b",
    re.I,
)
PAST_RE = re.compile(
    r"\b(aconteceu|foi realizado|foi realizada|reuniu|recebeu p[uú]blico|"
    r"encerrou|terminou|veja como foi|confira como foi|melhores momentos)\b",
    re.I,
)

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
    "abril": 4, "maio": 5, "junho": 6, "julho": 7,
    "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
DATE_NUMERIC_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")
DATE_ISO_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2})\s+de\s+([a-zçã]+)(?:\s+de\s+(20\d{2}))?\b", re.I
)
TIME_RE = re.compile(
    r"\b(?:às?\s*)?([01]?\d|2[0-3])\s*(?:h|:)\s*([0-5]\d)?\b", re.I
)


def clean(value: str | None) -> str:
    """Remove HTML simples e espaços repetidos."""
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def domain_of(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def is_trusted_source(url: str) -> bool:
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in TRUSTED_DOMAINS)


def is_instagram(item: dict) -> bool:
    values = " ".join([
        item.get("source_url", ""),
        item.get("link", ""),
        item.get("source_name", ""),
    ]).lower()
    return "instagram.com" in values or "instagram" in values


def parse_date(text: str, today: dt.date | None = None) -> dt.date | None:
    """Lê datas explícitas; não usa a data de publicação da notícia."""
    today = today or dt.date.today()

    match = DATE_ISO_RE.search(text)
    if match:
        try:
            return dt.date(*(int(x) for x in match.groups()))
        except ValueError:
            pass

    match = DATE_NUMERIC_RE.search(text)
    if match:
        day, month, year = map(int, match.groups())
        try:
            return dt.date(year, month, day)
        except ValueError:
            pass

    match = DATE_TEXT_RE.search(text.lower())
    if match:
        day = int(match.group(1))
        month = MONTHS.get(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        if month:
            try:
                result = dt.date(year, month, day)
                # Sem ano explícito, se a data já passou, não inventa ano futuro.
                return result
            except ValueError:
                pass
    return None


def parse_time(text: str) -> str | None:
    match = TIME_RE.search(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    return f"{hour:02d}:{minute:02d}"


def category(text: str) -> str:
    t = text.casefold()
    if re.search(r"\b(show|shows|m[uú]sica|forr[oó]|concerto|cantor|cantora)\b", t):
        return "Shows e música"
    if re.search(r"\b(festival|festa|micareta|carnaval|arrai[aá]|s[aã]o jo[aã]o)\b", t):
        return "Festas"
    if re.search(r"\b(esporte|corrida|campeonato|torneio|futebol|basquete)\b", t):
        return "Esportes"
    if re.search(r"\b(gastronomia|comida|culin[aá]ria|gastron[oô]mico)\b", t):
        return "Gastronomia"
    if re.search(r"\b(exposi[cç][aã]o|artesanato|feira)\b", t):
        return "Feiras e exposições"
    if re.search(r"\b(teatro|arte|cultura|sarau|cinema|dan[cç]a)\b", t):
        return "Cultura e arte"
    if re.search(r"\b(igreja|missa|religioso|culto|gospel)\b", t):
        return "Eventos religiosos"
    return "Outros"


def fetch_feed(query: str) -> ET.Element:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419",
    })
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 FeiraAcontece/2.0 RSS reader"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return ET.fromstring(response.read())


def read_items() -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    for query in QUERIES:
        try:
            root = fetch_feed(query)
            for node in root.findall(".//item"):
                title = clean(node.findtext("title"))
                description = clean(node.findtext("description"))
                link = clean(node.findtext("link"))
                source_node = node.find("source")
                source_url = (
                    source_node.attrib.get("url", "")
                    if source_node is not None else link
                )
                source_name = clean(
                    source_node.text if source_node is not None else ""
                )
                key = (link or title).casefold()
                if not title or key in seen:
                    continue
                seen.add(key)
                found.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "source_url": source_url or link,
                    "source_name": source_name or domain_of(source_url or link),
                })
        except Exception as exc:
            print(f"[AVISO] Falha na consulta {query!r}: {exc}")
    return found


def make_suggestion(item: dict) -> dict | None:
    """Cria sugestão parcial; campos desconhecidos ficam vazios, nunca inventados."""
    text = f"{item['title']} {item['description']}"
    event_date = parse_date(text)
    event_time = parse_time(text)

    if event_date is None or event_date < dt.date.today():
        return None

    title = item["title"]
    if " - " in title:
        title = title.rsplit(" - ", 1)[0].strip()

    slug = re.sub(
        r"[^a-z0-9]+", "-", title.casefold().encode("ascii", "ignore").decode()
    ).strip("-")[:55]
    event_id = f"rss-{slug or 'evento'}-{event_date.isoformat()}"
    free = bool(re.search(
        r"\b(gratuito|gratuita|entrada franca|entrada gr[aá]tis)\b", text, re.I
    ))

    return {
        "id": event_id,
        "titulo": title,
        "descricao": item["description"][:700],
        "categoria": category(text),
        "imagem": "",
        "data": event_date.isoformat(),
        "horarioInicio": event_time or "",
        "horarioFim": "",
        "local": "",
        "endereco": "Feira de Santana – BA",
        "latitude": None,
        "longitude": None,
        "googleMaps": "",
        "preco": "" if free else "Consulte a divulgação",
        "gratuito": free,
        "organizador": item["source_name"],
        "fonte": item["link"],
        "destaque": False,
    }


def load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Não foi possível ler {path.relative_to(ROOT)}: {exc}. "
            "O arquivo original foi preservado."
        ) from exc
    if not isinstance(data, list):
        raise RuntimeError(f"{path.relative_to(ROOT)} precisa conter uma lista JSON.")
    return data


def save_json(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    print("=== Feira Acontece: busca de eventos ===")
    candidates = read_items()
    print(f"Resultados brutos encontrados: {len(candidates)}")

    pending_by_key: dict[str, dict] = {}
    auto_by_id: dict[str, dict] = {}

    # Mantém itens anteriores na fila para não apagar revisões pendentes.
    old_pending = load_json_list(PENDING_JSON)
    for entry in old_pending:
        if isinstance(entry, dict):
            key = (entry.get("link") or entry.get("titulo") or "").casefold()
            if key:
                pending_by_key[key] = entry

    approved = load_json_list(APPROVED_JSON)
    for event in approved:
        if isinstance(event, dict) and event.get("id"):
            auto_by_id[event["id"]] = event

    for item in candidates:
        text = f"{item['title']} {item['description']}"

        # Cidade deve aparecer no conteúdo do resultado.
        if not CITY_RE.search(text):
            continue
        if not EVENT_RE.search(text):
            continue
        if ADMIN_ONLY_RE.search(text) and not re.search(
            r"\b(show|festival|micareta|festa|corrida|campeonato|programa[cç][aã]o)\b",
            text, re.I
        ):
            continue

        suggestion = make_suggestion(item)
        instagram = is_instagram(item)
        official = is_trusted_source(item["source_url"])

        # Só publica automaticamente fonte oficial + data + horário futuros.
        # Instagram, G1 e demais sites sempre aguardam aprovação humana.
        if official and suggestion and suggestion.get("horarioInicio"):
            auto_by_id[suggestion["id"]] = suggestion
            continue

        if PAST_RE.search(text):
            reason = "A publicação parece relatar um evento que já aconteceu; conferir antes de aprovar."
        elif instagram:
            reason = "Possível divulgação pública do Instagram; conferir a publicação original e os dados."
        elif not suggestion:
            reason = "Possível evento em Feira de Santana; faltam data futura confirmada e/ou informações completas."
        elif not suggestion.get("horarioInicio"):
            reason = "Data identificada, mas o horário não foi encontrado."
        else:
            reason = "Fonte encontrada, mas ainda precisa de conferência manual."

        entry = {
            "titulo": item["title"],
            "descricao": item["description"],
            "link": item["link"],
            "fonte": item["source_name"],
            "dominio": domain_of(item["source_url"]),
            "instagram": instagram,
            "motivo": reason,
            "sugestao": suggestion,
        }
        key = (item["link"] or item["title"]).casefold()
        pending_by_key[key] = entry

    # Remove da fila os que já foram aprovados.
    approved_links = {
        str(event.get("fonte", "")).casefold()
        for event in auto_by_id.values() if isinstance(event, dict)
    }
    pending = [
        item for item in pending_by_key.values()
        if str(item.get("link", "")).casefold() not in approved_links
    ]

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "/* Gerado automaticamente. Não edite este arquivo. */\n"
        "var EVENTOS_AUTO = "
        + json.dumps(list(auto_by_id.values()), ensure_ascii=False, indent=2)
        + ";\n"
    )
    OUT_JS.write_text(js, encoding="utf-8")
    save_json(PENDING_JSON, pending)

    instagram_count = sum(1 for item in pending if item.get("instagram"))
    print(f"Eventos aprovados/publicados: {len(auto_by_id)}")
    print(f"Itens aguardando revisão: {len(pending)}")
    print(f"Itens vindos do Instagram na fila: {instagram_count}")
    print("Concluído.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"[ERRO] {error}", file=sys.stderr)
        raise

