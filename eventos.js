/* =====================================================================
   FEIRA ACONTECE — eventos.js
   Configurações do aplicativo + lista de eventos.

   ESTE É O ÚNICO ARQUIVO QUE VOCÊ PRECISA EDITAR PARA CADASTRAR EVENTOS.
   Não é necessário mexer no index.html.

   ⚠️  ATENÇÃO — DADOS DE DEMONSTRAÇÃO
   Todos os eventos abaixo são FICTÍCIOS e existem apenas para mostrar o
   funcionamento da interface (filtros, mapa, favoritos, etc.).
   Nomes de locais, endereços, preços, organizadores e coordenadas são
   inventados. Substitua-os por informações verdadeiras e depois altere
   modoDemonstracao para false (isso esconde a faixa de aviso).

   COMO ADICIONAR UM EVENTO
   1) Copie o MODELO (logo abaixo de "const EVENTOS = [").
   2) Cole no final da lista, antes do "];".
   3) Troque os dados e salve o arquivo. Atualize a página no navegador.

   REGRAS DOS CAMPOS
   - id ............ texto único, sem repetir (ex.: 'show-banda-x-2026-12-05').
   - titulo ........ nome do evento.
   - descricao ..... texto livre. Use \n para quebrar linha.
   - categoria ..... use EXATAMENTE um destes nomes:
                     'Shows e música' | 'Festas' | 'Cultura e arte' | 'Esportes' |
                     'Gastronomia' | 'Eventos religiosos' | 'Feiras e exposições' |
                     'Eventos familiares' | 'Outros'
   - imagem ........ endereço de uma foto (https://...) OU caminho de um arquivo
                     na mesma pasta (ex.: 'imagens/meu-evento.jpg').
                     Se ficar vazio ou a imagem não abrir, o app mostra uma capa
                     colorida automática.
   - data .......... 'AAAA-MM-DD' (ex.: '2026-12-05').
   - horarioInicio . 'HH:MM' no formato 24 h (ex.: '20:00').
   - horarioFim .... 'HH:MM' ou '' se não souber. Se o fim for menor que o início
                     (ex.: início 22:00, fim 03:00) o app entende que termina no
                     dia seguinte. Sem horário de fim, o app considera
                     duracaoPadraoHoras (veja CONFIG) para saber quando acabou.
   - local ......... nome do estabelecimento/local.
   - endereco ...... endereço completo.
   - latitude / longitude
                     números com ponto decimal (ex.: -12.2664 e -38.9663).
                     Sem coordenadas use null — o evento aparece na lista, mas
                     não ganha marcador no mapa. NUNCA invente coordenadas.
                     Dica: no Google Maps, clique com o botão direito no local e
                     clique nos números que aparecem para copiá-los.
   - googleMaps .... link do Google Maps (opcional). Se vazio, o app gera uma
                     busca com as coordenadas ou com o endereço.
   - preco ......... texto mostrado quando gratuito for false (ex.: 'R$ 30,00').
   - gratuito ...... true ou false (sem aspas). Só é gratuito se estiver true;
                     preço vazio NÃO significa gratuito.
   - organizador ... texto ou '' .
   - fonte ......... link da divulgação original ou '' .
   - destaque ...... true para aparecer na faixa "Em destaque".
   - demo .......... true marca o evento como fictício (selo "Demonstração").
                     Remova esse campo nos eventos reais.

   Eventos que já terminaram somem da lista principal automaticamente, mas
   podem continuar no arquivo (aparecem em "Meus favoritos" como encerrados).
   ===================================================================== */

/* ---------------------------------------------------------------------
   CONFIGURAÇÕES DO APLICATIVO
   --------------------------------------------------------------------- */
