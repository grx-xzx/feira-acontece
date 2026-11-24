#!/usr/bin/env python3
# Feira Acontece - coletor seguro de eventos futuros de Feira de Santana.
import datetime as dt, html, json, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
OUT_JS=ROOT/'eventos-auto.js'; PENDING=ROOT/'aprovacao'/'pendentes.json'; APPROVED=ROOT/'aprovacao'/'aprovados.json'
TRUSTED_DOMAINS={'feiradesantana.ba.gov.br'}
QUERIES=['"agenda cultural" "Feira de Santana"','"eventos" "Feira de Santana" show','"show" "Feira de Santana" Bahia data','"festival" "Feira de Santana" programação','"inscrições" "Feira de Santana" corrida OR campeonato','"Feira de Santana" "será realizado" evento']
EVENT_WORDS=re.compile(r'\b(show|shows|festival|micareta|carnaval|s[aã]o jo[aã]o|arrai[aá]|corrida|campeonato|torneio|sarau|espet[aá]culo|pe[cç]a teatral|exposi[cç][aã]o|feira gastron[oô]mica|festa|encontro|congresso|conven[cç][aã]o|mostra cultural|apresenta[cç][aã]o musical|programa[cç][aã]o cultural)\b',re.I)
FUTURE_INTENT=re.compile(r'\b(acontecer[aá]|acontece em|ser[aá] realizado|ser[aá] realizada|ser[aã]o realizados|ser[aã]o realizadas|est[aá] marcado|inscri[cç][oõ]es abertas|ingressos [àa] venda|confira a programa[cç][aã]o|vai receber|receber[aá]|realiza no dia|ser[aá] promovido|ser[aá] promovida)\b',re.I)
PAST=re.compile(r'\b(terminou|encerrou|foi encerrad[oa]|aconteceu|reuniu|atraiu p[uú]blico|p[uú]blico se destacou|confira como foi|veja como foi|balan[cç]o|sem registro de|ap[oó]s o evento|durante a edi[cç][aã]o|relembre|lamenta agress[oõ]es)\b',re.I)
ADMIN=re.compile(r'\b(licita[cç][aã]o|contrato|cr[eé]dito especial|emenda parlamentar|or[cç]amento|repasse|presta[cç][aã]o de contas|nomeia|posse|investimento|obra ser[aá] entregue)\b',re.I)
CITY=re.compile(r'\b(feira de santana|em feira|no munic[ií]pio de feira)\b',re.I)
NUM=re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b'); ISO=re.compile(r'\b(20\d{2})-(\d{2})-(\d{2})\b')
MONTHS={'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
TEXTDATE=re.compile(r'\b(\d{1,2}) de ('+'|'.join(MONTHS)+r')(?: de (20\d{2}))?\b',re.I); TIME=re.compile(r'\b(?:às?\s*)?([01]?\d|2[0-3])(?:h|:)([0-5]\d)?\b',re.I)
def clean(s): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()
def domain(url):
 h=(urlparse(url).hostname or '').lower(); return h[4:] if h.startswith('www.') else h
def trusted(url):
 h=domain(url); return any(h==d or h.endswith('.'+d) for d in TRUSTED_DOMAINS)
def parse_date(s,today):
 m=ISO.search(s)
 if m:
  try:return dt.date(*map(int,m.groups()))
  except ValueError:return None
 m=NUM.search(s)
 if m:
  d,mo,y=map(int,m.groups())
  try:return dt.date(y,mo,d)
  except ValueError:return None
 m=TEXTDATE.search(s.lower())
 if m:
  d,mon=int(m.group(1)),m.group(2); y=int(m.group(3)) if m.group(3) else today.year
  try:
   result=dt.date(y,MONTHS[mon],d)
   if not m.group(3) and result<today: result=dt.date(y+1,result.month,result.day)
   return result
  except ValueError:return None
 return None
def parse_time(s):
 m=TIME.search(s.lower()); return f'{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}' if m else None
def category(s):
 t=s.lower()
 if any(x in t for x in ['show','música','musica','forró','forro','concerto']):return 'Shows e música'
 if any(x in t for x in ['festival','festa','micareta','arraiá','arraia']):return 'Festas'
 if any(x in t for x in ['esporte','corrida','campeonato','torneio','futebol']):return 'Esportes'
 if any(x in t for x in ['gastronomia','comida','culinária','culinaria']):return 'Gastronomia'
 if any(x in t for x in ['exposição','exposicao','artesanato']):return 'Feiras e exposições'
 if any(x in t for x in ['teatro','arte','cultura','sarau','cinema']):return 'Cultura e arte'
 return 'Outros'
def fetch(q):
 url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':q,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
 req=urllib.request.Request(url,headers={'User-Agent':'FeiraAcontece/2.0 RSS reader'})
 with urllib.request.urlopen(req,timeout=25) as r:return ET.fromstring(r.read())
def read_items():
 out=[]; seen=set()
 for q in QUERIES:
  try:
   for it in fetch(q).findall('.//item'):
    title=clean(it.findtext('title')); desc=clean(it.findtext('description')); link=clean(it.findtext('link')); src=it.find('source')
    su=src.attrib.get('url','') if src is not None else link; sn=clean(src.text if src is not None else '')
    key=(title.casefold(),link)
    if title and key not in seen: seen.add(key); out.append({'title':title,'description':desc,'link':link,'source_url':su,'source_name':sn})
  except Exception as e: print(f'[aviso] Falha no RSS {q!r}: {e}')
 return out
def make_record(item,today):
 s=item['title']+' '+item['description']; date=parse_date(s,today); time=parse_time(s)
 if not date:return None,'Não encontrei uma data explícita para o evento.'
 if date<today:return None,'A data do evento já passou.'
 if not time:return None,'Não encontrei horário explícito; precisa de revisão.'
 title=item['title'].rsplit(' - ',1)[0].strip() if ' - ' in item['title'] else item['title']
 slug=re.sub(r'[^a-z0-9]+','-',title.lower().encode('ascii','ignore').decode()).strip('-')[:55]
 free=bool(re.search(r'\b(gratuito|gratuita|entrada franca|entrada gr[aá]tis)\b',s,re.I))
 return {'id':'rss-'+(slug or 'evento')+'-'+date.isoformat(),'titulo':title,'descricao':item['description'][:700],'categoria':category(s),'imagem':'','data':date.isoformat(),'horarioInicio':time,'horarioFim':'','local':'','endereco':'Feira de Santana – BA','latitude':None,'longitude':None,'googleMaps':'','preco':'' if free else 'Consulte a divulgação','gratuito':free,'organizador':item['source_name'],'fonte':item['link'],'destaque':False},''
def classify(item,today):
 s=item['title']+' '+item['description']
 if not CITY.search(s):return 'skip','Não há confirmação textual de Feira de Santana.'
 if PAST.search(s):return 'skip','Notícia retrospectiva ou sobre evento já realizado.'
 if ADMIN.search(s):return 'skip','Conteúdo administrativo, não é anúncio de evento.'
 if not EVENT_WORDS.search(s):return 'skip','Não identifiquei um tipo de evento.'
 if not FUTURE_INTENT.search(s):return 'pending','Parece relacionado a evento, mas não confirma divulgação futura.'
 rec,reason=make_record(item,today)
 if not rec:
  if 'já passou' in reason:return 'skip',reason
  return 'pending',reason
 if not trusted(item['source_url']):return 'pending','Evento futuro identificado, mas a fonte ainda não foi autorizada para publicação automática.'
 return 'auto',rec
def load_list(path):
 try:
  data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []; return data if isinstance(data,list) else []
 except Exception as e: print(f'[aviso] Erro lendo {path}: {e}'); return []
def main():
 today=dt.date.today(); auto=[]; pending=[]
 for item in read_items():
  status,result=classify(item,today)
  if status=='auto':auto.append(result)
  elif status=='pending':pending.append({'titulo':item['title'],'descricao':item['description'],'link':item['link'],'fonte':item['source_name'],'dominio':domain(item['source_url']),'motivo':result,'sugestao':None})
 approved=load_list(APPROVED); by_id={}
 for e in approved+auto:
  if isinstance(e,dict) and e.get('id'):by_id[e['id']]=e
 OUT_JS.write_text('/* Gerado automaticamente. Não edite este arquivo. */\nvar EVENTOS_AUTO = '+json.dumps(list(by_id.values()),ensure_ascii=False,indent=2)+';\n',encoding='utf-8')
 PENDING.parent.mkdir(parents=True,exist_ok=True); PENDING.write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'Eventos publicados (aprovados + automáticos): {len(by_id)}'); print(f'Novos eventos aprovados automaticamente: {len(auto)}'); print(f'Itens aguardando revisão: {len(pending)}')
if __name__=='__main__':main()

