# estoque/firebird_ops.py
from core.firebird_db import fb_connect, CHARSET
import hashlib
import time
from decimal import Decimal, InvalidOperation, getcontext
import re
import base64
import itertools

getcontext().prec = 28  # boa precisão p/ NUMERIC(18,4)


#------------Login e Senha -------------
def _try_segment_mapping(stored: str, plain: str):
    stored = '' if stored is None else str(stored)
    plain = '' if plain is None else str(plain)
    L = len(stored)
    N = len(plain)
    if N == 0 or L == 0 or N > L:
        return None
    if L == N:
        mapping = {}
        rev = {}
        ok = True
        for ch, seg in zip(plain, stored):
            if ch in mapping and mapping[ch] != seg:
                ok = False; break
            if seg in rev and rev[seg] != ch:
                ok = False; break
            mapping[ch] = seg; rev[seg] = ch
        return mapping if ok else None

    for cuts in itertools.combinations(range(1, L), N-1):
        parts = []
        last = 0
        for c in cuts:
            parts.append(stored[last:c])
            last = c
        parts.append(stored[last:])
        mapping = {}
        rev = {}
        ok = True
        for ch, seg in zip(plain, parts):
            if ch in mapping and mapping[ch] != seg:
                ok = False; break
            if seg in rev and rev[seg] != ch:
                ok = False; break
            mapping[ch] = seg
            rev[seg] = ch
        if ok:
            return mapping
    return None

def verificar_credenciais_TGERUSUARIO(login, password):
    if login is None or password is None:
        return {'ok': False, 'reason': 'missing'}

    login_str = str(login).strip()

    with fb_connect() as con:
        cur = con.cursor()
        try:
            sql = """
                SELECT *
                FROM TGERUSUARIO
                WHERE (USUARIO = ? OR CAST(IDUSUARIO AS VARCHAR(50)) = ?)
                  AND COALESCE(UPPER(ATIVO),'N') = 'S'
                """
            cur.execute(sql, (login_str, login_str))
            row = cur.fetchone()
            if not row:
                cur.close()
                return {'ok': False, 'reason': 'not_found'}
            cols = [c[0].strip().upper() for c in cur.description]
            rec = dict(zip(cols, row))
        finally:
            try:
                cur.close()
            except Exception:
                pass

    idusuario = rec.get('IDUSUARIO') or rec.get('ID') or rec.get('IdUsuario')
    username = (rec.get('USUARIO') or rec.get('USERNAME') or '')
    nome = (rec.get('NOME') or rec.get('NOMEUSUARIO') or rec.get('NOME_COMPLETO') or '')

    pwd_candidates = [c for c in cols if c.lower() in (
        'senha','password','pwd','passwd','pass','senha_hash','hash','senha_md5','password_hash'
    )]
    stored_val = None
    if pwd_candidates:
        for f in pwd_candidates:
            stored_val = rec.get(f)
            if stored_val not in (None, ''):
                break
    if stored_val is None:
        for c in cols:
            low = c.lower()
            if 'senh' in low or 'pass' in low:
                stored_val = rec.get(c)
                if stored_val not in (None, ''):
                    break

    if stored_val is None:
        return {'ok': False, 'reason': 'no_password_field', 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    if isinstance(stored_val, bytes):
        try:
            stored_str = stored_val.decode(CHARSET)
        except Exception:
            stored_str = stored_val.decode(errors='ignore')
    else:
        stored_str = str(stored_val)

    if password == stored_str:
        return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    pwb = password.encode('utf-8')
    for algo in ('md5','sha1','sha256'):
        h = getattr(hashlib, algo)(pwb).hexdigest()
        if h == stored_str:
            return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    try:
        b64 = base64.b64encode(pwb).decode('ascii')
        if b64 == stored_str:
            return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}
        b64u = base64.urlsafe_b64encode(pwb).decode('ascii')
        if b64u == stored_str:
            return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}
    except Exception:
        pass

    if password[::-1] == stored_str:
        return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    seg_map = _try_segment_mapping(stored_str, password)
    if seg_map:
        return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}, 'mapping': seg_map}

    return {'ok': False, 'reason': 'invalid_password'}


