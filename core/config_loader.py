#core/config_loader.py
import configparser
import os
from pathlib import Path

def buscar_arquivo_ini():
    """Busca o arquivo ello.ini em locais comuns"""
    possiveis_caminhos = [
        'C:\\Ello\\Windows\\ello.ini',  # CAMINHO CORRETO
        'C:\\Ello\\ello.ini',
        'C:\\Ello\\Dados\\ello.ini',
        'C:\\Program Files\\Ello\\ello.ini',
        'C:\\Program Files (x86)\\Ello\\ello.ini',
        Path.home() / 'ello.ini',
    ]
    
    for caminho in possiveis_caminhos:
        caminho = Path(caminho)
        if caminho.exists():
            print(f"Arquivo .ini encontrado em: {caminho}")
            return str(caminho)
    
    # Se não encontrar, mostrar onde procurou
    print("Arquivo ello.ini NÃO encontrado nos seguintes locais:")
    for caminho in possiveis_caminhos:
        print(f"  - {caminho}")
    
    return None

def carregar_config_ello(caminho_ini=None):
    """
    Lê o ello.ini e retorna configurações do banco Firebird
    
    Formato esperado:
    [Dados]
    database=C:\Ello\Dados\MARTINAZZO.ELLO
    """
    if not caminho_ini:
        caminho_ini = buscar_arquivo_ini()
    
    if not caminho_ini or not os.path.exists(caminho_ini):
        raise FileNotFoundError(
            "Arquivo ello.ini não encontrado!\n"
            "Certifique-se de que existe em: C:\\Ello\\Windows\\ello.ini"
        )
    
    config = configparser.ConfigParser()
    config.read(caminho_ini, encoding='latin-1')
    
    # Ler caminho do banco da seção [Dados]
    database_path = config.get('Dados', 'database', fallback='')
    
    if not database_path:
        raise ValueError(
            "Caminho do banco não encontrado no ello.ini\n"
            "Esperado: [Dados] database=C:\\Caminho\\Banco.ELLO"
        )
    
    # Verificar se é servidor remoto ou local
    if ':' in database_path and database_path[1] != ':':
        # Servidor remoto
        hostname, db_path = database_path.split(':', 1)
    else:
        # Servidor local
        hostname = 'localhost'
        db_path = database_path
    
    return {
        'hostname': hostname,
        'database': db_path,
        'username': 'SYSDBA',
        'password': 'masterkey',
        'charset': 'ISO8859_1',
    }