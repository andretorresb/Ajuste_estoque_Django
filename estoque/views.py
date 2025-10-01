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
def ajustar_lote(request):
    """
    POST /api/estoque/ajustar_lote/
    Body JSON:
    {
      "empresa": 1,
      "idalmox": 1,
      "usuario_id": 1,
      "usuario_label": "SUPORTE",
      "motivo": "Ajuste de fechamento",
      "items": [
         {"idproduto": 3, "delta": 1},
         {"idproduto": 5, "delta": -2, "motivo": "Quebra"}
      ]
    }
    Retorna: [{idproduto, saldo}, ...]
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
def ajustar_lote(request):
    """
    POST /api/estoque/ajustar_lote/
    body:
    {
      "empresa":1,
      "idalmox":1,
      "usuario_id":1,
      "usuario_label":"SUPORTE",
      "idinventario": null OR existing id,
      "items":[ {"idproduto":123,"delta":1,"motivo":"..."}, ... ]
    }
    Se idinventario nao for passado -> cria um novo inventario e usa ele.
    Para cada item chama ajustar_estoque_TESTPRODUTOESTOQUE(..., idinventario=...)
    Retorna: {"idinventario": X, "results":[ {"idproduto":..., "saldo":...}, ... ]}
    """
    data = request.data or {}
    empresa = data.get('empresa') or 1
    idalmox = data.get('idalmox') or 1
    usuario_id = data.get('usuario_id')
    usuario_label = data.get('usuario_label')
    idinventario = data.get('idinventario')  # optional
    items = data.get('items') or []

    if not isinstance(items, list) or len(items) == 0:
        return Response({"detail": "Nenhum item para ajustar"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # cria inventario se nao informado
        if not idinventario:
            idinventario = criar_testinventario(empresa=empresa, idalmox=idalmox, usuario_id=usuario_id, usuario_label=usuario_label, motivo="Inventario de lote via API")

        results = []
        for it in items:
            pid = it.get('idproduto')
            delta = it.get('delta')
            motivo = it.get('motivo')
            if pid is None or delta is None:
                results.append({"idproduto": pid, "error": "idproduto ou delta ausente"})
                continue
            try:
                novo = ajustar_estoque_TESTPRODUTOESTOQUE(
                    empresa=empresa,
                    idproduto=pid,
                    delta=delta,
                    usuario_id=usuario_id,
                    usuario_label=usuario_label,
                    motivo=motivo,
                    idalmox=idalmox,
                    idinventario=idinventario
                )
                results.append({"idproduto": pid, "saldo": float(novo)})
            except Exception as e:
                results.append({"idproduto": pid, "error": str(e)})

        return Response({"idinventario": int(idinventario), "results": results}, status=200)
    except Exception as e:
        if settings.DEBUG:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Erro ao processar lote"}, status=status.HTTP_400_BAD_REQUEST)

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
def ajustar(request):
    """
    POST /api/estoque/ajustar/
    body: {"empresa":1,"idproduto":123,"delta":1,"motivo":"...", "usuario": 5, "usuario_label": "SUPORTE"}
    - 'usuario' : id do usuário (inteiro). Opcional.
    - 'usuario_label': string com o nome/login do usuário (opcional).
    Prioridade: se usuário informado no body será usado; se não, tenta request.user (se autenticado).
    """
    s = AjusteSerializer(data=request.data)
    s.is_valid(raise_exception=True)

    # empresa pode vir no body ou querystring; default 1
    empresa = request.data.get('empresa') or request.GET.get('empresa') or 1
    try:
        empresa = int(empresa)
    except Exception:
        return Response({"detail": "empresa inválida"}, status=status.HTTP_400_BAD_REQUEST)

    # obter usuario_id (campo 'usuario' no body) ou request.user
    usuario_id = None
    try:
        # aceitar 'usuario' ou 'usuario_id' no body (compatibilidade)
        raw_user = None
        if 'usuario' in request.data:
            raw_user = request.data.get('usuario')
        elif 'usuario_id' in request.data:
            raw_user = request.data.get('usuario_id')

        if raw_user not in (None, ''):
            usuario_id = int(raw_user)
        elif getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False):
            # se o Django autentico estiver presente usa request.user.id
            try:
                usuario_id = int(getattr(request.user, 'id', None))
            except Exception:
                usuario_id = None
    except Exception:
        usuario_id = None

    # usuario_label vindo no body (opcional)
    usuario_label = request.data.get('usuario_label') or request.data.get('usuarioName') or request.data.get('usuario_nome')

    # se só veio id e não label, tentamos resolver o label via buscar_usuarios_TGERUSUARIO
    resolved_label = _resolve_user_label(usuario_id, usuario_label)

    try:
        novo = ajustar_estoque_TESTPRODUTOESTOQUE(
            empresa=empresa,
            idproduto=s.validated_data['idproduto'],
            delta=s.validated_data['delta'],
            usuario_id=usuario_id,
            usuario_label=resolved_label,
            motivo=s.validated_data.get('motivo'),
            bloquear_negativo=True
        )
        return Response({'idproduto': s.validated_data['idproduto'], 'saldo': float(novo)}, status=status.HTTP_200_OK)
    except Exception as e:
        # retornar mensagem útil em DEBUG
        msg = str(e)
        if settings.DEBUG:
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Erro ao ajustar estoque'}, status=status.HTTP_400_BAD_REQUEST)


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