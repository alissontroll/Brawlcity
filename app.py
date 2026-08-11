import os
import time
import json
import datetime
import threading
from urllib.parse import quote

import requests
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, request, send_from_directory
from pywebpush import webpush, WebPushException

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------------------------
# A chave NÃO fica mais escrita no código (isso era o problema de segurança).
# Ela vem de uma variável de ambiente chamada BRAWL_API_KEY, configurada no
# painel do Render. Veja o README.md para o passo a passo.
API_KEY = os.environ.get("BRAWL_API_KEY", "")
PROXY_BASE = "https://bsproxy.royaleapi.dev/v1"
BRAWLIFY_BASE = "https://api.brawlify.com/v1"

# Chave do assistente de IA (Groq) — vem de variável de ambiente, nunca
# escrita no código, veja o README.md pra configurar no Render.
# Chave do assistente de IA (Groq) — vem de variável de ambiente, nunca
# escrita no código, veja o README.md pra configurar no Render.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Notificações push (Web Push) — as chaves vêm de variável de ambiente,
# veja o README.md pra saber como gerar/configurar as suas.
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS_EMAIL = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:contato@brawlcity.onrender.com")

# serve os arquivos estáticos (index.html, manifest.json, ícones, etc.)
# direto da raiz do projeto, do mesmo jeito que a Netlify fazia.
app = Flask(__name__, static_folder=".", static_url_path="")

# -----------------------------------------------------------------------------
# FIREBASE ADMIN — pra deixar o servidor atualizar o ranking sozinho
# -----------------------------------------------------------------------------
# O arquivo da chave de administrador NUNCA vai pro GitHub. Ele é enviado
# pro Render como "Secret File" e fica disponível nesse caminho fixo.
FIREBASE_CRED_PATH = "/etc/secrets/firebase-service-account.json"