# ------------ Busca Usuarios ----------
def buscar_usuarios_TGERUSUARIO():
    sql = """
      SELECT IDUSUARIO, USUARIO, NOME, COALESCE(UPPER(ATIVO),'N') AS ATIVO
      FROM TGERUSUARIO
      WHERE COALESCE(UPPER(ATIVO),'N') = 'S'
      ORDER BY NOME
    """
    out = []
    with fb_connect() as con:
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [c[0].strip().upper() for c in cur.description]
        cur.close()

    for r in rows:
        d = dict(zip(cols, r))
        out.append({
            "id": d.get("IDUSUARIO"),
            "username": (d.get("USUARIO") or "").strip(),
            "nome": (d.get("NOME") or "").strip(),
            "ativo": d.get("ATIVO")
        })
    return out


# ---------- BUSCA LISTA ----------
def buscar_produtos_TESTPRODUTO(query: str | None, empresa: str | int | None, limit: int = 25):
    q_raw = (query or "").strip()
    q_like = f"%{q_raw.upper()}%" if q_raw else None

    params = []
    # Quando empresa fornecida, faz LEFT JOIN apenas para IDALMOX = 1 (não somar outros almox)
    if empresa is not None:
        sql = """
            SELECT
                P.IDPRODUTO,
                TRIM(P.DESCRICAO) AS DESCRICAO,
                TRIM(P.CODBARRAS) AS CODBARRAS,
                P.PRECOVENDA,
                COALESCE(E.ESTDISPONIVEL, 0) AS ESTDISPONIVEL
            FROM TESTPRODUTO P
            LEFT JOIN TESTPRODUTOESTOQUE E
              ON E.IDPRODUTOPRINCIPAL = P.IDPRODUTO
                 AND E.EMPRESA = CAST(? AS INTEGER)
                 AND E.IDALMOX = 1
            WHERE 1 = 1
        """
        params.append(int(empresa))
    else:
        sql = """
            SELECT
                P.IDPRODUTO,
                TRIM(P.DESCRICAO) AS DESCRICAO,
                TRIM(P.CODBARRAS) AS CODBARRAS,
                P.PRECOVENDA,
                0 AS ESTDISPONIVEL
            FROM TESTPRODUTO P
            WHERE 1 = 1
        """

    if q_raw:
        sql += " AND (UPPER(P.DESCRICAO) LIKE ? OR COALESCE(P.CODBARRAS,'') = ?)"
        params += [q_like, q_raw]

    sql += " ORDER BY P.IDPRODUTO ROWS 1 TO ?"
    params.append(int(limit))

    with fb_connect() as con:
        cur = con.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cols = [c[0].strip().upper() for c in cur.description]
        cur.close()

    out = []
    for r in rows:
        d = dict(zip(cols, r))
        out.append({
            "idproduto": d.get("IDPRODUTO"),
            "descricao": (d.get("DESCRICAO") or "").strip(),
            "codbarras": (d.get("CODBARRAS") or "").strip(),
            "precovenda": float(d.get("PRECOVENDA") or 0),
            "estdisponivel": float(d.get("ESTDISPONIVEL") or 0),
        })
    return out

# ---------- DETALHE 1 PRODUTO + ESTOQUE ----------
def obter_produto_com_estoque(idproduto: int, empresa: str | int):
    idproduto = int(idproduto)
    empresa = int(empresa)

    sql_p = """
        SELECT
            P.IDPRODUTO,
            TRIM(P.DESCRICAO) AS DESCRICAO,
            TRIM(P.CODBARRAS) AS CODBARRAS,
            P.PRECOVENDA
        FROM TESTPRODUTO P
        WHERE P.IDPRODUTO = CAST(? AS INTEGER)
    """
    # LEITURA DO ESTOQUE: trazer apenas IDALMOX = 1
    sql_e = """
        SELECT COALESCE(E.ESTDISPONIVEL, 0)
        FROM TESTPRODUTOESTOQUE E
        WHERE E.EMPRESA = CAST(? AS INTEGER)
          AND E.IDALMOX = 1
          AND E.IDPRODUTOPRINCIPAL = CAST(? AS INTEGER)
    """

    with fb_connect() as con:
        cur = con.cursor()
        cur.execute(sql_p, (idproduto,))
        rowp = cur.fetchone()
        if not rowp:
            cur.close()
            return None
        cols = [c[0].strip().upper() for c in cur.description]
        prod = dict(zip(cols, rowp))

        cur.execute(sql_e, (empresa, idproduto))
        rowe = cur.fetchone()
        est = float(rowe[0]) if rowe and rowe[0] is not None else 0.0
        cur.close()

    return {
        "idproduto": prod.get("IDPRODUTO"),
        "descricao": (prod.get("DESCRICAO") or "").strip(),
        "codbarras": (prod.get("CODBARRAS") or "").strip(),
        "precovenda": float(prod.get("PRECOVENDA") or 0),
        "empresa": str(empresa),
        "estdisponivel": est,
    }

