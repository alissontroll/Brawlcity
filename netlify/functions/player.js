const API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjllYzg3ZDRlLTYyMmYtNGQ3Ni04MjUwLTZjMmY5ZTlkYTQ2NiIsImlhdCI6MTc3MTYyNzgyNiwic3ViIjoiZGV2ZWxvcGVyL2U4MjM0ZjYyLWFkZjgtN2UzZC0yYjI5LTk5OGI0YThlN2Q0YSIsInNjb3BlcyI6WyJicmF3bHN0YXJzIl0sImxpbWl0cyI6W3sidGllciI6ImRldmVsb3Blci9zaWx2ZXIiLCJ0eXBlIjoidGhyb3R0bGluZyJ9LHsiY2lkcnMiOlsiNDUuNzkuMjE4Ljc5Il0sInR5cGUiOiJjbGllbnQifV19.KZcuM3VphW4dXtKaSfufaXP4ftNfB0nGnigWyfGaHLIZTnAZGirKPkD1Ph_5jaKNYEuw8Je-DOosaxfFhXAzrw";

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

  const tag = event.queryStringParameters && event.queryStringParameters.tag;
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
        body: JSON.stringify({ error: data.message || data.reason || "Erro da API Brawl Stars", status: res.status })
      };
    }

    return {
      statusCode: 200,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ trophies: data.trophies, name: data.name, tag: data.tag })
    };
  } catch (e) {
    return {
      statusCode: 500,
      headers: { "Access-Control-Allow-Origin": "*" },
      body: JSON.stringify({ error: "Erro interno ao buscar jogador", detail: e.message })
    };
  }
};
