#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FEIRA ACONTECE — coletor RSS com leitura de matérias originais.

Publica automaticamente somente eventos futuros confirmados em Feira de
Santana, quando a fonte pertence à lista confiável. Instagram e fontes não
confiáveis continuam na fila de revisão. Não inventa datas, horários ou locais.
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
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT_JS = ROOT / "eventos-auto.js"
PENDING_JSON = ROOT / "aprovacao" / "pendentes.json"
APPROVED_JSON = ROOT / "aprovacao" / "aprovados.json"

CITY_RE = re.compile(r"\bfeira\s+de\s+santana\b", re.I)
OTHER_CITY_RE = re.compile(
    r"\b(?:micareta|festival|show|festa|evento|corrida)\s+(?:de|em)\s+"
    r"(serrinha|s[aã]o gon[cç]alo dos campos|concei[cç][aã]o do jac[uú]ipe|"
    r"irati|irati?ba|cora[cç][aã]o de maria|am[eé]lia rodrigues)\b", re.I
)
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
TRUSTED_DOMAINS = {
    "feiradesantana.ba.gov.br", "g1.globo.com", "acordacidade.com.br",
    "deolhonacidade.net", "jornalfolhadoestado.com", "jornalgrandebahia.com.br",
}
EVENT_RE = re.compile(
    r"\b(micareta|carnaval|s[aã]o jo[aã]o|s[aã]o pedro|arrai[aá]|festival|"
    r"show|shows|concerto|espet[aá]culo|pe[cç]a teatral|teatro|corrida|"
    r"campeonato|torneio|jogo|sarau|exposi[cç][aã]o|feira gastron[oô]mica|"
    r"feira de artesanato|festa|baile|encontro|congresso|conven[cç][aã]o|"
    r"mostra cultural|programa[cç][aã]o|agenda cultural|apresenta[cç][aã]o|"
    r"atra[cç][oõ]es|ingressos?|inscri[cç][oõ]es?)\b", re.I)
ADMIN_ONLY_RE = re.compile(
    r"\b(licita[cç][aã]o|contrato administrativo|emenda parlamentar|"
    r"presta[cç][aã]o de contas|cr[eé]dito especial|or[cç]amento municipal)\b", re.I)
PAST_RE = re.compile(
    r"\b(aconteceu|foi realizado|foi realizada|reuniu|recebeu p[uú]blico|"
    r"encerrou|terminou|veja como foi|confira como foi|melhores momentos)\b", re.I)
MONTHS = {"janeiro":1,"fevereiro":2,"março":3,"marco":3,"abril":4,"maio":5,
          "junho":6,"julho":7,"agosto":8,"setembro":9,"outubro":10,
          "novembro":11,"dezembro":12}
DATE_NUMERIC_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")
DATE_ISO_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
DATE_TEXT_RE = re.compile(r"\b(\d{1,2})\s+de\s+([a-zçã]+)(?:\s+de\s+(20\d{2}))?\b", re.I)
TIME_RE = re.compile(r"\b(?:às?\s*)?([01]?\d|2[0-3])\s*(?:h|:)([0-5]\d)?\b", re.I)


def clean(value: str | None) -> str:
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
    values = " ".join([item.get("source_url", ""), item.get("link", ""), item.get("source_name", "")]).lower()
    return "instagram.com" in values or "instagram" in values


def parse_date(text: str, today: dt.date | None = None) -> dt.date | None:
    today = today or dt.date.today()
    m = DATE_ISO_RE.search(text)
    if m:
        try: return dt.date(*(int(x) for x in m.groups()))
        except ValueError: pass
    m = DATE_NUMERIC_RE.search(text)
    if m:
        day, month, year = map(int, m.groups())
        try: return dt.date(year, month, day)
        except ValueError: pass
    m = DATE_TEXT_RE.search(text.lower())
    if m:
        day, month, year = int(m.group(1)), MONTHS.get(m.group(2)), int(m.group(3) or today.year)
        if month:
            try: return dt.date(year, month, day)
            except ValueError: pass
    return None


