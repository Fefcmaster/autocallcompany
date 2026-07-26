from flask import Flask, render_template_string, jsonify, request, send_from_directory, session, redirect, url_for
import pandas as pd
import threading
import time
import webbrowser
import os
import sqlite3
import hashlib
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "chave_secreta_super_segura_company777"

PASTA_UPLOADS = "uploads_usuarios"
PASTA_AUDIOS = "audios_upload"
ARQUIVO_PROGRESSO = "progresso.json"

for pasta in [PASTA_UPLOADS, PASTA_AUDIOS]:
    if not os.path.exists(pasta):
        os.makedirs(pasta)

DB_NAME = "banco_saas.db"

# Dicionário em memória para rastrear o status em tempo real de cada usuário logado
status_por_usuario = {}

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            provedor TEXT,
            servidor TEXT,
            sip_usuario TEXT,
            sip_senha TEXT,
            is_admin INTEGER DEFAULT 0,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    # Criação do Admin Master Company
    cursor.execute("SELECT * FROM usuarios WHERE username = 'Company'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO usuarios (username, senha, is_admin, ativo) VALUES (?, ?, ?, 1)", 
            ("Company", hash_senha("company@@@"), 1)
        )
        conn.commit()
    conn.close()

init_db()

def carregar_progresso(user_id):
    prog_file = os.path.join(PASTA_UPLOADS, f"user_{user_id}_progresso.json")
    if os.path.exists(prog_file):
        try:
            with open(prog_file, "r", encoding="utf-8") as f:
                return json.load(f).get("indice", 0)
        except:
            pass
    return 0

def salvar_progresso(user_id, indice):
    prog_file = os.path.join(PASTA_UPLOADS, f"user_{user_id}_progresso.json")
    try:
        with open(prog_file, "w", encoding="utf-8") as f:
            json.dump({"indice": indice}, f)
    except:
        pass

def carregar_clientes_usuario(user_id):
    caminho_planilha = os.path.join(PASTA_UPLOADS, f"user_{user_id}_planilha.xlsx")
    if not os.path.exists(caminho_planilha):
        return []
    try:
        df = pd.read_excel(caminho_planilha)
        clientes = []
        for index, row in df.iterrows():
            nome = str(row.get("nome", row.get("Nome", f"Cliente {index+1}")))
            cpf = str(row.get("cpf", row.get("CPF", "-")))
            agencia = str(row.get("agencia", row.get("Agencia", "-")))
            idade = str(row.get("idade", row.get("Idade", "-")))
            profissao = str(row.get("profissao", row.get("Profissao", "-")))
            renda = str(row.get("renda", row.get("Renda", "-")))
            protocolo = str(row.get("protocolo", row.get("Protocolo", "-")))
            cidade = str(row.get("cidade", row.get("Cidade", "-")))
            
            telefones = []
            for col in df.columns:
                if any(t_key in col.lower() for t_key in ["tel", "fone", "cel"]):
                    val = row.get(col)
                    if pd.notna(val):
                        tel_limpo = ''.join(filter(str.isdigit, str(val)))
                        if len(tel_limpo) >= 8:
                            if not tel_limpo.startswith("55") and len(tel_limpo) in [10, 11]:
                                tel_limpo = "55" + tel_limpo
                            if tel_limpo not in telefones:
                                telefones.append(tel_limpo)

            if not telefones:
                telefones = ["5511999999999"]

            clientes.append({
                "id": index + 1,
                "nome": nome, "cpf": cpf, "agencia": agencia,
                "idade": idade, "profissao": profissao, "renda": renda,
                "protocolo": protocolo, "cidade": cidade, "telefones": telefones
            })
        return clientes
    except Exception as e:
        return []