const CONFIG = {
  nomeApp: 'Feira Acontece',
  slogan: 'Descubra o que está acontecendo em Feira de Santana',
  cidade: 'Feira de Santana, Bahia',

  // Fuso usado para decidir o que é "hoje", "amanhã" e "acontecendo agora".
  fusoHorario: 'America/Bahia',

  // Centro inicial do mapa (Feira de Santana - BA) e zoom (12 = cidade inteira).
  centroMapa: [-12.2664, -38.9663],
  zoomMapa: 12,

  // Endereço público do app, usado no link de compartilhamento.
  // Quando hospedar o app (ex.: 'https://seunome.github.io/feira-acontece/'),
  // coloque aqui. Vazio = usa o endereço atual da página (se for http/https).
  urlApp: '',

  // true mostra a faixa "eventos fictícios". Coloque false ao usar dados reais.
  modoDemonstracao: true,

  // Quando o evento não tem horário de fim, considera-se esta duração.
  duracaoPadraoHoras: 3,

};

/* ---------------------------------------------------------------------
   LISTA DE EVENTOS
   ⚠️ TODOS OS EVENTOS ABAIXO SÃO FICTÍCIOS (DEMONSTRAÇÃO).
   As datas usam as funções demoDia(), demoProximoDia() e demoAgora() (no fim
   deste arquivo) só para que a demonstração sempre tenha eventos "hoje",
   "amanhã" e "acontecendo agora". Nos eventos reais escreva a data fixa,
   por exemplo:  data: '2026-12-05'
   As coordenadas abaixo são ILUSTRATIVAS: não correspondem a locais reais.
   --------------------------------------------------------------------- */
