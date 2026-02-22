const API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImVjZTgwNWFkLTIxZTAtNDhlMy05MzZkLWQxNGE5NzA5OWJhMyIsImlhdCI6MTc3MTYyNDUyNSwic3ViIjoiZGV2ZWxvcGVyL2U4MjM0ZjYyLWFkZjgtN2UzZC0yYjI5LTk5OGI0YThlN2Q0YSIsInNjb3BlcyI6WyJicmF3bHN0YXJzIl0sImxpbWl0cyI6W3sidGllciI6ImRldmVsb3Blci9zaWx2ZXIiLCJ0eXBlIjoidGhyb3R0bGluZyJ9LHsiY2lkcnMiOlsiMzQuMjI2LjIxMS43MSJdLCJ0eXBlIjoiY2xpZW50In1dfQ.ftWy-AxMIs-ahc76LwE7Ffbb_A7lMajZFKfaQEU-wtvfNlHRUJQeT4rHQ";

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

function predictNextMap(currentMapId) {
  for (let i = 0; i < ROTATION_CYCLE.length; i++) {
    if (ROTATION_CYCLE[i].mapId === currentMapId) {
      // Retorna o próximo, ou volta para o inicio do ciclo
      return ROTATION_CYCLE[(i + 1) % ROTATION_CYCLE.length];
    }
  }
  // Se não achou pelo ID, tenta achar pelo nome usando o mapa atual da API
  return null;
}

function predictNextMapByName(currentMapName) {
  const name = currentMapName.toLowerCase().replace(/-/g, ' ').trim();
  for (let i = 0; i < ROTATION_CYCLE.length; i++) {
    if (ROTATION_CYCLE[i].mapName.toLowerCase() === name) {
      return ROTATION_CYCLE[(i + 1) % ROTATION_CYCLE.length];
    }
  }
  return null;
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
      },
      body: ""
    };
  }

  const params = event.queryStringParameters || {};

  // Rota: buscar eventos + aprender rotacao
  if (params.type === 'events') {
    try {
      const res = await fetch('https://bsproxy.royaleapi.dev/v1/events/rotation', {
        headers: { Authorization: `Bearer ${API_KEY}` }
      });
      const data = await res.json();
      // API pode retornar {items:[]} ou array direto
      const todos = Array.isArray(data) ? data : (data.items || data.active || []);

      // Filtra Solo Showdown
      const soloShowdown = todos.filter(ev => {
        const m = ev.event && ev.event.mode ? ev.event.mode.toUpperCase() : '';
        return m === 'SOLO_SHOWDOWN' || m === 'SOLO SHOWDOWN' || m === 'SOLOSHOWDOWN';
      });

      // Prever próximo mapa usando o ciclo fixo
      let nextMap = null;
      if (soloShowdown.length > 0) {
        const ev = soloShowdown[0];
        const mapId = ev.event && ev.event.id ? ev.event.id : 0;
        const mapName = ev.event && ev.event.map ? ev.event.map : '';
        // Tenta pelo ID primeiro, depois pelo nome
        nextMap = predictNextMap(mapId) || predictNextMapByName(mapName);
      }

      return {
        statusCode: 200,
        headers: { "Access-Control-Allow-Origin": "*" },
        body: JSON.stringify({
          active: todos,
          nextSoloShowdown: nextMap,
          rotationSize: ROTATION_CYCLE.length
        })
      };
    } catch(e) {
      return {
        statusCode: 500,
        headers: { "Access-Control-Allow-Origin": "*" },
        body: JSON.stringify({ error: e.message })
      };
    }
  }

  // Rota: buscar jogador por TAG
  const tag = params.tag;
  if (!tag) {
    return {
      statusCode: 400,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ error: "TAG obrigatória" })
    };
  }

  const cleanTag = tag.startsWith('#') ? tag : '#' + tag;
  const encodedTag = encodeURIComponent(cleanTag);

  try {
    const res = await fetch(`https://bsproxy.royaleapi.dev/v1/players/${encodedTag}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await res.json();

    if (!res.ok) {
      return {
        statusCode: res.status,
        headers: { "Access-Control-Allow-Origin": "*" },
        body: JSON.stringify({ error: data.message || "Erro da API Brawl Stars" })
      };
    }

    return {
      statusCode: 200,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ trophies: data.trophies, name: data.name, tag: data.tag })
    };
  } catch(e) {
    return {
      statusCode: 500,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ error: "Erro interno", detail: e.message })
    };
  }
};