db = None
try:
    if os.path.exists(FIREBASE_CRED_PATH):
        cred = credentials.Certificate(FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[FIREBASE] Conectado com sucesso ao Firestore.")
    else:
        print(f"[FIREBASE] Arquivo secreto não encontrado em {FIREBASE_CRED_PATH}. "
              f"A atualização automática do ranking vai ficar desativada.")
except Exception as e:
    print("[FIREBASE] Erro ao iniciar o Firebase Admin:", repr(e))

_refresh_lock = threading.Lock()

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


def fetch_player_full(tag):
    """Busca todos os dados de um jogador (usado tanto pela rota da API
    quanto pela atualização automática do ranking)."""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    encoded = quote(clean_tag(tag))

    r = requests.get(f"{PROXY_BASE}/players/{encoded}", headers=headers, timeout=10)
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(f"Resposta inválida do servidor do jogo (código {r.status_code}).")
    if not r.ok:
        raise RuntimeError(data.get("message", "Erro da API"))

    icon_id = (data.get("icon") or {}).get("id")

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

    return {
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
    }


def refresh_all_players():
    """Passa por todo mundo cadastrado no ranking e atualiza os dados
    direto no Firestore — é a versão do servidor da antiga atualizarDados()
    que rodava só no navegador de quem tivesse o site aberto."""
    if not db:
        print("[REFRESH] Abortado: Firebase Admin não está configurado.")
        return {"error": "Firebase Admin não configurado"}

    players_ref = db.collection("players")
    docs = list(players_ref.stream())
    print(f"[REFRESH] Começando. {len(docs)} jogador(es) encontrados no Firestore.")
    updated = 0
    instantaneo = []

    # domingo mais recente (se hoje for domingo, é hoje mesmo) — usamos essa
    # data como "identificador da semana atual" pra saber se já resetou ou não
    hoje = datetime.date.today()
    dias_desde_domingo = (hoje.weekday() + 1) % 7  # weekday(): Seg=0..Dom=6 → queremos Dom=0
    semana_atual_str = (hoje - datetime.timedelta(days=dias_desde_domingo)).isoformat()

    for doc in docs:
        player = doc.to_dict()
        tag = player.get("tag")
        if not tag:
            print(f"[REFRESH] Documento {doc.id} não tem campo 'tag', pulando.")
            continue
        try:
            data = fetch_player_full(tag)
        except Exception as e:
            print(f"[REFRESH] Erro ao buscar {tag}: {repr(e)}")
            continue

        updates = {}

        # ---- ranking semanal: define a base na primeira vez, e reseta toda semana nova ----
        if data.get("trophies"):
            if player.get("semanaBase") is None or player.get("semanaResetWeek") != semana_atual_str:
                updates["semanaBase"] = data["trophies"]
                updates["semanaResetWeek"] = semana_atual_str
                updates["semanaInicio"] = int(time.time() * 1000)

        if data.get("trophies") and data["trophies"] != player.get("trophies"):
            updates["trophies"] = data["trophies"]
        if data.get("horas") and data["horas"] != player.get("horas"):
            updates["horas"] = data["horas"]
        if data.get("iconId") and data["iconId"] != player.get("iconId"):
            updates["iconId"] = data["iconId"]

        brawlers = data.get("brawlers") or []
        if brawlers:
            top_b = max(brawlers, key=lambda b: b.get("trophies") or 0)
            if top_b.get("imageUrl") and top_b["imageUrl"] != player.get("topBrawlerImg"):
                updates["topBrawlerImg"] = top_b["imageUrl"]

        # ---- brawler novo desbloqueado ----
        new_count = data.get("brawlerCount")
        old_count = player.get("brawlerCount")
        if new_count and old_count and new_count > old_count:
            diff = new_count - old_count
            updates["brawlerCount"] = new_count
            updates["newBrawlers"] = diff
            try:
                db.collection("notifications").add({
                    "playerName": player.get("name"),
                    "count": diff,
                    "timestamp": int(time.time() * 1000),
                    "type": "newBrawler",
                })
            except Exception as e:
                print(f"[REFRESH] Erro ao notificar brawler novo de {tag}: {repr(e)}")
        elif new_count and not old_count:
            updates["brawlerCount"] = new_count

        # ---- brawlers que chegaram aos 1000 troféus ----
        mil_atuais = sorted({(b.get("name") or "").upper() for b in brawlers if (b.get("trophies") or 0) >= 1000})
        mil_salvos = sorted(player.get("brawlers1000") or [])
        if mil_atuais != mil_salvos:
            if mil_salvos:  # só notifica se já tinha uma lista salva antes (evita spam no primeiro cálculo)
                novos_1000 = [n for n in mil_atuais if n not in mil_salvos]
                for nome in novos_1000:
                    b = next((x for x in brawlers if (x.get("name") or "").upper() == nome), None)
                    try:
                        db.collection("notifications").add({
                            "playerName": player.get("name"),
                            "playerEmoji": player.get("emoji") or "🎮",
                            "playerIconId": player.get("iconId"),
                            "brawlerNome": nome,
                            "brawlerImg": (b or {}).get("imageUrl", ""),
                            "trophies": (b or {}).get("trophies", 1000),
                            "timestamp": int(time.time() * 1000),
                            "type": "brawler1000",
                        })
                    except Exception as e:
                        print(f"[REFRESH] Erro ao notificar 1000 troféus de {tag}: {repr(e)}")
            updates["brawlers1000"] = mil_atuais

        # ---- brawlers maximizados (power 11) ----
        max_atuais = sorted({(b.get("name") or "").upper() for b in brawlers if (b.get("power") or 0) >= 11})
        max_salvos = sorted(player.get("brawlersMax") or [])
        if max_atuais != max_salvos:
            if max_salvos:
                novos_max = [n for n in max_atuais if n not in max_salvos]
                for nome in novos_max:
                    b = next((x for x in brawlers if (x.get("name") or "").upper() == nome), None)
                    try:
                        db.collection("notifications").add({
                            "playerName": player.get("name"),
                            "playerEmoji": player.get("emoji") or "🎮",
                            "playerIconId": player.get("iconId"),
                            "brawlerNome": nome,
                            "brawlerImg": (b or {}).get("imageUrl", ""),
                            "timestamp": int(time.time() * 1000),
                            "type": "brawlerMax",
                        })
                    except Exception as e:
                        print(f"[REFRESH] Erro ao notificar maximização de {tag}: {repr(e)}")
            updates["brawlersMax"] = max_atuais

        if updates:
            try:
                doc.reference.update(updates)
                updated += 1
                print(f"[REFRESH] {tag} atualizado: {updates}")
            except Exception as e:
                print(f"[REFRESH] Erro ao SALVAR {tag} no Firestore: {repr(e)}")

        instantaneo.append({
            "doc_id": doc.id,
            "tag": tag,
            "name": player.get("name") or data.get("name") or tag,
            "city": player.get("city") or "",
            "trophies": data.get("trophies") if data.get("trophies") is not None else player.get("trophies", 0),
            "lastRankPos": player.get("lastRankPos"),
        })

        if data.get("trophies"):
            try:
                hoje_str = datetime.date.today().isoformat()
                history_ref = doc.reference.collection("history")
                # procura se já existe um registro de hoje, pra atualizar em vez de duplicar
                existentes_hoje = list(history_ref.where("dateStr", "==", hoje_str).limit(1).stream())
                if existentes_hoje:
                    existentes_hoje[0].reference.update({
                        "trophies": data["trophies"],
                        "timestamp": int(time.time() * 1000),
                    })
                else:
                    history_ref.add({
                        "trophies": data["trophies"],
                        "timestamp": int(time.time() * 1000),
                        "dateStr": hoje_str,
                    })
            except Exception as e:
                print(f"[REFRESH] Erro ao salvar histórico de {tag}: {repr(e)}")

    # ---- checa quem foi ultrapassado no ranking da própria cidade e avisa ----
    try:
        subs_docs = list(db.collection("pushSubscriptions").stream())
        subs_map = {d.id: d.to_dict().get("subscription") for d in subs_docs}
    except Exception as e:
        print(f"[PUSH] Erro ao buscar inscrições: {repr(e)}")
        subs_map = {}

    cidades = {}
    for p in instantaneo:
        cidades.setdefault(p["city"], []).append(p)

    for cidade, jogadores in cidades.items():
        jogadores.sort(key=lambda p: -(p["trophies"] or 0))
        for i, p in enumerate(jogadores):
            pos_atual = i + 1
            pos_antiga = p["lastRankPos"]
            try:
                players_ref.document(p["doc_id"]).update({"lastRankPos": pos_atual})
            except Exception as e:
                print(f"[REFRESH] Erro ao salvar lastRankPos de {p['tag']}: {repr(e)}")

            if pos_antiga is not None and pos_atual > pos_antiga:
                sub = subs_map.get(p["tag"])
                if sub:
                    quem_passou = jogadores[pos_atual - 2]["name"] if pos_atual >= 2 else "alguém"
                    ok, motivo = send_push(
                        sub,
                        title="📉 Você foi ultrapassado!",
                        body=f"{quem_passou} passou você no ranking de {cidade}. Bora reagir! 🏆",
                        url="/",
                    )
                    if not ok and motivo == "expirada":
                        try:
                            db.collection("pushSubscriptions").document(p["tag"]).delete()
                        except Exception:
                            pass

    print(f"[REFRESH] Concluído. {updated} de {len(docs)} jogador(es) atualizados.")
    return {"updated": updated, "total": len(docs)}


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/refresh-all")
def refresh_all_route():
    """Chamada pelo index.html quando alguém abre o ranking. Roda em
    segundo plano pra não travar a resposta esperando todo mundo atualizar."""
    if _refresh_lock.locked():
        print("[REFRESH] Chamada ignorada: já tem uma atualização rodando.")
        return jsonify({"status": "already_running"})

    print("[REFRESH] Disparado por uma visita ao site.")

    def run():
        with _refresh_lock:
            refresh_all_players()

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"status": "started"})


