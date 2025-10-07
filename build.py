# build.py — Smart build for PyInstaller (auto templatetags + temporary build settings)
import os
import sys
import shutil
import textwrap
from pathlib import Path
import PyInstaller.__main__

print("=" * 60)
print("  GERANDO EXECUTÁVEL - Ajuste de Estoque")
print("=" * 60 + "\n")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PKG = "config"
ORIGINAL_SETTINGS = f"{CONFIG_PKG}.settings"
TEMP_SETTINGS_MODULE = f"{CONFIG_PKG}.settings_build"
TEMP_SETTINGS_PATH = BASE_DIR / CONFIG_PKG / "settings_build.py"

# Limpar builds anteriores
for folder in ['dist', 'build']:
    folder_path = BASE_DIR / folder
    if folder_path.exists():
        print(f"Limpando pasta {folder}...")
        shutil.rmtree(folder_path)

# --- cria settings_build.py temporário baseado no settings original ---
def write_temp_settings():
    """
    Cria config/settings_build.py que importa tudo de config.settings e remove django.contrib.gis
    para evitar warnings/erros do PyInstaller se você não usar GIS.
    """
    content = textwrap.dedent(f"""
    # Auto-generated temporary settings for packaging.
    # Imports original settings and applies lightweight patch for packaging.
    try:
        from {ORIGINAL_SETTINGS} import *
    except Exception as e:
        # se não der pra importar, cria um settings mínimo para o build
        INSTALLED_APPS = []
        DATABASES = {{}}
        SECRET_KEY = "packaging-temp-key"
        DEBUG = False
    else:
        # remover django.contrib.gis se estiver presente (comumente causa erro por GDAL ausente)
        INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django.contrib.gis']
    """)
    # garante pasta config existe
    (BASE_DIR / CONFIG_PKG).mkdir(parents=True, exist_ok=True)
    with open(TEMP_SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[ok] criado settings temporário em: {TEMP_SETTINGS_PATH}")

def remove_temp_settings():
    try:
        if TEMP_SETTINGS_PATH.exists():
            TEMP_SETTINGS_PATH.unlink()
            print(f"[ok] removido settings temporário: {TEMP_SETTINGS_PATH}")
    except Exception as e:
        print(f"[warn] não foi possível remover settings temporário: {e}")

# --- detectar templatetags e gerar hidden-imports automaticamente ---
def collect_templatetag_hidden_imports(base: Path):
    hidden = set()
    # procura por arquivos *.py em qualquer pasta 'templatetags'
    for pyfile in base.rglob("*/templatetags/*.py"):
        if pyfile.name == "__init__.py":
            continue
        # converter caminho relativo em módulo Python: ex web/templatetags/filters.py -> web.templatetags.filters
        try:
            rel = pyfile.relative_to(base)
        except Exception:
            continue
        module = ".".join(rel.with_suffix("").parts)
        hidden.add(module)
    return sorted(hidden)

# --- localizar templates/static/core/estoque (só inclui se existir) ---
def find_templates_dir(base: Path):
    # **IMPORTANTE**: preferimos empacotar 'web/templates' (contendo a subpasta 'web')
    preferred = base / 'web' / 'templates'
    if preferred.exists() and preferred.is_dir():
        return preferred
    # fallback: a primeira pasta 'templates' válida (exclui venv/site-packages)
    for p in base.rglob('templates'):
        if p.is_dir() and '.venv' not in str(p).lower() and 'site-packages' not in str(p).lower():
            return p
    return None

def make_add_data_arg(src: Path, dest: str) -> str:
    src_str = str(src)
    # PyInstaller usa os.pathsep (no Windows ';') para separar src/dest
    pair = f"{src_str}{os.pathsep}{dest}"
    return f"--add-data={pair}"

# --- main build flow ---
try:
    write_temp_settings()
    # garantir que BASE_DIR esteja no sys.path para que o settings_build seja importável
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    # setar DJANGO_SETTINGS_MODULE temporário durante o build
    os.environ['DJANGO_SETTINGS_MODULE'] = TEMP_SETTINGS_MODULE
    print(f"[ok] DJANGO_SETTINGS_MODULE={os.environ['DJANGO_SETTINGS_MODULE']} (temporário)")

    # montar args base
    args = [
        'launcher.py',
        '--name=AjusteEstoque',
        '--onefile',
        '--console',
        '--icon=icon.ico',
        '--hidden-import=django',
        '--hidden-import=django.contrib.contenttypes',
        '--hidden-import=django.contrib.auth',
        '--hidden-import=firebirdsql',
        '--hidden-import=waitress',
        '--collect-all=django',
        '--noconfirm',
    ]

    # add-data dinâmico
    add_data_args = []
    templates_dir = find_templates_dir(BASE_DIR)
    if templates_dir:
        print(f"[ok] templates encontrado em: {templates_dir}")
        # aqui empacotamos a pasta 'web/templates' inteira como 'templates'
        add_data_args.append(make_add_data_arg(templates_dir, "templates"))
    else:
        print("[warn] nenhum diretório de templates encontrado (pulando templates).")

    for name in ("static", "core", "estoque"):
        p = BASE_DIR / name
        if p.exists() and p.is_dir():
            print(f"[ok] incluindo {name}: {p}")
            add_data_args.append(make_add_data_arg(p, name))
        else:
            print(f"[info] pasta '{name}' não encontrada em {BASE_DIR} (pulando).")

    args += add_data_args

    # detectar automaticamente templatetags -> adiciona como hidden-import
    templatetags = collect_templatetag_hidden_imports(BASE_DIR)
    if templatetags:
        print(f"[ok] encontradas {len(templatetags)} templatetags. Adicionando como hidden-imports.")
        for mod in templatetags:
            args.append(f"--hidden-import={mod}")
    else:
        print("[info] nenhuma templatetag detectada automaticamente.")

    # imprimir args pra debugar
    print("\nPyInstaller será executado com os seguintes argumentos:")
    for a in args:
        print(" ", a)
    print()

    # executar PyInstaller
    PyInstaller.__main__.run(args)

finally:
    # cleanup: remover settings temporário e desfazer var de ambiente
    remove_temp_settings()
    if 'DJANGO_SETTINGS_MODULE' in os.environ:
        del os.environ['DJANGO_SETTINGS_MODULE']
    print("\n" + "=" * 60)
    print("  ✓ BUILD (término ou tentativa concluída)")
    print("=" * 60)
    print("\nArquivo (esperado): dist/AjusteEstoque.exe")
    print("\nPróximos passos:")
    print("1. Testar o .exe em um PC sem Python")
    print("2. Verificar se lê o ello.ini corretamente")
    print("3. Criar pacote .zip para distribuição")
