import time
import sys
import pandas as pd
import pjsip as pj

# --- SEUS DADOS DA VONO ---
SIP_DOMAIN = "vono3.me"
SIP_USER = "company1"
SIP_PASSWORD = "company1"

# Nome exato da sua planilha de clientes
ARQUIVO_EXCEL = "clientes.xlsx"

def carregar_clientes_do_excel(caminho):
    try:
        df = pd.read_excel(caminho)
        clientes = []
        
        # Colunas de telefone existentes na planilha
        colunas_tel = ["telefone1", "telefone2", "telefone3", "telefone4", "telefone5"]
        
        for index, row in df.iterrows():
            nome = str(row.get("nome", f"Cliente {index+1}"))
            telefones_validos = []
            
            # Coleta todos os números preenchidos para este cliente
            for col in colunas_tel:
                if col in df.columns:
                    telefone_raw = row.get(col)
                    if pd.notna(telefone_raw):
                        telefone = ''.join(filter(str.isdigit, str(telefone_raw)))
                        # Ajusta formato se vier com 10 ou 11 dígitos
                        if len(telefone) in [10, 11]:
                            telefone = "55" + telefone
                        if len(telefone) >= 10 and telefone not in telefones_validos:
                            telefones_validos.append(telefone)
            
            if telefones_validos:
                clientes.append({"nome": nome, "telefones": telefones_validos})
                
        return clientes
    except Exception as e:
        print(f"[ERRO] Não foi possível ler o arquivo Excel: {e}")
        return []

chamada_ativa = None
status_chamada_atual = None

class CallCallback(pj.CallCallback):
    def __init__(self, call=None):
        pj.CallCallback.__init__(self, call)

    def on_state(self):
        global chamada_ativa, status_chamada_atual
        estado = self.call.info().state_text
        status_chamada_atual = estado
        print(f"[STATUS] {estado}")
        
        if self.call.info().state == pj.CallState.DISCONNECTED:
            print("[INFO] Chamada encerrada.")
            chamada_ativa = None

class AccountCallback(pj.AccountCallback):
    def __init__(self, account=None):
        pj.AccountCallback.__init__(self, account)

    def on_reg_state(self):
        if self.account.info().reg_status == 200:
            print("[SUCESSO] Conectado e registrado no servidor Vono3.me!")
        else:
            print(f"[AVISO] Status de registro: {self.account.info().reg_reason}")

def iniciar_robo_lote():
    global chamada_ativa, status_chamada_atual

    clientes = carregar_clientes_do_excel(ARQUIVO_EXCEL)
    if not clientes:
        print("[ERRO] Nenhum cliente válido encontrado na planilha. Verifique o arquivo.")
        return

    total_fichas = len(clientes)
    print(f"[INFO] {total_fichas} clientes carregados. Iniciando varredura multitelefone...")

    lib = pj.Lib()
    try:
        lib.init()
    except pj.Error as e:
        print(f"Erro ao inicializar SIP: {e}")
        return

    try:
        transport_config = pj.TransportConfig()
        transport_config.port = 5060
        lib.create_transport(pj.TransportType.UDP, transport_config)
    except Exception:
        lib.create_transport(pj.TransportType.UDP)

    lib.start()

    acc_config = pj.AccountConfig()
    acc_config.id = f"sip:{SIP_USER}@{SIP_DOMAIN}"
    acc_config.reg_uri = f"sip:{SIP_DOMAIN}"
    acc_config.cred_info.append(
        pj.CredentialInfo(SIP_DOMAIN, "*", SIP_USER, SIP_PASSWORD)
    )

    acc = lib.create_account(acc_config)
    acc_cb = AccountCallback(acc)
    acc.set_callback(acc_cb)

    print("[INFO] Conectando na Vono3.me...")
    time.sleep(3)

    for i, cliente in enumerate(clientes):
        nome = cliente["nome"]
        telefones = cliente["telefones"]
        
        print(f"\n========================================")
        print(f"[{i+1}/{total_fichas}] Cliente: {nome} ({len(telefones)} números disponíveis)")
        print(f"========================================")

        # Passa por cada número cadastrado para este cliente
        for idx_tel, numero in enumerate(telefones):
            print(f"\n[DISCAGEM] Tentativa {idx_tel+1} para {nome} -> Número: {numero}")

            uri_destino = f"sip:{numero}@{SIP_DOMAIN}"
            call_cb = CallCallback()
            
            status_chamada_atual = "CALLING"
            chamada_ativa = acc.make_call(uri_destino, cb=call_cb)
            
            # Tempo limite de 30 segundos por tentativa de número
            tempo_limite = 30
            inicio = time.time()

            while chamada_ativa is not None:
                time.sleep(0.5)
                if time.time() - inicio > tempo_limite:
                    print("[INFO] Tempo limite excedido nesta tentativa. Desligando...")
                    try:
                        chamada_ativa.hangup()
                    except Exception:
                        pass
                    break

            # Pausa de 2 segundos entre um número e outro do mesmo cliente
            time.sleep(2)

        print("[INFO] Fim das tentativas para este cliente. Pausando 3 segundos para o próximo...")
        time.sleep(3)

    print("\n[INFO] Lote 100% finalizado! Todos os números de todos os clientes foram processados.")
    lib.destroy()

if __name__ == "__main__":
    iniciar_robo_lote()