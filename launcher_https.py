import os
import sys
import logging
from pathlib import Path
from threading import Thread
import time

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def iniciar_django_thread():
    """Inicia Django em thread separada"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from waitress import serve
    from django.core.wsgi import get_wsgi_application
    
    application = get_wsgi_application()
    serve(application, host='127.0.0.1', port=8000, threads=4)

def main():
    print("\n" + "=" * 70)
    print("  AJUSTE DE ESTOQUE - Sistema Ello (HTTPS)")
    print("=" * 70 + "\n")
    
    try:
        # Testar configuração
        print("1. Testando conexão com banco...")
        from core.firebird_db import fb_connect
        con = fb_connect()
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM TESTPRODUTO")
        qtd = cur.fetchone()[0]
        cur.close()
        con.close()
        print(f"   ✓ Conexão OK! ({qtd} produtos)")
        
        # Iniciar Django
        print("\n2. Iniciando Django...")
        django_thread = Thread(target=iniciar_django_thread, daemon=True)
        django_thread.start()
        time.sleep(3)
        print("   ✓ Django rodando")
        
        # Criar túnel HTTPS
        print("\n3. Criando túnel HTTPS com ngrok...")
        from pyngrok import ngrok
        
        public_url = ngrok.connect(8000, bind_tls=True)
        
        print("\n" + "=" * 70)
        print("  ✓ SERVIDOR HTTPS ATIVO!")
        print("=" * 70)
        print(f"\n  URL: {public_url}")
        print("\n  COMO USAR:")
        print("  1. Copie o URL acima")
        print("  2. Abra no navegador do celular")
        print("  3. Faça login")
        print("  4. Clique no botão da câmera 📷")
        print("  5. Permita acesso à câmera")
        print("\n  Pressione Ctrl+C para parar")
        print("\n" + "=" * 70 + "\n")
        
        # Manter rodando
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nEncerrando...")
            ngrok.disconnect(public_url)
            print("Servidor parado.")
        
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        print(f"\n❌ ERRO: {e}")
        input("\nPressione ENTER...")
        sys.exit(1)

if __name__ == '__main__':
    main()