def executar_disparos_background(user_id, username):
    global status_por_usuario
    clientes = carregar_clientes_usuario(user_id)
    if not clientes:
        if user_id in status_por_usuario:
            status_por_usuario[user_id]["status"] = "Erro: Planilha vazia"
        return

    if user_id not in status_por_usuario:
        status_por_usuario[user_id] = {}

    status_por_usuario[user_id]["status"] = "Rodando"
    total = len(clientes)
    indice_inicial = carregar_progresso(user_id)
    if indice_inicial >= total:
        indice_inicial = 0

    for i in range(indice_inicial, total):
        if status_por_usuario.get(user_id, {}).get("status") == "Parado":
            break
            
        cliente = clientes[i]
        for idx_tel, numero in enumerate(cliente["telefones"]):
            if status_por_usuario.get(user_id, {}).get("status") == "Parado":
                break
                
            status_por_usuario[user_id]["progresso"] = f"Lead [{i+1}/{total}] (Tel {idx_tel+1})"
            status_por_usuario[user_id]["indice_atual"] = i + 1
            status_por_usuario[user_id]["total_leads"] = total
            status_por_usuario[user_id]["cliente_atual"] = {
                "nome": cliente["nome"], "telefone": numero, "cidade": cliente["cidade"]
            }
            
            try:
                webbrowser.open(f"sip:{numero}")
            except:
                pass
            
            inicio = time.time()
            while time.time() - inicio < 15:
                if status_por_usuario.get(user_id, {}).get("status") == "Parado":
                    break
                time.sleep(0.5)
            time.sleep(1)

        if status_por_usuario.get(user_id, {}).get("status") == "Parado":
            break
        salvar_progresso(user_id, i + 1)

    if user_id in status_por_usuario:
        status_por_usuario[user_id]["status"] = "Parado"
        status_por_usuario[user_id]["progresso"] = "Lote concluído!"
    salvar_progresso(user_id, 0)