const EVENTOS = [

  /* ===== MODELO — copie, cole mais abaixo e altere =====
  {
    id: 'meu-evento-001',
    titulo: 'Nome do evento',
    descricao: 'Descrição detalhada do evento.',
    categoria: 'Shows e música',
    imagem: '',                       // https://... ou 'imagens/arquivo.jpg'
    data: '2026-12-05',
    horarioInicio: '20:00',
    horarioFim: '23:00',              // ou ''
    local: 'Nome do local',
    endereco: 'Rua, número – Bairro, Feira de Santana – BA',
    latitude: null,                   // ex.: -12.2664
    longitude: null,                  // ex.: -38.9663
    googleMaps: '',                   // link opcional
    preco: 'R$ 30,00',
    gratuito: false,                  // true = entrada gratuita
    organizador: '',
    fonte: '',
    destaque: false
  },
  ===== FIM DO MODELO ===== */

  /* ---------- Acontecendo agora (demonstração) ---------- */
  {
    id: 'demo-001',
    titulo: 'Noite do Forró Pé de Serra',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nTrês bandas fictícias se revezam no palco com forró pé de serra, xote e baião. Área de comidas típicas e pista aberta.\nEste texto serve apenas para testar a página de detalhes: substitua por informações verdadeiras.',
    categoria: 'Shows e música',
    imagem: 'https://picsum.photos/seed/feira-forro/900/600',
    ...demoAgora(-75),                // começou há 75 min (demo)
    horarioFim: demoHora(165),        // termina daqui a 165 min (demo)
    local: 'Arena Demonstração',
    endereco: 'Rua Exemplo, 100 – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2608,               // coordenada ILUSTRATIVA (fictícia)
    longitude: -38.9641,              // coordenada ILUSTRATIVA (fictícia)
    googleMaps: '',
    preco: 'R$ 40,00 (inteira)',
    gratuito: false,
    organizador: 'Produtora Exemplo (fictícia)',
    fonte: '',
    destaque: true,
    demo: true
  },
  {
    id: 'demo-002',
    titulo: 'Feira de Artesanato e Sabores',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nBarracas de artesanato em couro, cerâmica e bordados, além de comidas regionais. Entrada livre para toda a família.',
    categoria: 'Feiras e exposições',
    imagem: 'https://picsum.photos/seed/feira-artesanato/900/600',
    ...demoAgora(-120),
    horarioFim: demoHora(180),
    local: 'Praça Demonstração',
    endereco: 'Avenida Modelo, s/n – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2689,
    longitude: -38.9702,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: 'Associação Exemplo (fictícia)',
    fonte: '',
    destaque: false,
    demo: true
  },

  /* ---------- Hoje, mais tarde (demonstração) ---------- */
  {
    id: 'demo-003',
    titulo: 'Festa Luau do Sertão',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nFesta temática com DJ, drinks sem álcool e pista ao ar livre. Dress code: estampas tropicais.',
    categoria: 'Festas',
    imagem: 'https://picsum.photos/seed/feira-luau/900/600',
    data: demoDia(0),
    horarioInicio: '21:00',
    horarioFim: '03:00',              // termina na madrugada do dia seguinte
    local: 'Espaço Eventos Demonstração',
    endereco: 'Rua das Palmeiras de Mentira, 250 – Kalilândia, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2531,
    longitude: -38.9569,
    googleMaps: '',
    preco: 'R$ 60,00 (lote único)',
    gratuito: false,
    organizador: 'Coletivo Exemplo (fictício)',
    fonte: '',
    destaque: true,
    demo: true
  },
  {
    id: 'demo-016',
    titulo: 'Café Literário da Manhã (já encerrado hoje)',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO, criado para provar que eventos encerrados não aparecem em "Próximos eventos".',
    categoria: 'Cultura e arte',
    imagem: '',
    ...demoAgora(-300),
    horarioFim: demoHora(-120),
    local: 'Biblioteca Demonstração',
    endereco: 'Rua Livro Imaginário, 12 – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2655,
    longitude: -38.9688,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: '',
    fonte: '',
    destaque: false,
    demo: true
  },

  /* ---------- Amanhã e depois (demonstração) ---------- */
  {
    id: 'demo-005',
    titulo: 'Torneio de Futsal Amador',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nOito times fictícios disputam o troféu em um dia de jogos. Torcida liberada, venda de lanches no local.',
    categoria: 'Esportes',
    imagem: 'https://picsum.photos/seed/feira-futsal/900/600',
    data: demoDia(1),
    horarioInicio: '08:30',
    horarioFim: '17:00',
    local: 'Ginásio Demonstração',
    endereco: 'Rua do Esporte Imaginário, 300 – Capuchinhos, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2723,
    longitude: -38.9588,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: 'Liga Exemplo (fictícia)',
    fonte: '',
    destaque: false,
    demo: true
  },
  {
    id: 'demo-008',
    titulo: 'Domingo em Família no Parque',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nOficinas de pintura para crianças, pula-pula, contação de histórias e piquenique coletivo. Leve sua toalha.',
    categoria: 'Eventos familiares',
    imagem: '',                       // sem imagem: mostra a capa automática
    data: demoProximoDia(0),          // próximo domingo (demo)
    horarioInicio: '09:00',
    horarioFim: '13:00',
    local: 'Parque Demonstração',
    endereco: 'Avenida Verde de Mentira, s/n – Sobradinho, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2405,
    longitude: -38.9512,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: 'Prefeitura Fictícia',
    fonte: '',
    destaque: false,
    demo: true
  },
  {
    id: 'demo-004',
    titulo: 'Celebração Comunitária de Domingo',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO, sem coordenadas, para testar o botão que pesquisa o endereço no Google Maps.\nCelebração aberta à comunidade, seguida de café compartilhado.',
    categoria: 'Eventos religiosos',
    imagem: '',
    data: demoProximoDia(0),
    horarioInicio: '18:00',
    horarioFim: '20:00',
    local: 'Igreja Exemplo',
    endereco: 'Rua da Paz Imaginária, 45 – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: null,                   // sem coordenadas: não aparece no mapa
    longitude: null,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: '',
    fonte: '',
    destaque: false,
    demo: true
  },
  {
    id: 'demo-009',
    titulo: 'Show Acústico Sertanejo',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nApresentação intimista de uma dupla fictícia, com repertório de clássicos e músicas autorais. Mesas disponíveis por ordem de chegada.',
    categoria: 'Shows e música',
    imagem: 'https://picsum.photos/seed/feira-acustico/900/600',
    data: demoProximoDia(6),          // próximo sábado (demo)
    horarioInicio: '20:00',
    horarioFim: '23:30',
    local: 'Bar Demonstração',
    endereco: 'Rua da Música de Mentira, 77 – Ponto Central, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2574,
    longitude: -38.9677,
    googleMaps: 'https://www.google.com/maps/search/?api=1&query=Feira+de+Santana+Bahia', // exemplo de link pronto
    preco: 'A partir de R$ 60,00',
    gratuito: false,
    organizador: 'Produtora Exemplo (fictícia)',
    fonte: 'https://example.com/evento-demonstracao',
    destaque: true,
    demo: true
  },
  {
    id: 'demo-012',
    titulo: 'Aulão de Zumba na Praça',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nAula aberta e gratuita com instrutores fictícios. Leve água e roupa confortável.',
    categoria: 'Esportes',
    imagem: 'https://picsum.photos/seed/feira-zumba/900/600',
    data: demoDia(2),
    horarioInicio: '18:30',
    horarioFim: '20:00',
    local: 'Praça Demonstração',
    endereco: 'Avenida Modelo, s/n – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2689,
    longitude: -38.9702,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: 'Academia Exemplo (fictícia)',
    fonte: '',
    destaque: false,
    demo: true
  },
  {
    id: 'demo-006',
    titulo: 'Festival Gastronômico Sabores da Terra',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nDez cozinhas fictícias servem pratos da culinária sertaneja: carne de sol, maniçoba, bolos e doces regionais. Pagamento por fichas.',
    categoria: 'Gastronomia',
    imagem: '',
    data: demoDia(2),
    horarioInicio: '17:00',
    horarioFim: '22:00',
    local: 'Centro de Eventos Demonstração',
    endereco: 'Avenida dos Sabores Inventados, 900 – Santa Mônica, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2801,
    longitude: -38.9654,
    googleMaps: '',
    preco: 'Entrada R$ 10,00',
    gratuito: false,
    organizador: 'Associação Exemplo (fictícia)',
    fonte: '',
    destaque: false,
    demo: true
  },
  {
    id: 'demo-007',
    titulo: 'Exposição de Arte Popular',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nMostra com esculturas, xilogravuras e pinturas de artistas fictícios, com visita guiada às 19h.',
    categoria: 'Cultura e arte',
    imagem: 'https://picsum.photos/seed/feira-arte/900/600',
    data: demoDia(3),
    horarioInicio: '10:00',
    horarioFim: '19:00',
    local: 'Galeria Demonstração',
    endereco: 'Rua da Arte Imaginária, 18 – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2642,
    longitude: -38.9625,
    googleMaps: '',
    preco: 'R$ 15,00 (meia R$ 7,50)',
    gratuito: false,
    organizador: 'Instituto Exemplo (fictício)',
    fonte: '',
    destaque: true,
    demo: true
  },
  {
    id: 'demo-011',
    titulo: 'Sarau de Poesia Aberta',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO.\nMicrofone aberto para quem quiser recitar, cantar ou contar uma história. Inscrições no local.',
    categoria: 'Cultura e arte',
    imagem: '',
    data: demoDia(4),
    horarioInicio: '19:30',
    horarioFim: '22:00',
    local: 'Café Demonstração',
    endereco: 'Rua dos Versos de Mentira, 5 – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2619,
    longitude: -38.9710,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: 'Coletivo Exemplo (fictício)',
    fonte: 'https://example.com/sarau-demonstracao',
    destaque: false,
    demo: true
  },
  {
    id: 'demo-014',
    titulo: 'Quermesse da Padroeira',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO, sem coordenadas.\nBarracas de comidas típicas, leilão e música ao vivo após a missa.',
    categoria: 'Eventos religiosos',
    imagem: '',
    data: demoDia(5),
    horarioInicio: '18:00',
    horarioFim: '22:30',
    local: 'Largo Demonstração',
    endereco: 'Largo da Imaginação, s/n – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: null,
    longitude: null,
    googleMaps: '',
    preco: '',
    gratuito: true,
    organizador: 'Paróquia Fictícia',
    fonte: '',
    destaque: false,
    demo: true
  },
  {
    id: 'demo-010',
    titulo: 'Encontro de Colecionadores',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO, sem horário de término, sem organizador e sem coordenadas.\nTroca e venda de discos, cartas, moedas e brinquedos antigos.',
    categoria: 'Outros',
    imagem: '',
    data: demoDia(6),
    horarioInicio: '09:00',
    horarioFim: '',
    local: 'Salão Demonstração',
    endereco: 'Rua do Colecionador Inventado, 63 – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: null,
    longitude: null,
    googleMaps: '',
    preco: 'R$ 10,00',
    gratuito: false,
    organizador: '',
    fonte: '',
    destaque: false,
    demo: true
  },

  /* ---------- Já encerrado (demonstração) ---------- */
  {
    id: 'demo-013',
    titulo: 'Show de Ontem (evento encerrado)',
    descricao: 'EVENTO FICTÍCIO DE DEMONSTRAÇÃO. Já aconteceu: não aparece na lista principal, mas os dados continuam no arquivo.',
    categoria: 'Shows e música',
    imagem: '',
    data: demoDia(-1),
    horarioInicio: '20:00',
    horarioFim: '23:00',
    local: 'Arena Demonstração',
    endereco: 'Rua Exemplo, 100 – Centro, Feira de Santana – BA (endereço fictício)',
    latitude: -12.2608,
    longitude: -38.9641,
    googleMaps: '',
    preco: 'R$ 30,00',
    gratuito: false,
    organizador: '',
    fonte: '',
    destaque: false,
    demo: true
  }

  // ← novos eventos entram aqui (lembre da vírgula depois do evento anterior)
];