def parse_time(text: str) -> str | None:
    m = TIME_RE.search(text)
    if not m: return None
    return f"{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}"


class ArticleParser(HTMLParser):
    """Extrai texto visível e blocos JSON-LD, ignorando scripts comuns."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.jsonld: list[str] = []
        self._script_type = ""
        self._script_data: list[str] = []
        self._skip = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "script":
            self._script_type = attrs.get("type", "").lower()
            self._script_data = []
            self._skip += 1
        elif tag.lower() in {"style", "noscript", "svg"}:
            self._skip += 1
    def handle_endtag(self, tag):
        if tag.lower() == "script":
            if "ld+json" in self._script_type and self._script_data:
                self.jsonld.append("".join(self._script_data))
            self._script_type = ""
            self._skip = max(0, self._skip - 1)
        elif tag.lower() in {"style", "noscript", "svg"}:
            self._skip = max(0, self._skip - 1)
    def handle_data(self, data):
        if self._skip:
            if self._script_type and "ld+json" in self._script_type:
                self._script_data.append(data)
        elif data.strip():
            self.parts.append(data.strip())


def walk_jsonld(obj):
    if isinstance(obj, dict):
        typ = obj.get("@type", [])
        types = [typ] if isinstance(typ, str) else typ
        if any(str(t).lower() in {"event", "festival", "music event", "sports event"} for t in types):
            yield obj
        for value in obj.values():
            yield from walk_jsonld(value)
    elif isinstance(obj, list):
        for value in obj: yield from walk_jsonld(value)


def fetch_article(url: str) -> tuple[str, list[dict], str]:
    """Busca matéria pública via HTTP; retorna texto, eventos JSON-LD e URL final."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "", [], url
    # Impede endereços locais/privados e limita resposta para não baixar arquivos enormes.
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith((".local", ".internal")):
        return "", [], url
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FeiraAcontece/3.0)",
                                               "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            final_url = response.geturl()
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                return "", [], final_url
            raw = response.read(1_500_000)
            charset = response.headers.get_content_charset() or "utf-8"
        parser = ArticleParser()
        parser.feed(raw.decode(charset, errors="replace"))
        text = clean(" ".join(parser.parts))
        events = []
        for block in parser.jsonld:
            try:
                data = json.loads(block)
                events.extend(walk_jsonld(data))
            except (json.JSONDecodeError, TypeError):
                continue
        return text[:100_000], events, final_url
    except Exception as exc:
        print(f"[AVISO] Não foi possível abrir matéria {url[:100]}: {exc}")
        return "", [], url


def event_details(article_text: str, json_events: list[dict]) -> tuple[dt.date | None, str | None, str]:
    """Prioriza dados estruturados de Event; depois procura data perto de contexto de evento."""
    today = dt.date.today()
    for event in json_events:
        start = event.get("startDate") or event.get("start_date")
        if start:
            parsed = parse_date(str(start))
            if parsed and parsed >= today:
                loc = event.get("location")
                if isinstance(loc, dict):
                    loc_text = " ".join(str(loc.get(k, "")) for k in ("name", "address"))
                    addr = loc.get("address")
                    if isinstance(addr, dict): loc_text += " " + " ".join(str(addr.get(k, "")) for k in addr.values())
                else: loc_text = str(loc or "")
                return parsed, parse_time(str(start)), clean(loc_text)
    # Datas em texto: só aceita quando aparecem em trecho que descreve realização futura.
    patterns = [DATE_ISO_RE, DATE_NUMERIC_RE, DATE_TEXT_RE]
    for pattern in patterns:
        for m in pattern.finditer(article_text):
            start, end = m.span()
            context = article_text[max(0, start-150):min(len(article_text), end+180)]
            if not re.search(r"\b(acontece|ser[aá]|ocorre|realiza|come[cç]a|come[cç]ar[aá]|dia|data|programa[cç][aã]o|apresenta[cç][aã]o|ingressos)\b", context, re.I):
                continue
            d = parse_date(m.group(0))
            if d and d >= today:
                return d, parse_time(context), ""
    return None, None, ""


