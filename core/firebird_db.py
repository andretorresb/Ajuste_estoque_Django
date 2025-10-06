import firebirdsql
import logging
from .config_loader import carregar_config_ello

logger = logging.getLogger(__name__)

# Carregar configuração do ello.ini ao iniciar Django
try:
    DB_CONFIG = carregar_config_ello()
    CHARSET = DB_CONFIG['charset']
    logger.info(f"Configuração carregada: {DB_CONFIG['database']}")
except Exception as e:
    logger.error(f"Erro ao carregar configuração: {e}")
    DB_CONFIG = None
    CHARSET = 'ISO8859_1'

def fb_connect():
    """Conecta ao Firebird usando configurações do ello.ini"""
    if not DB_CONFIG:
        raise RuntimeError(
            "Configuração do banco não foi carregada!\n"
            "Verifique se o arquivo ello.ini existe."
        )
    
    try:
        logger.info('Conectando ao banco de dados Firebird...')
        
        connection = firebirdsql.connect(
            user=DB_CONFIG['username'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            host=DB_CONFIG['hostname'],
            charset=DB_CONFIG['charset']
        )
        
        logger.info('Conexão estabelecida com sucesso.')
        return connection
        
    except Exception as e:
        logger.error(f'Erro ao conectar ao banco: {e}')
        raise ConnectionError(f"Falha ao conectar no Firebird: {e}")