def criar_testinventario(empresa, idalmox: int | None = None, usuario_id: int | None = None, usuario_label: str | None = None, motivo: str | None = None):
    """
    Cria um TESTINVENTARIO e retorna o IDINVENTARIO criado (inteiro).
    Usa heurísticas para preencher colunas obrigatórias (mesma lógica que já existe em ajustar_estoque).
    """
    import re
    if idalmox is None:
        idalmox = 1
    try:
        empresa = int(empresa)
    except Exception:
        raise RuntimeError("empresa inválida")

    with fb_connect() as con:
        cur = con.cursor()
        try:
            # calcula novo IDINVENTARIO (MAX+1) por empresa
            cur.execute("SELECT COALESCE(MAX(IDINVENTARIO),0)+1 FROM TESTINVENTARIO WHERE EMPRESA = ?", (empresa,))
            row = cur.fetchone()
            next_invid = int(row[0]) if row and row[0] is not None else 1

            base_map = {
                'EMPRESA': empresa,
                'IDINVENTARIO': next_invid,
                'IDALMOX': int(idalmox),
                'TIPO': 'AJU',
                'SITUACAO': 'ABERTO',
                'USUARIO': usuario_label if usuario_label else (str(usuario_id) if usuario_id else 'API'),
                'OBS': motivo or 'Inventário gerado automaticamente (criado via API)'
            }
            if usuario_id:
                base_map['IDUSUARIO'] = int(usuario_id)

            def _insert_inv(cur, cols_map):
                cols = list(cols_map.keys())
                placeholders = []
                params = []
                for c in cols:
                    cu = c.upper()
                    v = cols_map[c]
                    if cu in ('EMPRESA', 'IDINVENTARIO', 'IDALMOX', 'IDUSUARIO'):
                        placeholders.append("CAST(? AS INTEGER)")
                        params.append(int(v))
                    else:
                        placeholders.append("?")
                        params.append(v)
                sql_ins = f"INSERT INTO TESTINVENTARIO ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                cur.execute(sql_ins, tuple(params))

            inserted = False
            extras = {}
            tries = 0
            max_tries = 8
            while not inserted and tries < max_tries:
                tries += 1
                try:
                    cols_map = dict(base_map)
                    cols_map.update(extras)
                    _insert_inv(cur, cols_map)
                    inserted = True
                except Exception as ie:
                    msgie = str(ie)
                    m = re.search(r'column\s+"[^"]+"\."(?P<col>\w+)"', msgie, re.IGNORECASE)
                    if not m:
                        m = re.search(r'\"(?P<col>[A-Z0-9_]+)\"', msgie)
                    if not m:
                        raise
                    colname = m.group('col').strip()
                    cu = colname.upper()
                    if cu.startswith('ID') or cu.endswith('ID'):
                        extras[colname] = 1
                    elif cu in ('TIPO', 'SITUACAO', 'USUARIO', 'OBS', 'REGISTROHORA', 'REGISTRODATA'):
                        extras[colname] = '' if cu != 'USUARIO' else (usuario_label or (str(usuario_id) if usuario_id else 'API'))
                    else:
                        extras[colname] = 0
            if not inserted:
                con.rollback()
                cur.close()
                raise RuntimeError("Não foi possível criar TESTINVENTARIO")

            con.commit()
            cur.close()
            return next_invid

        except Exception as e:
            try:
                con.rollback()
            except Exception:
                pass
            try:
                cur.close()
            except Exception:
                pass
            raise


