const API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImVjZTgwNWFkLTIxZTAtNDhlMy05MzZkLWQxNGE5NzA5OWJhMyIsImlhdCI6MTc3MTYyNDUyNSwic3ViIjoiZGV2ZWxvcGVyL2U4MjM0ZjYyLWFkZjgtN2UzZC0yYjI5LTk5OGI0YThlN2Q0YSIsInNjb3BlcyI6WyJicmF3bHN0YXJzIl0sImxpbWl0cyI6W3sidGllciI6ImRldmVsb3Blci9zaWx2ZXIiLCJ0eXBlIjoidGhyb3R0bGluZyJ9LHsiY2lkcnMiOlsiNDUuNzkuMjE4Ljc5Il0sInR5cGUiOiJjbGllbnQifV19.ASSINATURA";

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: { "Access-Control-Allow-Origin": "*" }, body: "" };
  }
  const tag = event.queryStringParameters && event.queryStringParameters.tag;
  if (!tag) return { statusCode: 400, headers: { "Access-Control-Allow-Origin": "*" }, body: JSON.stringify({ error: "TAG obrigatória" }) };
  const encodedTag = encodeURIComponent(tag.startsWith('#') ? tag : '#' + tag);
  try {
    const res = await fetch(`https://bsproxy.royaleapi.dev/v1/players/${encodedTag}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await res.json();
    if (!res.ok) return { statusCode: res.status, headers: { "Access-Control-Allow-Origin": "*" }, body: JSON.stringify({ error: data.message || "Erro da API" }) };
    return { statusCode: 200, headers: { "Access-Control-Allow-Origin": "*" }, body: JSON.stringify({ trophies: data.trophies, name: data.name }) };
  } catch (e) {
    return { statusCode: 500, headers: { "Access-Control-Allow-Origin": "*" }, body: JSON.stringify({ error: e.message }) };
  }
};