def send_push(subscription_info, title, body, url="/"):
    """Manda uma notificação push pra um único inscrito. Se der erro de
    'inscrição não existe mais' (410/404), avisa o chamador pra poder apagar."""
    if not VAPID_PRIVATE_KEY:
        return False, "sem_chave"
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
        )
        return True, None
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            return False, "expirada"
        print(f"[PUSH] Erro ao enviar: {repr(e)}")
        return False, "erro"


@app.route("/api/push/vapid-public-key")
def push_vapid_public_key():
    return jsonify({"key": VAPID_PUBLIC_KEY})


@app.route("/api/push/subscribe", methods=["POST"])
def push_subscribe():
    if not db:
        return jsonify({"error": "Firebase Admin não configurado"}), 500
    body = request.get_json(force=True, silent=True) or {}
    tag = (body.get("tag") or "").replace("#", "").upper()
    subscription = body.get("subscription")
    if not tag or not subscription:
        return jsonify({"error": "Faltou tag ou subscription"}), 400
    try:
        db.collection("pushSubscriptions").document(tag).set({
            "tag": tag,
            "subscription": subscription,
            "updatedAt": int(time.time() * 1000),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"})


@app.route("/api/push/unsubscribe", methods=["POST"])
def push_unsubscribe():
    if not db:
        return jsonify({"error": "Firebase Admin não configurado"}), 500
    body = request.get_json(force=True, silent=True) or {}
    tag = (body.get("tag") or "").replace("#", "").upper()
    if not tag:
        return jsonify({"error": "Faltou tag"}), 400
    try:
        db.collection("pushSubscriptions").document(tag).delete()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"})


@app.route("/api/ai-chat", methods=["POST"])
def ai_chat():
    """Ponte protegida pro assistente de IA. A chave da Groq fica só
    aqui no servidor, nunca aparece no código do site."""
    if not GROQ_API_KEY:
        return jsonify({"error": "Chave da Groq não configurada no servidor."}), 500

    body = request.get_json(force=True, silent=True) or {}
    messages = body.get("messages")
    if not messages:
        return jsonify({"error": "Nenhuma mensagem enviada."}), 400

    try:
        r = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": body.get("max_tokens", 600),
                "temperature": body.get("temperature", 0.9),
            },
            timeout=30,
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

    if not r.ok:
        return jsonify({
            "error": f"Groq respondeu {r.status_code}: {r.text[:300]}"
        }), r.status_code

    try:
        data = r.json()
    except ValueError:
        return jsonify({"error": f"Resposta não era JSON: {r.text[:300]}"}), 502

    content = ""
    choices = data.get("choices") or []
    if choices:
        content = (choices[0].get("message") or {}).get("content", "")

    return jsonify({"content": content})


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
            return jsonify({"error": r.text[:300]}), r.status_code

        try:
            raw = r.json()
        except ValueError:
            return jsonify({"error": "O servidor do jogo mandou uma resposta inesperada. Tenta de novo."}), 502

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
        try:
            data = r.json()
        except ValueError:
            return jsonify({"error": "O servidor do jogo mandou uma resposta inesperada. Tenta de novo."}), 502
        if not r.ok:
            return jsonify({"error": data.get("message", "Erro da API")}), r.status_code
        return jsonify(data)

    # ---- JOGADOR ----
    tag = request.args.get("tag")
    if not tag:
        return jsonify({"error": "TAG obrigatória"}), 400

    try:
        result = fetch_player_full(tag)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