HTML_LOGIN = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Login - Company777 SaaS</title>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: #161b22; border: 1px solid #30363d; padding: 30px; border-radius: 10px; width: 320px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); text-align: center; }
        h2 { color: #58a6ff; margin-bottom: 10px; }
        p { color: #8b949e; font-size: 12px; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; text-align: left; }
        .form-group label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 5px; font-weight: bold; }
        .form-group input { width: 100%; padding: 10px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; box-sizing: border-box; }
        .btn { background: #238636; color: white; border: none; padding: 10px; width: 100%; font-size: 15px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .btn:hover { background: #2ea043; }
        .error { color: #da3633; font-size: 13px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>Company777 SaaS</h2>
        <p>Acesse com sua conta</p>
        <form method="POST">
            <div class="form-group"><label>Usuário</label><input type="text" name="username" required></div>
            <div class="form-group"><label>Senha</label><input type="password" name="senha" required></div>
            <button type="submit" class="btn">Entrar</button>
            {% if erro %}<div class="error">{{ erro }}</div>{% endif %}
        </form>
    </div>
</body>
</html>
"""

HTML_ADMIN = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Supervisão Master (Admin) - Company777</title>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 30px; }
        .container { max-width: 1100px; margin: auto; }
        .header { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        h2 { color: #58a6ff; margin: 0; }
        .btn-danger { background: #da3633; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
        .card h3 { color: #58a6ff; margin-top: 0; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
        .form-group { margin-bottom: 12px; display: inline-block; margin-right: 10px; width: 42%; }
        .form-group label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 4px; font-weight: bold; }
        .form-group input { width: 100%; padding: 8px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; box-sizing: border-box; }
        .btn { background: #238636; color: white; border: none; padding: 9px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .btn:hover { background: #2ea043; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #30363d; padding: 12px 10px; text-align: left; font-size: 13px; }
        th { background: #21262d; color: #58a6ff; }
        .status-dot { height: 10px; width: 10px; background-color: #da3633; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .status-dot.online { background-color: #3fb950; box-shadow: 0 0 8px #3fb950; }
        .badge-status { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; background: #21262d; border: 1px solid #30363d; }
        .btn-acao { padding: 4px 10px; font-size: 11px; border-radius: 4px; border: none; color: white; cursor: pointer; font-weight: bold; margin-right: 4px; text-decoration: none; display: inline-block;}
        .btn-block { background: #9e6a03; }
        .btn-unblock { background: #238636; }
        .btn-del { background: #da3633; }
        .msg { color: #3fb950; font-size: 13px; margin-top: 8px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Painel Master: Central de Supervisão em Tempo Real</h2>
            <a href="/logout" class="btn-danger">Sair do Master</a>
        </div>

        <div class="card">
            <h3>Criar Novo Login para Cliente</h3>
            <form action="/admin/criar_cliente" method="POST">
                <div class="form-group"><label>Usuário do Cliente</label><input type="text" name="novo_user" required></div>
                <div class="form-group"><label>Senha Inicial</label><input type="password" name="nova_senha" required></div>
                <button type="submit" class="btn" style="vertical-align: bottom;">Criar Acesso</button>
            </form>
            {% if msg %}<div class="msg">{{ msg }}</div>{% endif %}
        </div>

        <div class="card">
            <h3>Monitória e Controle de Clientes</h3>
            <table>
                <tr>
                    <th>Status Online</th>
                    <th>Cliente</th>
                    <th>Estado da Automação</th>
                    <th>Lead em Atendimento Agora</th>
                    <th>Progresso da Planilha</th>
                    <th>Ações Administrativas</th>
                </tr>
                <tbody id="tabela-monit">
                    <tr><td colspan="6" style="text-align:center; color:#8b949e;">Carregando dados ao vivo...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function atualizarSupervisao() {
            fetch('/admin/dados_supervisao')
                .then(res => res.status === 401 ? window.location.href = '/' : res.json())
                .then(data => {
                    let html = "";
                    data.forEach(cli => {
                        let dotClass = cli.online ? "status-dot online" : "status-dot";
                        let onlineText = cli.online ? "Online agora" : "Offline";
                        let statusRobo = cli.status_robo || "Parado";
                        let leadAtual = cli.lead_nome !== "-" ? `<b>${cli.lead_nome}</b> (${cli.lead_tel})` : "-";
                        let progresso = cli.total_leads > 0 ? `${cli.indice} / ${cli.total_leads}` : "Sem planilha";
                        
                        let blockBtn = cli.ativo === 1 
                            ? `<form action="/admin/bloquear/${cli.id}" method="POST" style="display:inline;"><button class="btn-acao btn-block">Bloquear</button></form>`
                            : `<form action="/admin/bloquear/${cli.id}" method="POST" style="display:inline;"><button class="btn-acao btn-unblock">Ativar</button></form>`;
                        
                        let delBtn = cli.username !== 'Company' 
                            ? `<form action="/admin/deletar_cliente/${cli.id}" method="POST" style="display:inline;"><button class="btn-acao btn-del" onclick="return confirm('Excluir cliente?')">Excluir</button></form>`
                            : `<span style="color:#8b949e; font-size:11px;">Master</span>`;

                        let acoes = cli.username !== 'Company' ? `${blockBtn} ${delBtn}` : "-";

                        html += `<tr>
                            <td><span class="${dotClass}"></span> ${onlineText}</td>
                            <td><b>${cli.username}</b></td>
                            <td><span class="badge-status">${statusRobo}</span></td>
                            <td>${leadAtual}</td>
                            <td>${progresso}</td>
                            <td>${acoes}</td>
                        </tr>`;
                    });
                    document.getElementById('tabela-monit').innerHTML = html;
                });
        }
        setInterval(atualizarSupervisao, 2000);
        atualizarSupervisao();
    </script>
</body>
</html>
"""

HTML_PAINEL = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Painel SaaS - Company777</title>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 1100px; margin: auto; }
        .header { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        h2 { color: #58a6ff; margin: 0; }
        .btn-danger { background: #da3633; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 14px; display: inline-block; }
        .config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; text-align: left; }
        .card h3 { color: #58a6ff; margin-top: 0; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 4px; font-weight: bold; }
        .form-group input { width: 100%; padding: 8px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; box-sizing: border-box; }
        .btn { background: #238636; color: white; border: none; padding: 10px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; margin-top: 5px; }
        .btn:hover { background: #2ea043; }
        .control-panel { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 20px; text-align: center; }
        .status-box { font-size: 16px; margin: 10px 0; font-weight: bold; color: #f0883e; }
        .grid-atendimento { display: grid; grid-template-columns: 1.2fr 1fr; gap: 20px; margin-bottom: 20px; }
        .client-info p { font-size: 14px; margin: 8px 0; }
        .client-info b { color: #58a6ff; }
        .highlight-val { color: #3fb950; font-weight: bold; }
        .btn-copy { background: #1f6feb; padding: 3px 8px; font-size: 11px; border-radius: 4px; border: none; color: white; cursor: pointer; font-weight: bold; margin-left: 5px; }
        .audio-section { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-top: 20px; }
        .audio-item { display: flex; justify-content: space-between; align-items: center; background: #0d1117; padding: 8px; border-radius: 6px; margin-bottom: 6px; border: 1px solid #30363d; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Painel do Cliente: {{ usuario }}</h2>
            <a href="/logout" class="btn-danger">Sair do Sistema</a>
        </div>

        <div class="control-panel">
            <h3>Automação e Discagem Inteligente</h3>
            <p class="status-box">Status: <span id="status">Parado</span> | Progresso: <span id="progresso">-</span></p>
            <button class="btn" style="width: auto; background:#238636; display:inline-block; padding: 10px 20px;" onclick="iniciarRobo()">INICIAR / RETOMAR DISPAROS</button>
            <button class="btn" style="width: auto; background:#da3633; display:inline-block; padding: 10px 20px;" onclick="pararRobo()">PAUSAR / PARAR</button>
            <button class="btn" style="width: auto; background:#9e6a03; display:inline-block; padding: 10px 20px;" onclick="resetarProgresso()">Zerar Fila</button>
        </div>

        <div class="grid-atendimento">
            <div class="card" style="border: 2px solid #58a6ff;">
                <h3>Cliente em Atendimento / Discagem</h3>
                <div class="client-info">
                    <p><b>Nome:</b> <span id="c-nome" class="highlight-val">-</span> <button class="btn-copy" onclick="copiarTexto('c-nome')">Copiar</button></p>
                    <p><b>Telefone:</b> <span id="c-tel" class="highlight-val">-</span> <button class="btn-copy" onclick="copiarTexto('c-tel')">Copiar</button></p>
                    <p><b>CPF:</b> <span id="c-cpf">-</span> <button class="btn-copy" onclick="copiarTexto('c-cpf')">Copiar</button></p>
                    <p><b>Agência:</b> <span id="c-agencia">-</span> <button class="btn-copy" onclick="copiarTexto('c-agencia')">Copiar</button></p>
                    <p><b>Idade:</b> <span id="c-idade">-</span> <button class="btn-copy" onclick="copiarTexto('c-idade')">Copiar</button></p>
                    <p><b>Profissão:</b> <span id="c-profissao">-</span> <button class="btn-copy" onclick="copiarTexto('c-profissao')">Copiar</button></p>
                    <p><b>Renda:</b> R$ <span id="c-renda">-</span> <button class="btn-copy" onclick="copiarTexto('c-renda')">Copiar</button></p>
                    <p><b>Protocolo:</b> <span id="c-protocolo">-</span> <button class="btn-copy" onclick="copiarTexto('c-protocolo')">Copiar</button></p>
                    <p><b>Cidade:</b> <span id="c-cidade">-</span> <button class="btn-copy" onclick="copiarTexto('c-cidade')">Copiar</button></p>
                </div>
            </div>
            <div class="card">
                <h3>Fila de Leads Carregados</h3>
                <div style="max-height: 330px; overflow-y: auto;">
                    <ul id="lista-clientes" style="padding-left: 15px; font-size: 13px; margin: 0;">Carregando...</ul>
                </div>
            </div>
        </div>

        <div class="config-grid">
            <div class="card">
                <h3>Configuração SIP (Operadora)</h3>
                <form action="/salvar_sip" method="POST">
                    <div class="form-group"><label>Provedor</label><input type="text" name="provedor" value="{{ config.provedor }}"></div>
                    <div class="form-group"><label>Servidor / Proxy SIP</label><input type="text" name="servidor" value="{{ config.servidor }}"></div>
                    <div class="form-group"><label>Usuário / Ramal</label><input type="text" name="sip_usuario" value="{{ config.sip_usuario }}"></div>
                    <div class="form-group"><label>Senha SIP</label><input type="password" name="sip_senha" value="{{ config.sip_senha }}"></div>
                    <button type="submit" class="btn" style="background:#1f6feb;">Salvar SIP</button>
                </form>
            </div>

            <div class="card">
                <h3>Enviar Planilha de Leads (XLSX)</h3>
                <form action="/upload_planilha" method="POST" enctype="multipart/form-data">
                    <div class="form-group" style="margin-top: 15px;">
                        <label>Arquivo Excel (.xlsx)</label>
                        <input type="file" name="planilha" accept=".xlsx" style="color: #c9d1d9; padding: 10px 0;" required>
                    </div>
                    <button type="submit" class="btn" style="margin-top: 28px;">Carregar Planilha</button>
                </form>
            </div>
        </div>

        <div class="audio-section">
            <h3>Gerenciador de Áudios / Música de Fundo</h3>
            <div style="margin-bottom: 15px;">
                <input type="file" id="arquivoAudio" accept="audio/*" style="color: #c9d1d9;">
                <button class="btn" style="width: auto; padding: 6px 15px; background: #238636;" onclick="enviarAudio()">Carregar Áudio</button>
            </div>
            <ul style="list-style: none; padding: 0;" id="lista-audios"></ul>
        </div>
    </div>

    <script>
        let audioAtual = null;

        function atualizarDados() {
            fetch('/status')
                .then(res => res.status === 401 ? window.location.href = '/' : res.json())
                .then(data => {
                    if (!data) return;
                    document.getElementById('status').innerText = data.status;
                    document.getElementById('progresso').innerText = data.progresso;
                    
                    let cur = data.cliente_atual;
                    document.getElementById('c-nome').innerText = cur.nome;
                    document.getElementById('c-tel').innerText = cur.telefone;
                    document.getElementById('c-cpf').innerText = cur.cpf;
                    document.getElementById('c-agencia').innerText = cur.agencia;
                    document.getElementById('c-idade').innerText = cur.idade;
                    document.getElementById('c-profissao').innerText = cur.profissao;
                    document.getElementById('c-renda').innerText = cur.renda;
                    document.getElementById('c-protocolo').innerText = cur.protocolo;
                    document.getElementById('c-cidade').innerText = cur.cidade;
                    
                    let listaHtml = "";
                    data.clientes_lista.forEach((c, idx) => {
                        let st = (idx + 1 === data.indice_atual) ? "color: #3fb950; font-weight: bold;" : "";
                        listaHtml += `<li style="${st}"><b>${c.nome}</b> (${c.telefones.join(', ')})</li>`;
                    });
                    document.getElementById('lista-clientes').innerHTML = listaHtml;
                });
            carregarAudios();
        }

        function carregarAudios() {
            fetch('/audios').then(res => res.json()).then(data => {
                let html = "";
                if(data.length === 0) html = "<li style='color: #8b949e;'>Nenhum áudio.</li>";
                else data.forEach(nome => {
                    html += `<li class="audio-item"><span>🎵 ${nome}</span><div>
                        <button class="btn" style="width:auto; padding:3px 8px; background:#238636;" onclick="tocarAudio('${nome}')">Tocar</button>
                        <button class="btn" style="width:auto; padding:3px 8px; background:#9e6a03;" onclick="pausarAudio()">Pausar</button>
                        <button class="btn" style="width:auto; padding:3px 8px; background:#da3633;" onclick="apagarAudio('${nome}')">Apagar</button>
                    </div></li>`;
                });
                document.getElementById('lista-audios').innerHTML = html;
            });
        }

        function enviarAudio() {
            let input = document.getElementById('arquivoAudio');
            if(!input.files.length) return alert("Selecione um áudio!");
            let fd = new FormData(); fd.append("audio", input.files[0]);
            fetch('/upload_audio', {method:'POST', body:fd}).then(r=>r.json()).then(d=>{alert(d.mensagem); input.value=""; carregarAudios();});
        }
        function tocarAudio(n) { if(audioAtual) audioAtual.pause(); audioAtual = new Audio('/stream_audio/'+n); audioAtual.loop=true; audioAtual.play(); }
        function pausarAudio() { if(audioAtual) audioAtual.pause(); }
        function apagarAudio(n) { fetch('/apagar_audio/'+n, {method:'DELETE'}).then(r=>r.json()).then(d=>{alert(d.mensagem); carregarAudios();}); }
        function copiarTexto(id) { navigator.clipboard.writeText(document.getElementById(id).innerText).then(()=>alert("Copiado!")); }
        function iniciarRobo() { fetch('/iniciar', {method:'POST'}).then(r=>r.json()).then(d=>alert(d.mensagem)); }
        function pararRobo() { fetch('/parar', {method:'POST'}).then(r=>r.json()); }
        function resetarProgresso() { fetch('/resetar', {method:'POST'}).then(r=>r.json()).then(d=>alert(d.mensagem)); }

        setInterval(atualizarDados, 3000);
        atualizarDados();
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        username = request.form.get('username')
        senha = hash_senha(request.form.get('senha'))
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, is_admin, ativo FROM usuarios WHERE username = ? AND senha = ?", (username, senha))
        user = cursor.fetchone()
        conn.close()
        if user:
            if user[3] == 0:
                erro = "Sua conta está bloqueada! Entre em contato com o suporte."
            else:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['is_admin'] = user[2]
                
                # Atualiza último acesso
                status_por_usuario[user[0]] = {
                    "ultimo_ping": time.time(),
                    "status": "Parado",
                    "progresso": "Aguardando",
                    "indice_atual": 0,
                    "total_leads": len(carregar_clientes_usuario(user[0])),
                    "cliente_atual": {"nome": "-", "telefone": "-", "cidade": "-"}
                }

                if user[2] == 1:
                    return redirect(url_for('admin_painel'))
                else:
                    return redirect(url_for('painel'))
        else:
            erro = "Usuário ou senha incorretos!"
    return render_template_string(HTML_LOGIN, erro=erro)

@app.route('/admin')
def admin_painel():
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))
    return render_template_string(HTML_ADMIN, msg=None)

@app.route('/admin/dados_supervisao')
def admin_dados_supervisao():
    if 'user_id' not in session or session.get('is_admin') != 1:
        return jsonify({"erro": "Não autorizado"}), 401
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, is_admin, ativo FROM usuarios")
    usuarios_db = cursor.fetchall()
    conn.close()

    tempo_atual = time.time()
    dados_saida = []

    for u in usuarios_db:
        u_id, u_name, is_adm, ativo = u
        
        # Verifica se está online (fez requisição nos últimos 15 segundos)
        info_mem = status_por_usuario.get(u_id, {})
        ultimo_ping = info_mem.get("ultimo_ping", 0)
        online = (tempo_atual - ultimo_ping) < 15

        status_robo = info_mem.get("status", "Parado")
        indice = carregar_progresso(u_id)
        total_leads = len(carregar_clientes_usuario(u_id))
        cli_atual = info_mem.get("cliente_atual", {"nome": "-", "telefone": "-", "cidade": "-"})

        dados_saida.append({
            "id": u_id,
            "username": u_name,
            "is_admin": is_adm,
            "ativo": ativo,
            "online": online,
            "status_robo": status_robo,
            "indice": indice,
            "total_leads": total_leads,
            "lead_nome": cli_atual.get("nome", "-"),
            "lead_tel": cli_atual.get("telefone", "-")
        })

    return jsonify(dados_saida)

@app.route('/admin/criar_cliente', methods=['POST'])
def admin_criar_cliente():
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))
    
    novo_user = request.form.get('novo_user')
    nova_senha = hash_senha(request.form.get('nova_senha'))
    
    msg = ""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, senha, is_admin, ativo) VALUES (?, ?, 0, 1)", (novo_user, nova_senha))
        conn.commit()
        msg = f"Cliente '{novo_user}' criado com sucesso!"
    except:
        msg = "Erro: Nome de usuário já existe!"
    conn.close()
    return render_template_string(HTML_ADMIN, msg=msg)

@app.route('/admin/bloquear/<int:id_cliente>', methods=['POST'])
def admin_bloquear(id_cliente):
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT ativo FROM usuarios WHERE id = ?", (id_cliente,))
    res = cursor.fetchone()
    if res:
        novo_status = 0 if res[0] == 1 else 1
        cursor.execute("UPDATE usuarios SET ativo = ? WHERE id = ? AND username != 'Company'", (novo_status, id_cliente))
        conn.commit()
    conn.close()
    return redirect(url_for('admin_painel'))

@app.route('/admin/deletar_cliente/<int:id_cliente>', methods=['POST'])
def admin_deletar_cliente(id_cliente):
    if 'user_id' not in session or session.get('is_admin') != 1:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = ? AND is_admin = 0", (id_cliente,))
    conn.commit()
    conn.close()
    if id_cliente in status_por_usuario:
        del status_por_usuario[id_cliente]
    return redirect(url_for('admin_painel'))

@app.route('/painel')
def painel():
    if 'user_id' not in session or session.get('is_admin') == 1:
        return redirect(url_for('login'))
    
    # Atualiza o pings de atividade do usuário
    if session['user_id'] in status_por_usuario:
        status_por_usuario[session['user_id']]["ultimo_ping"] = time.time()
    else:
        status_por_usuario[session['user_id']] = {
            "ultimo_ping": time.time(), "status": "Parado", "progresso": "Aguardando", "indice_atual": 0, "cliente_atual": {"nome": "-", "telefone": "-"}
        }

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT provedor, servidor, sip_usuario, sip_senha FROM usuarios WHERE id = ?", (session['user_id'],))
    dados = cursor.fetchone()
    conn.close()
    config = {
        "provedor": dados[0] if dados else "",
        "servidor": dados[1] if dados else "",
        "sip_usuario": dados[2] if dados else "",
        "sip_senha": dados[3] if dados else ""
    }
    return render_template_string(HTML_PAINEL, usuario=session['username'], config=config)

@app.route('/status')
def status():
    if 'user_id' not in session: return jsonify({"erro": "Não autorizado"}), 401
    
    # Atualiza pings
    uid = session['user_id']
    if uid in status_por_usuario:
        status_por_usuario[uid]["ultimo_ping"] = time.time()
    
    clientes = carregar_clientes_usuario(uid)
    info_mem = status_por_usuario.get(uid, {})
    
    dados = {
        "status": info_mem.get("status", "Parado"),
        "progresso": info_mem.get("progresso", "Aguardando"),
        "cliente_atual": info_mem.get("cliente_atual", {"nome": "-", "telefone": "-", "cpf": "-", "agencia": "-", "idade": "-", "profissao": "-", "renda": "-", "protocolo": "-", "cidade": "-"}),
        "clientes_lista": clientes,
        "indice_atual": carregar_progresso(uid)
    }
    return jsonify(dados)

@app.route('/salvar_sip', methods=['POST'])
def salvar_sip():
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE usuarios SET provedor = ?, servidor = ?, sip_usuario = ?, sip_senha = ? WHERE id = ?
    """, (request.form.get('provedor'), request.form.get('servidor'), request.form.get('sip_usuario'), request.form.get('sip_senha'), session['user_id']))
    conn.commit()
    conn.close()
    return redirect(url_for('painel'))

@app.route('/upload_planilha', methods=['POST'])
def upload_planilha():
    if 'user_id' not in session: return redirect(url_for('login'))
    file = request.files.get('planilha')
    if file:
        file.save(os.path.join(PASTA_UPLOADS, f"user_{session['user_id']}_planilha.xlsx"))
        salvar_progresso(session['user_id'], 0)
    return redirect(url_for('painel'))

@app.route('/audios')
def listar_audios():
    if 'user_id' not in session: return jsonify([])
    return jsonify([f for f in os.listdir(PASTA_AUDIOS) if f.lower().endswith(('.mp3', '.wav', '.ogg'))])

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    if 'user_id' not in session: return jsonify({"mensagem": "Não autorizado"})
    file = request.files.get('audio')
    if file:
        file.save(os.path.join(PASTA_AUDIOS, file.filename))
        return jsonify({"mensagem": "Áudio enviado!"})
    return jsonify({"mensagem": "Erro no arquivo!"})

@app.route('/stream_audio/<filename>')
def stream_audio(filename):
    if 'user_id' not in session: return "Não autorizado", 401
    return send_from_directory(PASTA_AUDIOS, filename)

@app.route('/apagar_audio/<filename>', methods=['DELETE'])
def apagar_audio(filename):
    if 'user_id' not in session: return jsonify({"mensagem": "Não autorizado"})
    fp = os.path.join(PASTA_AUDIOS, filename)
    if os.path.exists(fp): os.remove(fp)
    return jsonify({"mensagem": "Áudio apagado!"})

@app.route('/iniciar', methods=['POST'])
def iniciar():
    if 'user_id' not in session: return jsonify({"mensagem": "Não autorizado"}), 401
    uid = session['user_id']
    if uid not in status_por_usuario:
        status_por_usuario[uid] = {}
        
    if status_por_usuario[uid].get("status") != "Rodando":
        threading.Thread(target=executar_disparos_background, args=(uid, session['username']), daemon=True).start()
        return jsonify({"mensagem": "Automação iniciada!"})
    return jsonify({"mensagem": "Já está rodando!"})

@app.route('/parar', methods=['POST'])
def parar():
    if 'user_id' not in session: return jsonify({"mensagem": "Não autorizado"}), 401
    uid = session['user_id']
    if uid in status_por_usuario:
        status_por_usuario[uid]["status"] = "Parado"
        status_por_usuario[uid]["progresso"] = "Pausado"
    return jsonify({"mensagem": "Pausado!"})

@app.route('/resetar', methods=['POST'])
def resetar():
    if 'user_id' not in session: return jsonify({"mensagem": "Não autorizado"}), 401
    uid = session['user_id']
    salvar_progresso(uid, 0)
    if uid in status_por_usuario:
        status_por_usuario[uid]["status"] = "Parado"
        status_por_usuario[uid]["progresso"] = "Reiniciado"
    return jsonify({"mensagem": "Fila zerada!"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)