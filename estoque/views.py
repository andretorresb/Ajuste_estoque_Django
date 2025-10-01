# estoque/views.py
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .serializers import AjusteSerializer, ProdutoQuerySerializer
from .firebird_ops import (
    buscar_produtos_TESTPRODUTO,
    obter_produto_com_estoque,
    buscar_usuarios_TGERUSUARIO,
    verificar_credenciais_TGERUSUARIO,
    criar_testinventario,
    ajustar_lote_TESTPRODUTOESTOQUE,
)



@api_view(['POST'])
@permission_classes([AllowAny])
def criar_inventario_view(request):
    """
    POST /api/estoque/inventario/
    body: { "empresa":1, "idalmox":1, "usuario_id":1, "usuario_label":"SUPORTE", "motivo":"..." }
    retorna { "idinventario": 123 }
    """
    data = request.data or {}
    empresa = data.get('empresa') or 1
    idalmox = data.get('idalmox') or 1
    usuario_id = data.get('usuario_id')
    usuario_label = data.get('usuario_label')
    motivo = data.get('motivo')
    try:
        idinv = criar_testinventario(empresa=empresa, idalmox=idalmox, usuario_id=usuario_id, usuario_label=usuario_label, motivo=motivo)
        return Response({"idinventario": int(idinv)}, status=200)
    except Exception as e:
        if settings.DEBUG:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Erro ao criar inventario"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def usuarios_auth(request):
    """
    POST /api/usuarios/auth/
    Body JSON: { "username": "SUPORTE", "password": "senha123" }
    Também aceita {"id": 1, "password": "..." } ou {"usuario": "SUPORTE", "password": "..."}
    Retorna 200 com { ok: true, id, username, nome } em caso de sucesso.
    Retorna 401 em caso de credenciais inválidas.
    """
    data = request.data or {}
    login = data.get('username') or data.get('usuario') or data.get('id')
    password = data.get('password') or data.get('senha')

    if not login or not password:
        return Response({'detail': 'Usuário e senha são obrigatórios.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        res = verificar_credenciais_TGERUSUARIO(login, password)
    except Exception as e:
        if settings.DEBUG:
            return Response({'detail': f'Erro de validação: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'detail': 'Erro interno'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if res.get('ok'):
        u = res['user']
        return Response({'ok': True, 'id': int(u.get('id')) if u.get('id') is not None else None,
                         'username': u.get('username'),
                         'nome': u.get('nome')}, status=status.HTTP_200_OK)
    else:
        # credenciais inválidas
        return Response({'detail': 'Credenciais inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)


def _resolve_user_label(usuario_id, usuario_label):
    """
    Se veio usuario_label retorna ele; se não veio mas veio usuario_id tenta
    buscar o nome via buscar_usuarios_TGERUSUARIO() (pesquisa em lote).
    Retorna string ou None.
    """
    if usuario_label:
        return str(usuario_label)
    if not usuario_id:
        return None
    try:
        usuarios = buscar_usuarios_TGERUSUARIO()
        # possíveis chaves: id, idusuario, IDUSUARIO
        for u in usuarios:
            uid = u.get("id") or u.get("idusuario") or u.get("IDUSUARIO")
            if uid is None:
                continue
            try:
                if int(uid) == int(usuario_id):
                    # prefer nome, senão username
                    return (u.get("nome") or u.get("username") or u.get("user") or str(uid))
            except Exception:
                continue
    except Exception:
        # falha ao obter lista de usuarios -> retorna None e o caller fará fallback
        return None
    return None


@api_view(['POST'])
@permission_classes([AllowAny])
def ajustar_lote(request):
    """
    POST /api/estoque/ajustar_lote/
    body:
    {
      "empresa":1,
      "idalmox":1,
      "usuario_id":1,
      "usuario_label":"SUPORTE",
      "motivo":"Ajuste de fechamento",
      "items":[ {"idproduto":123,"delta":1,"motivo":"..."}, ... ]
    }
    Usa a função em lote ajustar_lote_TESTPRODUTOESTOQUE que cria UM inventário
    e insere todos os movimentos em sequência.
    Retorna: {'ok': True, 'results': [{idproduto, saldo}, ...]}
    """
    data = request.data or {}
    items = data.get('items')
    if not items or not isinstance(items, list):
        return Response({'detail': "items é obrigatório (lista)."}, status=status.HTTP_400_BAD_REQUEST)

    empresa = data.get('empresa') or request.GET.get('empresa') or 1
    try:
        empresa = int(empresa)
    except Exception:
        return Response({'detail': 'empresa inválida'}, status=status.HTTP_400_BAD_REQUEST)

    idalmox = data.get('idalmox') or 1
    usuario_id = data.get('usuario_id') or data.get('usuario')
    usuario_label = data.get('usuario_label') or data.get('usuarioName')

    try:
        results = ajustar_lote_TESTPRODUTOESTOQUE(
            empresa=empresa,
            items=items,
            idalmox=idalmox,
            usuario_id=usuario_id,
            usuario_label=usuario_label,
            motivo_geral=data.get('motivo')
        )
        return Response({'ok': True, 'results': results}, status=status.HTTP_200_OK)
    except Exception as e:
        if settings.DEBUG:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Erro ao processar ajuste em lote'}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def produtos_list(request):
    """
    GET /api/estoque/produtos/?limit=25&query=...&empresa=1
    """
    s = ProdutoQuerySerializer(data=request.query_params)
    s.is_valid(raise_exception=True)
    query = s.validated_data.get('query')
    limit = s.validated_data.get('limit') or 25

    # pega empresa da querystring (ou usa 1 se não informado)
    empresa = request.query_params.get('empresa') or 1
    try:
        empresa = int(empresa)
    except Exception:
        empresa = 1

    try:
        itens = buscar_produtos_TESTPRODUTO(query, empresa, limit)
        return Response({"count": len(itens), "results": itens}, status=status.HTTP_200_OK)
    except Exception as e:
        if settings.DEBUG:
            return Response({"detail": f"Erro na busca: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"detail": "Erro interno"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([AllowAny])
def produto_detail(request, idproduto):
    """
    GET /api/estoque/produtos/<idproduto>/?empresa=1
    """
    try:
        empresa = request.GET.get('empresa') or 1
        p = obter_produto_com_estoque(idproduto, empresa)
        if not p:
            return Response({"detail": "Produto não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(p, status=status.HTTP_200_OK)
    except Exception as e:
        if settings.DEBUG:
            return Response({"detail": f"Erro ao carregar produto: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"detail": "Erro interno"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def usuarios_list(request):
    """
    GET /api/usuarios/  -> devolve lista de usuários ATIVOS (TGERUSUARIO)
    Formato: [{id, username, nome, ativo}, ...]
    """
    try:
        usuarios = buscar_usuarios_TGERUSUARIO()
        return Response(usuarios, status=status.HTTP_200_OK)
    except Exception as e:
        if settings.DEBUG:
            return Response({"detail": f"Erro ao buscar usuarios: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"detail": "Erro interno"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)