def category(text: str) -> str:
    t = text.casefold()
    if re.search(r"\b(show|shows|m[uú]sica|forr[oó]|concerto|cantor|cantora)\b", t): return "Shows e música"
    if re.search(r"\b(festival|festa|micareta|carnaval|arrai[aá]|s[aã]o jo[aã]o)\b", t): return "Festas"
    if re.search(r"\b(esporte|corrida|campeonato|torneio|futebol|basquete)\b", t): return "Esportes"
    if re.search(r"\b(gastronomia|comida|culin[aá]ria|gastron[oô]mico)\b", t): return "Gastronomia"
    if re.search(r"\b(exposi[cç][aã]o|artesanato|feira)\b", t): return "Feiras e exposições"
    if re.search(r"\b(teatro|arte|cultura|sarau|cinema|dan[cç]a)\b", t): return "Cultura e arte"
    if re.search(r"\b(igreja|missa|religioso|culto|gospel)\b", t): return "Eventos religiosos"
    return "Outros"


def fetch_feed(query: str) -> ET.Element:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q":query,"hl":"pt-BR","gl":"BR","ceid":"BR:pt-419"})
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 FeiraAcontece/3.0 RSS reader"})
    with urllib.request.urlopen(req, timeout=25) as response: return ET.fromstring(response.read())


def read_items() -> list[dict]:
    found, seen = [], set()
    for query in QUERIES:
        try:
            root = fetch_feed(query)
            for node in root.findall(".//item"):
                title, description, link = clean(node.findtext("title")), clean(node.findtext("description")), clean(node.findtext("link"))
                source_node = node.find("source")
                source_url = source_node.attrib.get("url", "") if source_node is not None else link
                source_name = clean(source_node.text if source_node is not None else "")
                key = (link or title).casefold()
                if not title or key in seen: continue
                seen.add(key)
                found.append({"title":title,"description":description,"link":link,
                              "source_url":source_url or link,"source_name":source_name or domain_of(source_url or link)})
        except Exception as exc: print(f"[AVISO] Falha na consulta {query!r}: {exc}")
    return found


def make_suggestion(item: dict, event_date: dt.date, event_time: str | None, location: str = "") -> dict:
    text = f"{item['title']} {item['description']} {item.get('article_text','')}"
    title = item["title"].rsplit(" - ", 1)[0].strip() if " - " in item["title"] else item["title"]
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold().encode("ascii","ignore").decode()).strip("-")[:55]
    free = bool(re.search(r"\b(gratuito|gratuita|entrada franca|entrada gr[aá]tis)\b", text, re.I))
    # Endereço genérico não é apresentado como endereço confirmado.
    return {"id":f"rss-{slug or 'evento'}-{event_date.isoformat()}","titulo":title,
            "descricao":item.get("article_text", "")[:700] or item["description"][:700],
            "categoria":category(text),"imagem":"","data":event_date.isoformat(),
            "horarioInicio":event_time or "","horarioFim":"","local":location[:180],
            "endereco":"Feira de Santana – BA","latitude":None,"longitude":None,
            "googleMaps":"","preco":"" if free else "Consulte a divulgação","gratuito":free,
            "organizador":item["source_name"],"fonte":item["link"],"destaque":False}


def load_json_list(path: Path) -> list:
    if not path.exists(): return []
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Não foi possível ler {path.relative_to(ROOT)}: {exc}. O arquivo original foi preservado.") from exc
    if not isinstance(data, list): raise RuntimeError(f"{path.relative_to(ROOT)} precisa conter uma lista JSON.")
    return data


