#!/usr/bin/env python3
# Feira Acontece — coletor RSS com validação conservadora de município e evento.
# Não acessa redes sociais privadas nem contorna bloqueios.
import datetime as dt
import html
import json
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

# Somente fontes cuja confiabilidade foi explicitamente confirmada podem
# publicar automaticamente. Outras fontes ficam para revisão humana.
TRUSTED_DOMAINS = {"feiradesantana.ba.gov.br"}

QUERIES = [
    '"Micareta de Feira" OR "Micareta de Feira de Santana"',
    '"eventos em Feira de Santana"',
    'shows OR festas OR festivais "Feira de Santana"',
    '"São João" OR "São Pedro" "Feira de Santana" evento',
    'feiras OR exposições OR corrida "Feira de Santana"',
]

EVENT_ANCHORS = re.compile(
    r"\b(micareta|carnaval|s[aã]o jo[aã]o|s[aã]o pedro|arrai[aá]|"
    r"festival|show|concerto|espet[aá]culo|pe[cç]a teatral|corrida|"
    r"campeonato|torneio|sarau|exposi[cç][aã]o|feira de artesanato|"
    r"feira gastron[oô]mica|festa|encontro|congresso|conven[cç][aã]o|"
    r"mostra cultural|circuito cultural)\b", re.I
)
EVENT_INTENT = re.compile(
    r"\b(acontece|acontecer[aá]|ser[aá] realizado|ser[aá] realizada|"
    r"ser[aã]o realizados|ser[aã]o realizadas|programa[cç][aã]o|"
    r"ingressos?|inscri[cç][oõ]es?|atra[cç][oõ]es|abertura|edi[cç][aã]o|"
    r"data e hor[aá]rio|confira a programa[cç][aã]o|vai receber|"
    r"ser[aá] sediado|reunir[aá])\b", re.I
)
ADMIN_TERMS = re.compile(
    r"\b(aprov(a|ou|am)|cr[eé]dito especial|verba|or[cç]amento|repasse|"
    r"licita[cç][aã]o|contrato|emenda parlamentar|presta[cç][aã]o de contas)\b", re.I
)
INFO_ONLY_TERMS = re.compile(
    r"\b(internet gratuita|pontos de internet|tr[aâ]nsito|interdi[cç][aã]o|"
    r"seguran[cç]a refor[cç]ada|servi[cç]os no circuito|estrutura para a festa)\b", re.I
)

# Menções a cidades vizinhas/região não podem ser confundidas com local do evento.
OTHER_MUNICIPALITIES = [
    "Serrinha", "Conceição do Coité", "Conceicao do Coite", "São Gonçalo dos Campos",
    "Sao Goncalo dos Campos", "Amélia Rodrigues", "Amelia Rodrigues", "Conceição da Feira",
    "Conceicao da Feira", "Coração de Maria", "Coracao de Maria", "Irará", "Ira ra",
    "Tanquinho", "Santa Bárbara", "Santa Barbara", "Santanópolis", "Sant anopolis",
    "Riachão do Jacuípe", "Riachao do Jacuipe", "Anguera", "Antônio Cardoso",
    "Antonio Cardoso", "Ipecaetá", "Ipecaeta", "Baixa Grande", "Rafael Jambeiro"
]
OTHER_CITY_RE = re.compile(
    r"\b(" + "|".join(re.escape(x) for x in sorted(OTHER_MUNICIPALITIES, key=len, reverse=True)) + r")\b",
    re.I
)

# Exige uma ligação explícita entre o evento e Feira de Santana.
LOCAL_EVENT_PATTERNS = [
    re.compile(r"\b(micareta|s[aã]o jo[aã]o|s[aã]o pedro|carnaval)\s+de\s+feira(?:\s+de\s+santana)?\b", re.I),
    re.compile(r"\b(em|no|na|de|do|da|para)\s+feira\s+de\s+santana\b", re.I),
    re.compile(r"\bfeira\s+de\s+santana\s+(recebe|sedia|ter[aá]|promove|realiza|vai receber)\b", re.I),
    re.compile(r"\b(circuito|centro|parque|arena|est[aá]dio|pra[cç]a|teatro)\b.{0,100}\bfeira\s+de\s+santana\b", re.I),
    re.compile(r"\bfeira\s+de\s+santana\b.{0,100}\b(circuito|centro|parque|arena|est[aá]dio|pra[cç]a|teatro)\b", re.I),
]
CITY_MENTION_RE = re.compile(r"\bfeira\s+de\s+santana\b", re.I)

DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b"),
    re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b"),
]
MONTHS = {
    "janeiro":1, "fevereiro":2, "março":3, "marco":3, "abril":4, "maio":5,
    "junho":6, "julho":7, "agosto":8, "setembro":9, "outubro":10,
    "novembro":11, "dezembro":12
}
TIME_RE = re.compile(r"\b(?:às?\s*)?([01]?\d|2[0-3])(?:h|:)([0-5]\d)?\b", re.I)

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

def domain_of(url):
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host

def trusted(url):
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in TRUSTED_DOMAINS)

def event_is_in_feira(text):
    """True somente com evidência local positiva e sem cidade vizinha explícita."""
    if not CITY_MENTION_RE.search(text):
        return False, "Não há menção explícita a Feira de Santana."
    # Se o título/texto nomeia outra cidade, não assumir que Feira é o local.
    other = OTHER_CITY_RE.search(text)
    if other:
        return False, f"A publicação também identifica outro município ({other.group(0)}); local do evento não confirmado em Feira."
    if not any(pattern.search(text) for pattern in LOCAL_EVENT_PATTERNS):
        return False, "Feira de Santana foi mencionada, mas não ficou claro que o evento acontece no município."
    return True, ""

def parse_date(text):
    text = text.lower()
    for index, pattern in enumerate(DATE_PATTERNS):
        match = pattern.search(text)
        if match:
            try:
                if index == 0:
                    day, month, year = map(int, match.groups())
                else:
                    year, month, day = map(int, match.groups())
                return dt.date(year, month, day)
            except ValueError:
                pass
    match = re.search(r"\b(\d{1,2})\s+de\s+([a-zçã]+)(?:\s+de\s+(20\d{2}))?\b", text)
    if match and match.group(2) in MONTHS:
        today = dt.date.today()
        year = int(match.group(3) or today.year)
        try:
            result = dt.date(year, MONTHS[match.group(2)], int(match.group(1)))
            if not match.group(3) and result < today:
                result = dt.date(year + 1, result.month, result.day)
            return result
        except ValueError:
            pass
    return None

def parse_time(text):
    match = TIME_RE.search(text.lower())
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2) or 0):02d}"

def category(text):
    t = text.lower()
    if any(x in t for x in ("show", "música", "musica", "forró", "forro", "concerto")):
        return "Shows e música"
    if any(x in t for x in ("festival", "festa", "micareta", "arraiá", "arraia", "carnaval", "são joão", "sao joao")):
        return "Festas"
    if any(x in t for x in ("esporte", "corrida", "campeonato", "torneio", "futebol")):
        return "Esportes"
    if any(x in t for x in ("gastronomia", "comida", "culinária", "culinaria")):
        return "Gastronomia"
    if any(x in t for x in ("exposição", "exposicao", "feira", "artesanato")):
        return "Feiras e exposições"
    if any(x in t for x in ("teatro", "arte", "cultura", "sarau", "cinema")):
        return "Cultura e arte"
    if any(x in t for x in ("igreja", "missa", "religioso", "culto")):
        return "Eventos religiosos"
    return "Outros"

def fetch_feed(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"
    })
    request = urllib.request.Request(url, headers={"User-Agent": "FeiraAconteceBot/2.0 (public RSS reader)"})
    with urllib.request.urlopen(request, timeout=25) as response:
        return ET.fromstring(response.read())

def read_items():
    found, seen = [], set()
    for query in QUERIES:
        try:
            feed = fetch_feed(query)
            for item in feed.findall(".//item"):
                title = clean(item.findtext("title"))
                description = clean(item.findtext("description"))
                link = clean(item.findtext("link"))
                source = item.find("source")
                source_url = source.attrib.get("url", "") if source is not None else link
                source_name = clean(source.text if source is not None else "")
                key = (title.casefold(), link)
                if title and key not in seen:
                    seen.add(key)
                    found.append({
                        "title": title, "description": description, "link": link,
                        "source_url": source_url, "source_name": source_name
                    })
        except Exception as exc:
            print(f"[aviso] Falha no RSS {query!r}: {exc}")
    return found

