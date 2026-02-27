const API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjljZTRjNDI3LTQ0MzMtNDFjZi04MzhkLWZlZTZlYzk4NTJiOSIsImlhdCI6MTc3MTc3MTQzNywic3ViIjoiZGV2ZWxvcGVyL2U4MjM0ZjYyLWFkZjgtN2UzZC0yYjI5LTk5OGI0YThlN2Q0YSIsInNjb3BlcyI6WyJicmF3bHN0YXJzIl0sImxpbWl0cyI6W3sidGllciI6ImRldmVsb3Blci9zaWx2ZXIiLCJ0eXBlIjoidGhyb3R0bGluZyJ9LHsiY2lkcnMiOlsiNDUuNzkuMjE4Ljc5Il0sInR5cGUiOiJjbGllbnQifV19.0an3H-7dBNfLxC01JZB3ZehQ3zw23w6oo3TKLblKXDEtxDbLny3C5xkqVLgPwyzuvD02KQstReqEx7k5MtmPGw";

// Ciclo completo de rotação do Solo Showdown (14 mapas)
const ROTATION_CYCLE = [
  { mapName: 'Crystal Eye Castle', mapId: 15001013 },
  { mapName: 'Acid Lakes',         mapId: 15000015 },
  { mapName: 'Gated Community',    mapId: 15000046 },
  { mapName: 'Cavern Churn',       mapId: 15000006 },
  { mapName: 'Lotus',              mapId: 15000024 },
  { mapName: 'Kroket',             mapId: 15000097 },
  { mapName: 'Feast or Famine',    mapId: 15000007 },
  { mapName: 'Flying Fantasies',   mapId: 15000016 },
  { mapName: 'Lilypond Grove',     mapId: 15001088 },
  { mapName: 'North Park Station', mapId: 15000067 },
  { mapName: 'Twisting Vines',     mapId: 15001064 },
  { mapName: 'Safety Center',      mapId: 15000850 },
  { mapName: 'Skull Creek',        mapId: 15000005 },
  { mapName: 'Makeshift Scaffolding', mapId: 15001141 },
];

function predictNext(currentMapName) {
  const name = (currentMapName || '').toLowerCase().replace(/-/g, ' ').trim();
  for (let i = 0; i < ROTATION_CYCLE.length; i++) {
    if (ROTATION_CYCLE[i].mapName.toLowerCase() === name) {
      return ROTATION_CYCLE[(i + 1) % ROTATION_CYCLE.length];
    }
  }
  return null;
}

const HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json"
};

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: HEADERS, body: "" };
  }

  const params = event.queryStringParameters || {};

  // ---- EVENTOS ----
  if (params.type === 'events') {
    try {
      const res = await fetch('https://bsproxy.royaleapi.dev/v1/events/rotation', {
        headers: { Authorization: `Bearer ${API_KEY}` }
      });

      if (!res.ok) {
        const err = await res.text();
        return { statusCode: res.status, headers: HEADERS, body: JSON.stringify({ error: err }) };
      }

      const raw = await res.json();

      // A API retorna array de eventos diretamente
      const todos = Array.isArray(raw) ? raw : (raw.items || raw.active || []);

      // Log para debug - mostra todos os modos
      const modos = todos.map(ev => {
        const m = ev.event ? ev.event.mode : (ev.mode ? ev.mode.name || ev.mode : 'null');
        const n = ev.event ? ev.event.map : (ev.map ? ev.map.name : 'null');
        return m + '|' + n;
      });

      // Filtra Solo Showdown - testa vários formatos possíveis
      const solo = todos.filter(ev => {
        const mode = ev.event && ev.event.mode ? ev.event.mode :
                     ev.mode && ev.mode.name ? ev.mode.name :
                     ev.mode ? String(ev.mode) : '';
        return mode.toUpperCase().includes('SOLO') || mode === 'soloShowdown';
      });

      // Pega o nome do mapa atual
      let currentMapName = '';
      if (solo.length > 0) {
        const ev = solo[0];
        currentMapName = ev.event ? ev.event.map : (ev.map ? ev.map.name : '');
      }

      const nextMap = predictNext(currentMapName);

      return {
        statusCode: 200,
        headers: HEADERS,
        body: JSON.stringify({
          active: todos,
          nextSoloShowdown: nextMap,
          rotationSize: ROTATION_CYCLE.length,
          debug: { totalEvents: todos.length, modos: modos, soloFound: solo.length, currentMap: currentMapName }
        })
      };
    } catch(e) {
      return { statusCode: 500, headers: HEADERS, body: JSON.stringify({ error: e.message }) };
    }
  }

  // ---- JOGADOR ----
  const tag = params.tag;
  if (!tag) {
    return { statusCode: 400, headers: HEADERS, body: JSON.stringify({ error: "TAG obrigatória" }) };
  }

  const cleanTag = tag.startsWith('#') ? tag : '#' + tag;
  const encodedTag = encodeURIComponent(cleanTag);

  try {
    const res = await fetch(`https://bsproxy.royaleapi.dev/v1/players/${encodedTag}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await res.json();
    if (!res.ok) {
      return { statusCode: res.status, headers: HEADERS, body: JSON.stringify({ error: data.message || "Erro da API" }) };
    }
    const iconId = data.icon && data.icon.id ? data.icon.id : null;

    // Busca mapa de imagens da Brawlify para os brawlers
    // A API retorna a imageUrl correta com o hash/nome do brawler
    // ex: https://cdn.brawlify.com/brawler/Shelly.png (NÃO usa ID numérico)
    let brawlerImgMap = {};
    try {
      const bwRes = await fetch('https://api.brawlify.com/v1/brawlers');
      if (bwRes.ok) {
        const bwData = await bwRes.json();
        (bwData.list || []).forEach(bw => {
          if (bw.id && bw.imageUrl) {
            // Usa a imageUrl exata que a Brawlify fornece (pelo nome, não pelo ID numérico)
            brawlerImgMap[bw.id] = bw.imageUrl;
          }
        });
      }
    } catch(e) {}

    const brawlers = (data.brawlers || []).map(b => ({
      id: b.id,
      name: b.name,
      power: b.power,
      rank: b.rank,
      trophies: b.trophies,
      highestTrophies: b.highestTrophies,
      imageUrl: brawlerImgMap[b.id] || ''
    }));

    return { statusCode: 200, headers: HEADERS, body: JSON.stringify({
      trophies: data.trophies,
      highestTrophies: data.highestTrophies,
      name: data.name,
      tag: data.tag,
      expLevel: data.expLevel,
      brawlerCount: brawlers.length,
      iconId: iconId,
      soloVictories: data.soloVictories,
      duoVictories: data.duoVictories,
      '3vs3Victories': data['3vs3Victories'],
      club: data.club ? { name: data.club.name } : null,
      brawlers: brawlers
    }) };
  } catch(e) {
    return { statusCode: 500, headers: HEADERS, body: JSON.stringify({ error: e.message }) };
  }
};