def save_json(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    print("=== Feira Acontece: busca de eventos ===")
    candidates = read_items()
    print(f"Resultados brutos encontrados: {len(candidates)}")
    pending_by_key, auto_by_id = {}, {}
    for entry in load_json_list(PENDING_JSON):
        if isinstance(entry, dict):
            key = (entry.get("link") or entry.get("titulo") or "").casefold()
            if key: pending_by_key[key] = entry
    for event in load_json_list(APPROVED_JSON):
        if isinstance(event, dict) and event.get("id"): auto_by_id[event["id"]] = event

    auto_count = 0
    # Evita sobrecarregar sites: abre somente resultados de fontes confiáveis e relevantes.
    article_fetches = 0
    for item in candidates:
        rss_text = f"{item['title']} {item['description']}"
        instagram = is_instagram(item)
        trusted = is_trusted_source(item["source_url"])
        if not CITY_RE.search(rss_text) or not EVENT_RE.search(rss_text): continue
        if OTHER_CITY_RE.search(rss_text):
            reason = "A matéria parece tratar de evento em outro município; não publicar em Feira de Santana."
            suggestion = None
        elif ADMIN_ONLY_RE.search(rss_text) and not re.search(r"\b(show|festival|micareta|festa|corrida|campeonato|programa[cç][aã]o)\b", rss_text, re.I):
            continue
        else:
            reason, suggestion = "", None

        article_text, json_events, final_url = "", [], item["link"]
        if trusted and not instagram and not suggestion and not reason and article_fetches < 80:
            article_text, json_events, final_url = fetch_article(item["link"])
            article_fetches += 1
        item["article_text"] = article_text
        # Confere o destino real após os redirecionamentos do Google News.
        # Se o link terminar em domínio diferente da fonte confiável, não publica.
        final_domain_ok = is_trusted_source(final_url) if article_text else False
        full_text = f"{rss_text} {article_text}"
        # Confirma município também no corpo da matéria; rejeita evento explicitamente de outra cidade.
        city_ok = bool(CITY_RE.search(full_text)) and not OTHER_CITY_RE.search(full_text)
        if not reason and (not city_ok or not EVENT_RE.search(full_text)):
            reason = "A matéria completa não confirmou claramente evento em Feira de Santana."
        event_date, event_time, location = event_details(article_text, json_events) if article_text else (None, None, "")
        if not reason and event_date is None:
            reason = "A matéria original foi consultada, mas não foi encontrada data futura do evento."
        if not reason and PAST_RE.search(full_text):
            reason = "A publicação parece relatar evento passado; conferir antes de aprovar."
        if not reason and not final_domain_ok:
            reason = "O link da matéria não confirmou o domínio confiável após o redirecionamento."
        if not reason and event_date:
            suggestion = make_suggestion(item, event_date, event_time, location)

        # Instagram e fontes não confiáveis nunca são aprovados automaticamente.
        if not reason and trusted and not instagram and suggestion:
            auto_by_id[suggestion["id"]] = suggestion
            auto_count += 1
            continue
        if not reason:
            reason = "Fonte não liberada para publicação automática; precisa de aprovação manual."
        entry = {"titulo":item["title"],"descricao":item["description"],"link":item["link"],
                 "fonte":item["source_name"],"dominio":domain_of(item["source_url"]),
                 "instagram":instagram,"motivo":reason,"sugestao":suggestion}
        key = (item["link"] or item["title"]).casefold()
        pending_by_key[key] = entry

    approved_links = {str(e.get("fonte","")).casefold() for e in auto_by_id.values() if isinstance(e,dict)}
    pending = [e for e in pending_by_key.values() if str(e.get("link","")).casefold() not in approved_links]
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text("/* Gerado automaticamente. Não edite este arquivo. */\nvar EVENTOS_AUTO = "+json.dumps(list(auto_by_id.values()),ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    save_json(PENDING_JSON,pending)
    print(f"Matérias originais consultadas: {article_fetches}")
    print(f"Eventos aprovados/publicados nesta execução: {auto_count}")
    print(f"Eventos aprovados/publicados no total: {len(auto_by_id)}")
    print(f"Itens aguardando revisão: {len(pending)}")
    print(f"Itens vindos do Instagram na fila: {sum(1 for x in pending if x.get('instagram'))}")
    print("Concluído.")
    return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as error:
        print(f"[ERRO] {error}", file=sys.stderr)
        raise