def make_record(item):
    text = item["title"] + " " + item["description"]
    date = parse_date(text)
    time = parse_time(text)
    if not date:
        return None, "Data do evento não identificada; precisa de revisão."
    if date < dt.date.today():
        return None, "A data identificada já passou."
    title = item["title"]
    if " - " in title:
        title = title.rsplit(" - ", 1)[0].strip()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().encode("ascii", "ignore").decode()).strip("-")[:55]
    event_id = "rss-" + (slug or "evento") + "-" + date.isoformat()
    free = bool(re.search(r"\b(gratuito|gratuita|entrada franca|entrada grátis|entrada gratis)\b", text, re.I))
    record = {
        "id": event_id, "titulo": title, "descricao": item["description"][:700],
        "categoria": category(text), "imagem": "", "data": date.isoformat(),
        "horarioInicio": time or "", "horarioFim": "", "local": "",
        "endereco": "Feira de Santana – BA", "latitude": None, "longitude": None,
        "googleMaps": "", "preco": "" if free else "Consulte a divulgação",
        "gratuito": free, "organizador": item["source_name"],
        "fonte": item["link"], "destaque": False
    }
    if not time:
        return record, "Data identificada, mas horário não encontrado; precisa de revisão."
    return record, ""

def load_json_list(path):
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[aviso] Não foi possível ler {path}: {exc}")
        return []

def main():
    candidates = read_items()
    auto_by_id, pending_by_link = {}, {}

    for item in candidates:
        text = item["title"] + " " + item["description"]
        has_anchor = bool(EVENT_ANCHORS.search(text))
        if not has_anchor:
            continue

        local_ok, local_reason = event_is_in_feira(text)
        if not local_ok:
            # Não encher a fila com notícias regionais ou simples menções à cidade.
            # Só manter casos com cara de evento e motivo claro para revisão.
            if CITY_MENTION_RE.search(text) and not OTHER_CITY_RE.search(text):
                pending_by_link[item["link"]] = {
                    "titulo": item["title"], "descricao": item["description"],
                    "link": item["link"], "fonte": item["source_name"],
                    "dominio": domain_of(item["source_url"]), "motivo": local_reason,
                    "sugestao": None
                }
            continue

        # Notícias administrativas/de serviço não viram eventos automaticamente.
        if ADMIN_TERMS.search(text) and not EVENT_INTENT.search(text):
            pending_by_link[item["link"]] = {
                "titulo": item["title"], "descricao": item["description"],
                "link": item["link"], "fonte": item["source_name"],
                "dominio": domain_of(item["source_url"]),
                "motivo": "Notícia administrativa/informativa sobre evento; não é uma divulgação de programação.",
                "sugestao": None
            }
            continue
        if INFO_ONLY_TERMS.search(text) and not EVENT_INTENT.search(text):
            pending_by_link[item["link"]] = {
                "titulo": item["title"], "descricao": item["description"],
                "link": item["link"], "fonte": item["source_name"],
                "dominio": domain_of(item["source_url"]),
                "motivo": "Informação de serviço sobre evento; não contém divulgação de uma atividade específica.",
                "sugestao": None
            }
            continue

        record, reason = make_record(item)
        is_trusted = trusted(item["source_url"])
        if record and reason == "" and is_trusted and EVENT_INTENT.search(text):
            auto_by_id[record["id"]] = record
        else:
            if not reason:
                reason = "Evento local identificado, mas a fonte ou a divulgação precisa de aprovação."
            pending_by_link[item["link"]] = {
                "titulo": item["title"], "descricao": item["description"],
                "link": item["link"], "fonte": item["source_name"],
                "dominio": domain_of(item["source_url"]), "motivo": reason,
                "sugestao": record
            }

    # Preserva aprovações manuais e combina com os itens confirmados desta execução.
    approved = load_json_list(APPROVED)
    approved_by_id = {
        e["id"]: e for e in approved if isinstance(e, dict) and e.get("id")
    }
    published = dict(approved_by_id)
    published.update(auto_by_id)

    PENDING.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "/* Gerado automaticamente. Não edite este arquivo. */\n"
        "var EVENTOS_AUTO = " + json.dumps(list(published.values()), ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8"
    )
    PENDING.write_text(
        json.dumps(list(pending_by_link.values()), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Fontes RSS analisadas: {len(candidates)}")
    print(f"Eventos publicados automaticamente: {len(auto_by_id)}")
    print(f"Eventos aprovados preservados: {len(approved_by_id)}")
    print(f"Itens aguardando revisão: {len(pending_by_link)}")

if __name__ == "__main__":
    main()

