# launcher.py (versão ajustada)
import os
import sys
import logging
import importlib
import socket
from pathlib import Path

# --- Paths / frozen support ---
BASE_DIR = Path(__file__).resolve().parent

# Se estiver empacotado com PyInstaller, adicionar _MEIPASS ao path (extração onefile)
if getattr(sys, "frozen", False):
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # inserir antes para que importlib encontre módulos extraídos primeiro
        sys.path.insert(0, meipass)

# garantir que o diretório base do projeto esteja no path para imports como config.settings
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ajuste_estoque.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# --- Funções utilitárias ---
def detect_local_ip():
    """Retorna o IP local que é acessível na rede (tenta não usar 127.x)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # endereço externo apenas para descobrir a interface (não conecta realmente)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "localhost"


def find_settings_module_by_file(base: Path):
    """
    Procura recursivamente por arquivos 'settings.py' no projeto e converte para módulo.
    Ex.: <BASE>/config/settings.py -> 'config.settings'
    Retorna a primeira ocorrência útil (exclui venv/site-packages).
    """
    candidates = []
    for p in base.rglob("*/settings.py"):
        s = str(p).lower()
        if ".venv" in s or "site-packages" in s or "dist-packages" in s:
            continue
        # derivar módulo relativo a BASE_DIR
        try:
            rel = p.relative_to(base)
            parts = rel.with_suffix("").parts  # e.g. ('config','settings')
            # só aceitar se tiver pelo menos 2 partes (pacote + settings)
            if len(parts) >= 2:
                module = ".".join(parts)
                candidates.append((p, module))
        except Exception:
            continue
    # priorizar config.settings, core.settings se existirem
    priority = ("config.settings", "core.settings", "settings")
    for pr in priority:
        for p, mod in candidates:
            if mod == pr:
                return mod
    # se não achou prioridade, retorna primeiro candidato (se houver)
    return candidates[0][1] if candidates else None


def choose_settings_module():
    """
    Tenta descobrir um módulo de settings importável e retorna string 'package.settings'.
    1) tenta importações comuns
    2) tenta detectar por arquivo
    """
    tried = []
    common = [
        "config.settings",
        "core.settings",
        "settings",
        "config.settings_build",  # possível temporário
    ]
    for mod in common:
        tried.append(mod)
        try:
            importlib.import_module(mod)
            logger.info(f"Using settings module (quick): {mod}")
            return mod
        except Exception:
            continue

    # fallback: procurar por settings.py em disco e formar módulo
    try:
        detected = find_settings_module_by_file(BASE_DIR)
        if detected:
            tried.append(f"detected:{detected}")
            try:
                importlib.import_module(detected)
                logger.info(f"Using settings module (detected): {detected}")
                return detected
            except Exception as e:
                logger.warning(f"Found settings file for {detected} but failed import: {e}")
    except Exception as e:
        logger.exception(f"Erro procurando settings.py: {e}")

    logger.error(f"Impossível localizar um módulo de settings. Tentadas: {tried}")
    return None


def ensure_templates_dirs(settings_module_name):
    """
    Se possível, adiciona caminhos extras em settings.TEMPLATES[0]['DIRS'] para suportar exe.
    Acrescenta:
      - sys._MEIPASS/templates
      - sys._MEIPASS/templates/web
      - <BASE_DIR>/templates
      - <BASE_DIR>/web/templates
      - <BASE_DIR>/web/templates/web
    """
    try:
        settings_mod = importlib.import_module(settings_module_name)
    except Exception as e:
        logger.warning(f"Não foi possível importar {settings_module_name} para ajustar TEMPLATES: {e}")
        return

    tpl = getattr(settings_mod, "TEMPLATES", None)
    if not tpl or not isinstance(tpl, (list, tuple)):
        logger.info("TEMPLATES não definido ou não é lista/tupla — pulando ajuste de DIRS.")
        return

    current_dirs = list(tpl[0].get("DIRS", [])) or []

    possible_paths = []

    # caminhos extraídos pelo PyInstaller (quando empacotado)
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        meip = str(sys._MEIPASS)
        possible_paths.append(os.path.join(meip, "templates"))
        possible_paths.append(os.path.join(meip, "templates", "web"))

    # caminhos de desenvolvimento / after extraction in onedir
    possible_paths.append(str(BASE_DIR / "web" / "templates"))
    possible_paths.append(str(BASE_DIR / "web" / "templates" / "web"))
    possible_paths.append(str(BASE_DIR / "templates"))

    # adicionar no final apenas se existir fisicamente ou (se empacotado) sempre adicionar meipass paths
    for p in possible_paths:
        if p not in current_dirs:
            if os.path.exists(p) or (getattr(sys, "frozen", False) and ("_MEIPASS" in str(p) or "templates" in p)):
                current_dirs.append(p)

    tpl[0]["DIRS"] = current_dirs
    logger.info(f"TEMPLATES DIRS ajustados: {tpl[0]['DIRS']}")


# --- Antes de qualquer import do Django: garantir DJANGO_SETTINGS_MODULE ---
settings_mod = choose_settings_module()
if settings_mod:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_mod)
else:
    logger.error(
        "Nenhum módulo de settings encontrado (tente config.settings, core.settings ou gerar config.settings_build)."
    )
    print("❌ ERRO: Nenhum módulo de settings encontrado (ver logs).")
    input("Pressione ENTER para sair...")
    sys.exit(1)


# --- Função para iniciar o Django + Waitress ---
def iniciar_django():
    """Inicia o servidor Django com Waitress. Ajusta templates antes do get_wsgi_application()."""
    # Ajusta TEMPLATES DIRS para modo empacotado/dev
    try:
        ensure_templates_dirs(os.environ["DJANGO_SETTINGS_MODULE"])
    except Exception:
        logger.exception("Erro ajustando TEMPLATES DIRS")

    # Agora importar Django e WSGI
    try:
        from django.core.wsgi import get_wsgi_application
        from waitress import serve
    except Exception as e:
        logger.exception("Erro ao importar Django/Waitress")
        raise

    # obter aplicação WSGI (dispara django.setup internamente)
    try:
        application = get_wsgi_application()
    except Exception as exc:
        # se TemplateDoesNotExist acontecer aqui, logamos os DIRS pra ajudar a debugar
        logger.exception("Erro obtendo get_wsgi_application()")
        raise

    # detectar ip acessível
    local_ip = detect_local_ip()
    hostname = os.environ.get("COMPUTERNAME", local_ip)

    print("\n" + "=" * 70)
    print("  SERVIDOR INICIADO COM SUCESSO!")
    print("=" * 70)
    print(f"\n  Acesse localmente:   http://localhost:8000")
    print(f"  Acesse pela rede:    http://{local_ip}:8000")
    print(f"  (ou http://{hostname}:8000 se o nome do PC resolver na sua rede)")
    print("\n  Para sair: Feche esta janela ou pressione Ctrl+C")
    print("\n" + "=" * 70 + "\n")

    logger.info(f"Servidor aguardando conexões na porta 8000 (host 0.0.0.0). IP detectado: {local_ip}")

    try:
        serve(application, host="0.0.0.0", port=8000, threads=4)
    except KeyboardInterrupt:
        print("\n\nServidor encerrado.")
        logger.info("Servidor encerrado pelo usuário")


# --- main (carrega config Ello, testa Firebird, etc) ---
def main():
    print("\n" + "=" * 70)
    print("  AJUSTE DE ESTOQUE - Sistema Ello")
    print("=" * 70 + "\n")

    try:
        # Exemplo: carregar configuração do ello.ini (seu módulo)
        print("1. Carregando configurações do ello.ini...")
        from core.config_loader import carregar_config_ello

        config = carregar_config_ello()

        print(f"   ✓ Arquivo banco: {config['database']}")
        print(f"   ✓ Servidor:      {config['hostname']}")

        # Testar conexão com Firebird
        print("\n2. Testando conexão com Firebird...")
        from core.firebird_db import fb_connect

        con = fb_connect()
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM TESTPRODUTO")
        qtd = cur.fetchone()[0]
        cur.close()
        con.close()

        print(f"   ✓ Conexão OK! ({qtd} produtos cadastrados)")

        # Iniciar servidor web
        print("\n3. Iniciando servidor web...")
        iniciar_django()

    except FileNotFoundError as e:
        print(f"\n❌ ERRO: {e}")
        print("\nVerifique:  • O sistema Ello está instalado • O arquivo ello.ini existe")
        input("\nPressione ENTER para sair...")
        sys.exit(1)

    except ConnectionError as e:
        print(f"\n❌ ERRO: {e}")
        print("\nVerifique:  • O Firebird está rodando")
        input("\nPressione ENTER para sair...")
        sys.exit(1)

    except Exception as e:
        logger.exception("Erro inesperado durante inicialização")
        print(f"\n❌ ERRO INESPERADO: {e}")
        print("\nVerifique o arquivo ajuste_estoque.log para mais detalhes")
        input("\nPressione ENTER para sair...")
        sys.exit(1)


if __name__ == "__main__":
    main()
