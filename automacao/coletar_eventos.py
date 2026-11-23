#!/usr/bin/env python3
# Coletor simples de eventos públicos para Feira Acontece.
# Usa somente RSS público; não faz scraping de Instagram/Facebook.
import datetime as dt
import email.utils
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT_JS = ROOT / "eventos-auto.js"
PENDING = ROOT / "aprovacao" / "pendentes.json"
APPROVED = ROOT / "aprovacao" / "aprovados.json"

# Comece com fontes oficiais. Só amplie depois de verificar a confiabilidade.
TRUSTED_DOMAINS = {
    "feiradesantana.ba.gov.br",
}
QUERIES = [
    '"eventos" "Feira de Santana"',
    '"show" "Feira de Santana" Bahia',
    '"festival" "Feira de Santana"',
    '"feira" "Feira de Santana" evento',
]
# Termos que identificam um evento específico (ex.: Micareta 2026) ou
# uma programação. Evita confundir notícias administrativas com eventos.
EVENT_ANCHORS = re.compile(
    r"\b(micareta|carnaval|s[aã]o jo[aã]o|arrai[aá]|festival|show|concerto|"
    r"espet[aá]culo|pe[cç]a teatral|corrida|campeonato|torneio|sarau|"
    r"exposi[cç][aã]o|feira de artesanato|feira gastron[oô]mica|"
    r"festa|encontro|congresso|conven[cç][aã]o|mostra cultural)\b", re.I
)
GENERIC_EVENT_WORDS = re.compile(
    r"\b(eventos?|festas?|festejos|programa[cç][aã]o|agenda cultural)\b", re.I
)
EVENT_INTENT = re.compile(
    r"\b(acontece|acontecer[aá]|ser[aá] realizado|ser[aá] realizada|"
    r"ser[aã]o realizados|ser[aã]o realizadas|programa[cç][aã]o|ingressos?|"
    r"inscri[cç][oõ]es?|atra[cç][oõ]es|abertura|edi[cç][aã]o|data e hor[aá]rio)\b", re.I
)
ADMIN_ONLY = re.compile(
    r"\b(aprov(a|ou|am)|cr[eé]dito especial|verba|or[cç]amento|repasse|"
    r"licita[cç][aã]o|contrato|emenda parlamentar|presta[cç][aã]o de contas)\b", re.I
)
DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b"),
    re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),
]
MONTHS = {
    "janeiro":1,"fevereiro":2,"março":3,"marco":3,"abril":4,"maio":5,"junho":6,
    "julho":7,"agosto":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12
}
TIME_RE = re.compile(r"\b(?:às?\s*)?([01]?\d|2[0-3])(?:h|:)([0-5]\d)?\b", re.I)

def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def domain_of(url):
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host

def trusted(url):
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in TRUSTED_DOMAINS)

def parse_date(text):
    text = text.lower()
    for p in DATE_PATTERNS:
        m = p.search(text)
        if m:
            try:
                if p is DATE_PATTERNS[0]:
                    day, month, year = map(int, m.groups())
                else:
                    year, month, day = map(int, m.groups())
                return dt.date(year, month, day)
            except ValueError:
                pass
    m = re.search(r"\b(\d{1,2})\s+de\s+([a-zçã]+)(?:\s+de\s+(20\d{2}))?\b", text)
    if m and m.group(2) in MONTHS:
        today = dt.date.today()
        year = int(m.group(3) or today.year)
        try:
            result = dt.date(year, MONTHS[m.group(2)], int(m.group(1)))
            if not m.group(3) and result < today:
                result = dt.date(year + 1, result.month, result.day)
            return result
        except ValueError:
            pass
    return None

def parse_time(text):
    m = TIME_RE.search(text.lower())
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    return f"{hour:02d}:{minute:02d}"

def category(text):
    t = text.lower()
    if any(x in t for x in ["show", "música", "musica", "forró", "forro", "concerto"]): return "Shows e música"
    if any(x in t for x in ["festival", "festa", "micareta", "arraiá", "arraia"]): return "Festas"
    if any(x in t for x in ["esporte", "corrida", "campeonato", "torneio", "futebol"]): return "Esportes"
    if any(x in t for x in ["gastronomia", "comida", "culinária", "culinaria"]): return "Gastronomia"
    if any(x in t for x in ["exposição", "exposicao", "feira", "artesanato"]): return "Feiras e exposições"
    if any(x in t for x in ["teatro", "arte", "cultura", "sarau", "cinema"]): return "Cultura e arte"
    if any(x in t for x in ["igreja", "missa", "religioso", "culto"]): return "Eventos religiosos"
    return "Outros"

