import os
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request, send_from_directory

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------------------------
# A chave NÃO fica mais escrita no código (isso era o problema de segurança).
# Ela vem de uma variável de ambiente chamada BRAWL_API_KEY, configurada no
# painel do Render. Veja o README.md para o passo a passo.
API_KEY = os.environ.get("BRAWL_API_KEY", "")
PROXY_BASE = "https://bsproxy.royaleapi.dev/v1"
BRAWLIFY_BASE = "https://api.brawlify.com/v1"

# serve os arquivos estáticos (index.html, manifest.json, ícones, etc.)
# direto da raiz do projeto, do mesmo jeito que a Netlify fazia.
app = Flask(__name__, static_folder=".", static_url_path="")

# Ciclo completo de rotação do Solo Showdown (14 mapas)
ROTATION_CYCLE = [
    {"mapName": "Crystal Eye Castle", "mapId": 15001013},
    {"mapName": "Acid Lakes", "mapId": 15000015},
    {"mapName": "Gated Community", "mapId": 15000046},
    {"mapName": "Cavern Churn", "mapId": 15000006},
    {"mapName": "Lotus", "mapId": 15000024},
    {"mapName": "Kroket", "mapId": 15000097},
    {"mapName": "Feast or Famine", "mapId": 15000007},
    {"mapName": "Flying Fantasies", "mapId": 15000016},
    {"mapName": "Lilypond Grove", "mapId": 15001088},
    {"mapName": "North Park Station", "mapId": 15000067},
    {"mapName": "Twisting Vines", "mapId": 15001064},
    {"mapName": "Safety Center", "mapId": 15000850},
    {"mapName": "Skull Creek", "mapId": 15000005},
    {"mapName": "Makeshift Scaffolding", "mapId": 15001141},
]


def predict_next(current_map_name):
    name = (current_map_name or "").lower().replace("-", " ").strip()
    for i, m in enumerate(ROTATION_CYCLE):
        if m["mapName"].lower() == name:
            return ROTATION_CYCLE[(i + 1) % len(ROTATION_CYCLE)]
    return None


def clean_tag(tag):
    return tag if tag.startswith("#") else "#" + tag


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/.netlify/functions/player")
def player_function():
    """Recria a função que antes rodava na Netlify, no mesmo endereço,
    pra não precisar mudar nada no index.html."""
    if not API_KEY:
        return jsonify({"error": "Chave da API não configurada no servidor."}), 500

    headers = {"Authorization": f"Bearer {API_KEY}"}
    ptype = request.args.get("type")

    # ---- EVENTOS ----
    if ptype == "events":
        try:
            r = requests.get(f"{PROXY_BASE}/events/rotation", headers=headers, timeout=10)
        except requests.RequestException as e:
            return jsonify({"error": str(e)}), 500
        if not r.ok:
            return jsonify({"error": r.text}), r.status_code

        raw = r.json()
        todos = raw if isinstance(raw, list) else (raw.get("items") or raw.get("active") or [])

        def get_mode(ev):
            if ev.get("event"):
                return ev["event"].get("mode", "")
            m = ev.get("mode")
            return m.get("name", "") if isinstance(m, dict) else str(m or "")

        def get_map(ev):
            if ev.get("event"):
                return ev["event"].get("map", "")
            m = ev.get("map")
            return m.get("name", "") if isinstance(m, dict) else ""

        solo = [ev for ev in todos if "SOLO" in get_mode(ev).upper() or get_mode(ev) == "soloShowdown"]
        current_map = get_map(solo[0]) if solo else ""
        next_map = predict_next(current_map)

        return jsonify({
            "active": todos,
            "nextSoloShowdown": next_map,
            "rotationSize": len(ROTATION_CYCLE),
        })

    # ---- BATTLELOG ----
    if ptype == "battlelog":
        btag = request.args.get("tag")
        if not btag:
            return jsonify({"error": "TAG obrigatorio"}), 400
        encoded = quote(clean_tag(btag))
        try:
            r = requests.get(f"{PROXY_BASE}/players/{encoded}/battlelog", headers=headers, timeout=10)
        except requests.RequestException as e:
            return jsonify({"error": str(e)}), 500
        data = r.json()
        if not r.ok:
            return jsonify({"error": data.get("message", "Erro da API")}), r.status_code
        return jsonify(data)

    # ---- JOGADOR ----
    tag = request.args.get("tag")
    if not tag:
        return jsonify({"error": "TAG obrigatória"}), 400

    encoded = quote(clean_tag(tag))
    try:
        r = requests.get(f"{PROXY_BASE}/players/{encoded}", headers=headers, timeout=10)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

    data = r.json()
    if not r.ok:
        return jsonify({"error": data.get("message", "Erro da API")}), r.status_code

    icon_id = (data.get("icon") or {}).get("id")

    # horas jogadas, quando a Brawlify tiver esse dado
    horas = 0
    try:
        bf = requests.get(f"{BRAWLIFY_BASE}/players/{encoded}", timeout=8)
        if bf.ok:
            bfd = bf.json()
            horas = bfd.get("hoursPlayed") or (bfd.get("player") or {}).get("hoursPlayed") or 0
    except requests.RequestException:
        pass
    if not horas and data.get("expPoints"):
        horas = data["expPoints"] // 220

    # mapa de imagens dos brawlers, pela Brawlify
    brawler_img_map = {}
    try:
        bw = requests.get(f"{BRAWLIFY_BASE}/brawlers", timeout=8)
        if bw.ok:
            for b in bw.json().get("list", []):
                if b.get("id") and b.get("imageUrl"):
                    brawler_img_map[b["id"]] = b["imageUrl"]
    except requests.RequestException:
        pass

    brawlers = [{
        "id": b.get("id"),
        "name": b.get("name"),
        "power": b.get("power"),
        "rank": b.get("rank"),
        "trophies": b.get("trophies"),
        "highestTrophies": b.get("highestTrophies"),
        "imageUrl": brawler_img_map.get(b.get("id"), ""),
    } for b in data.get("brawlers", [])]

    return jsonify({
        "trophies": data.get("trophies"),
        "highestTrophies": data.get("highestTrophies"),
        "name": data.get("name"),
        "tag": data.get("tag"),
        "expLevel": data.get("expLevel"),
        "expPoints": data.get("expPoints", 0),
        "horas": horas,
        "brawlerCount": len(brawlers),
        "iconId": icon_id,
        "soloVictories": data.get("soloVictories"),
        "duoVictories": data.get("duoVictories"),
        "3vs3Victories": data.get("3vs3Victories"),
        "club": {"name": data["club"]["name"]} if data.get("club") else None,
        "brawlers": brawlers,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