def ajustar_lote_TESTPRODUTOESTOQUE(
    empresa,
    items,                    # lista de { "idproduto": int, "delta": Decimal|float, "motivo": str (opt) }
    idalmox: int | None = None,
    usuario_id: int | None = None,
    usuario_label: str | None = None,
    motivo_geral: str | None = None,
    max_retries=5, retry_delay=0.05
):
    """
    Cria um único TESTINVENTARIO e insere múltiplos movimentos (items).
    Retorna lista de saldos atualizados por item: [{idproduto, saldo}, ...]
    """
    from decimal import Decimal, InvalidOperation
    import time
    import re

    try:
        empresa = int(empresa)
    except Exception:
        raise RuntimeError("empresa inválida (inteiro esperado)")
    if idalmox is None:
        idalmox = 1
    else:
        idalmox = int(idalmox)

    if not isinstance(items, (list, tuple)) or len(items) == 0:
        raise RuntimeError("items inválido (esperado lista de ajustes)")

    # normalize deltas and idproduto
    normalized = []
    for it in items:
        try:
            pid = int(it.get('idproduto') or it.get('id') or it.get('produto'))
        except Exception:
            raise RuntimeError("idproduto inválido em um dos items")
        try:
            d = Decimal(str(it.get('delta') or it.get('qtd') or 0))
        except Exception:
            raise RuntimeError("delta inválido para produto %s" % pid)
        normalized.append({'idproduto': pid, 'delta': d, 'motivo': it.get('motivo')})

    attempt = 0
    last_exc = None

    while attempt < max_retries:
        attempt += 1
        with fb_connect() as con:
            cur = con.cursor()
            try:
                # resolve usuario_label se necessário
                if usuario_id and not usuario_label:
                    try:
                        cur.execute("SELECT COALESCE(NOME, USUARIO) FROM TGERUSUARIO WHERE IDUSUARIO = CAST(? AS INTEGER)", (int(usuario_id),))
                        rowu = cur.fetchone()
                        if rowu and rowu[0]:
                            usuario_label = str(rowu[0])
                    except Exception:
                        usuario_label = None

                # 1) criar um inventario (UMA vez)
                cur.execute("SELECT COALESCE(MAX(IDINVENTARIO),0)+1 FROM TESTINVENTARIO WHERE EMPRESA = ?", (empresa,))
                row = cur.fetchone()
                next_invid = int(row[0]) if row and row[0] is not None else 1

                base_map = {
                    'EMPRESA': empresa,
                    'IDINVENTARIO': next_invid,
                    'IDALMOX': idalmox,
                    'TIPO': 'AJU',
                    'SITUACAO': 'ABERTO',
                    'USUARIO': usuario_label if usuario_label else (str(usuario_id) if usuario_id else 'API'),
                    'OBS': motivo_geral or 'Inventário gerado automaticamente (lote)'
                }
                if usuario_id:
                    base_map['IDUSUARIO'] = int(usuario_id)

                def _insert_inv(cur, cols_map):
                    cols = list(cols_map.keys())
                    placeholders = []
                    params = []
                    for c in cols:
                        cu = c.upper()
                        v = cols_map[c]
                        if cu in ('EMPRESA', 'IDINVENTARIO', 'IDALMOX', 'IDUSUARIO'):
                            placeholders.append("CAST(? AS INTEGER)")
                            params.append(int(v))
                        else:
                            placeholders.append("?")
                            params.append(v)
                    sql_ins = f"INSERT INTO TESTINVENTARIO ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                    cur.execute(sql_ins, tuple(params))

                inserted = False
                extras = {}
                tries = 0
                max_tries = 8
                while not inserted and tries < max_tries:
                    tries += 1
                    try:
                        cols_map = dict(base_map)
                        cols_map.update(extras)
                        _insert_inv(cur, cols_map)
                        inserted = True
                    except Exception as ie:
                        msgie = str(ie)
                        m = re.search(r'column\s+"[^"]+"\."(?P<col>\w+)"', msgie, re.IGNORECASE)
                        if not m:
                            m = re.search(r'\"(?P<col>[A-Z0-9_]+)\"', msgie)
                        if not m:
                            raise
                        colname = m.group('col').strip()
                        cu = colname.upper()
                        if cu.startswith('ID') or cu.endswith('ID'):
                            extras[colname] = 1
                        elif cu in ('TIPO', 'SITUACAO', 'USUARIO', 'OBS', 'REGISTROHORA', 'REGISTRODATA'):
                            extras[colname] = '' if cu != 'USUARIO' else (usuario_label or (str(usuario_id) if usuario_id else 'API'))
                        else:
                            extras[colname] = 0
                if not inserted:
                    con.rollback()
                    cur.close()
                    raise RuntimeError("Não foi possível criar TESTINVENTARIO (pai) para o ajuste em lote.")

                idinventario = next_invid

                # 2) preparar base para inserir movimentos e inserir um a um
                # calculamos um next_idmov inicial e incrementamos localmente
                cur.execute("SELECT COALESCE(MAX(IDMOVIMENTO),0)+1 FROM TESTPRODUTOMOVIMENTO WHERE EMPRESA = ?", (empresa,))
                rowm = cur.fetchone()
                next_idmov = int(rowm[0]) if rowm and rowm[0] is not None else 1

                insert_sql = f"""
                    INSERT INTO TESTPRODUTOMOVIMENTO
                      (EMPRESA, IDMOVIMENTO, IDTIPOMOVIMENTO, IDPRODUTO, IDPRODUTOPRINCIPAL,
                       IDALMOX, IDINVENTARIO, QTDE, ESTDISPONIVEL, QTDEEMBALAGEM, MOVIMENTAESTOQUE, DESCRICAO
                      )
                    VALUES
                      (CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS INTEGER),
                       CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS NUMERIC(18,4)), CAST(? AS NUMERIC(18,4)), CAST(? AS NUMERIC(18,4)), ?, ?)
                """

                results = []
                idtipomov = 6
                for it in normalized:
                    pid = it['idproduto']
                    delta = float(it['delta'])
                    mot = it.get('motivo') or motivo_geral

                    # pegar descricao do produto
                    cur.execute("SELECT TRIM(DESCRICAO) FROM TESTPRODUTO WHERE IDPRODUTO = CAST(? AS INTEGER)", (pid,))
                    rr = cur.fetchone()
                    prod_name = (rr[0] or '').strip() if rr and rr[0] else ''
                    descricao = (mot or prod_name or 'AJUSTE')[:250]

                    params = [
                        empresa, next_idmov, idtipomov, pid, pid,
                        idalmox, idinventario, delta, delta, 1.0, '1', descricao
                    ]
                    try:
                        cur.execute(insert_sql, tuple(params))
                    except Exception as ie:
                        # se conflito de PK, recalcular e tentar novamente
                        msgie = str(ie).upper()
                        if 'UNIQUE' in msgie or 'CONSTRAINT' in msgie or '-803' in msgie or 'DUPLICAT' in msgie:
                            cur.execute("SELECT COALESCE(MAX(IDMOVIMENTO),0)+1 FROM TESTPRODUTOMOVIMENTO WHERE EMPRESA = ?", (empresa,))
                            row2 = cur.fetchone()
                            next_idmov = int(row2[0]) if row2 and row2[0] is not None else next_idmov + 1
                            con.rollback()
                            cur.close()
                            raise RuntimeError("Conflito ao inserir movimento em lote; tente novamente.")
                        else:
                            raise

                    # incrementar idmov para próximo item
                    next_idmov += 1

                    # após inserir, ler saldo para este produto
                    cur.execute("SELECT COALESCE(ESTDISPONIVEL,0) FROM TESTPRODUTOESTOQUE WHERE EMPRESA = CAST(? AS INTEGER) AND IDPRODUTOPRINCIPAL = CAST(? AS INTEGER)",
                                (empresa, pid))
                    rb = cur.fetchone()
                    saldo = float(rb[0]) if rb and rb[0] is not None else 0.0
                    results.append({'idproduto': pid, 'saldo': saldo})

                # commit final e retornar saldos
                con.commit()
                cur.close()
                return results

            except Exception as e:
                try:
                    con.rollback()
                except Exception:
                    pass
                try:
                    cur.close()
                except Exception:
                    pass
                last_exc = e
                msg = str(e).upper()
                if any(k in msg for k in ("DEAD", "LOCK", "TIMEOUT", "CONFLICT")):
                    time.sleep(retry_delay * attempt)
                    continue
                raise RuntimeError(f"Erro no ajuste em lote: {e}")

    raise RuntimeError(f"Falha ao ajustar estoque em lote: {last_exc}")