def fetch_feed(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"
    })
    req = urllib.request.Request(url, headers={"User-Agent":"FeiraAconteceBot/1.0 (RSS reader)"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return ET.fromstring(response.read())

def read_items():
    found = []
    seen = set()
    for query in QUERIES:
        try:
            xml = fetch_feed(query)
            for item in xml.findall(".//item"):
                title = clean(item.findtext("title"))
                desc = clean(item.findtext("description"))
                link = clean(item.findtext("link"))
                source_el = item.find("source")
                source_url = source_el.attrib.get("url", "") if source_el is not None else link
                source_name = clean(source_el.text if source_el is not None else "")
                key = (title.lower(), link)
                if title and key not in seen:
                    seen.add(key)
                    found.append({"title":title,"description":desc,"link":link,
                                  "source_url":source_url,"source_name":source_name})
        except Exception as exc:
            print(f"[aviso] Não consegui consultar RSS para {query!r}: {exc}")
    return found

def make_record(item):
    text = item["title"] + " " + item["description"]
    date = parse_date(text)
    time = parse_time(text)
    if not date or not time:
        return None, "Não foi possível identificar data e horário completos."
    if date < dt.date.today():
        return None, "A data encontrada já passou."
    title = item["title"]
    # Retira o sufixo comum de manchete: " - Nome da fonte".
    if " - " in title:
        title = title.rsplit(" - ", 1)[0].strip()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().encode("ascii","ignore").decode()).strip("-")[:55]
    event_id = "rss-" + (slug or "evento") + "-" + date.isoformat()
    free = bool(re.search(r"\b(gratuito|gratuita|entrada franca|entrada grátis|entrada gratis)\b", text, re.I))
    price = "" if free else "Consulte a divulgação"
    record = {
        "id": event_id, "titulo": title, "descricao": item["description"][:700],
        "categoria": category(text), "imagem": "", "data": date.isoformat(),
        "horarioInicio": time, "horarioFim": "", "local": "",
        "endereco": "Feira de Santana – BA", "latitude": None, "longitude": None,
        "googleMaps": "", "preco": price, "gratuito": free,
        "organizador": item["source_name"], "fonte": item["link"], "destaque": False
    }
    return record, ""

def main():
    candidates = read_items()
    auto, pending = [], []
    for item in candidates:
        text = item["title"] + " " + item["description"]
        if not re.search(r"feira de santana", text, re.I):
            continue

        # Mantém notícias diretamente ligadas a eventos conhecidos da cidade
        # (por exemplo, Micareta), mesmo quando são informações de serviço.
        has_anchor = bool(EVENT_ANCHORS.search(text))
        has_generic_event = bool(GENERIC_EVENT_WORDS.search(text))
        has_event_intent = bool(EVENT_INTENT.search(text))
        administrative_only = bool(ADMIN_ONLY.search(text)) and not has_anchor
        if administrative_only:
            continue
        if not has_anchor and not (has_generic_event and has_event_intent):
            continue

        record, reason = make_record(item)
        trusted_source = trusted(item["source_url"])
        if record and trusted_source:
            auto.append(record)
        else:
            if has_anchor and not record:
                reason = reason or "Notícia relacionada a um evento; falta confirmar a programação completa."
            pending.append({
                "titulo": item["title"], "descricao": item["description"],
                "link": item["link"], "fonte": item["source_name"],
                "dominio": domain_of(item["source_url"]),
                "motivo": reason or "Fonte ainda não está na lista de fontes confiáveis.",
                "sugestao": record
            })

    # Eventos aprovados manualmente são preservados entre as execuções.
    approved = []
    if APPROVED.exists():
        try:
            approved = json.loads(APPROVED.read_text(encoding="utf-8"))
            if not isinstance(approved, list): approved = []
        except Exception:
            approved = []
    by_id = {}
    for e in approved + auto:
        if isinstance(e, dict) and e.get("id"):
            by_id[e["id"]] = e
    auto = list(by_id.values())

    OUT_JS.write_text(
        "/* Gerado automaticamente. Não edite este arquivo. */\n"
        "var EVENTOS_AUTO = " + json.dumps(auto, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8"
    )
    PENDING.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Eventos publicados automaticamente: {len(auto)}")
    print(f"Itens aguardando revisão: {len(pending)}")

if __name__ == "__main__":
    main()