/* ---------------------------------------------------------------------
   FERRAMENTAS SÓ DA DEMONSTRAÇÃO
   Geram datas e horas relativos a "agora" (fuso America/Bahia) para que a
   demonstração sempre tenha eventos de hoje, amanhã e acontecendo agora.
   Nos eventos reais você NÃO precisa delas: escreva a data e a hora fixas.
   --------------------------------------------------------------------- */
function _demoRelogio() {
  // Relógio "de parede" do fuso configurado, em milissegundos (UTC fictício).
  const p = {};
  new Intl.DateTimeFormat('en-CA', {
    timeZone: CONFIG.fusoHorario, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
  }).formatToParts(new Date()).forEach(function (x) { p[x.type] = x.value; });
  return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute);
}
function _demoPad(n) { return String(n).padStart(2, '0'); }
function _demoData(ms) {
  const d = new Date(ms);
  return d.getUTCFullYear() + '-' + _demoPad(d.getUTCMonth() + 1) + '-' + _demoPad(d.getUTCDate());
}
function _demoHora(ms) {
  const d = new Date(ms);
  return _demoPad(d.getUTCHours()) + ':' + _demoPad(d.getUTCMinutes());
}
// Data de hoje + n dias, no formato 'AAAA-MM-DD'.
function demoDia(n) { return _demoData(_demoRelogio() + n * 86400000); }
// Próxima ocorrência de um dia da semana (0 = domingo ... 6 = sábado); hoje conta.
function demoProximoDia(diaSemana) {
  const base = _demoRelogio();
  const hoje = new Date(base).getUTCDay();
  return _demoData(base + ((diaSemana - hoje + 7) % 7) * 86400000);
}
// { data, horarioInicio } de "agora + minutos".
function demoAgora(minutos) {
  const t = _demoRelogio() + minutos * 60000;
  return { data: _demoData(t), horarioInicio: _demoHora(t) };
}
// 'HH:MM' de "agora + minutos".
function demoHora(minutos) { return _demoHora(_demoRelogio() + minutos * 60000); }
