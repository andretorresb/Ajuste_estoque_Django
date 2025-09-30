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
    """
    Tenta descobrir se `stored` é a concatenação de N segmentos, um por caractere
    de `plain`. Ex.: plain='1425', stored pode ser 'X05E03C01' (segmentos variados).
    Testa todas as formas de separar `stored` em len(plain) partes (composições)
    e verifica se existe um mapeamento consistente char->segmento (injetivo).
    Retorna dict mapping se OK, ou None.
    """
    stored = '' if stored is None else str(stored)
    plain = '' if plain is None else str(plain)
    L = len(stored)
    N = len(plain)
    if N == 0 or L == 0 or N > L:
        return None
    # se L == N pode ser mapeamento 1:1 char->char (exato)
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

    # gera todas as composições de L em N partes: escolhe N-1 índices de corte em range(1,L)
    for cuts in itertools.combinations(range(1, L), N-1):
        parts = []
        last = 0
        for c in cuts:
            parts.append(stored[last:c])
            last = c
        parts.append(stored[last:])
        # verifica consistência 1-to-1: cada caractere de plain deve mapear ao mesmo segmento
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
    """
    Verifica credenciais na tabela TGERUSUARIO.
    Tenta múltiplas heurísticas:
     - busca usuário ativo por USUARIO ou IDUSUARIO
     - compara plain text
     - compara MD5/SHA1/SHA256 hex digest
     - compara base64 (padrão e urlsafe)
     - compara reversed string
     - tenta mapeamento por segmentos (heurística para esquemas 'cada char -> substring fixa')
    Retorna {'ok': True, 'user': {...}} ou {'ok': False, 'reason': '...'}
    """
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

    # detectar campo de senha (heurística)
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
        # não achamos coluna de senha -> não podemos validar
        return {'ok': False, 'reason': 'no_password_field', 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    # normaliza stored para string
    if isinstance(stored_val, bytes):
        try:
            stored_str = stored_val.decode(CHARSET)
        except Exception:
            stored_str = stored_val.decode(errors='ignore')
    else:
        stored_str = str(stored_val)

    # 1) plain text exact
    if password == stored_str:
        return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    # 2) hashes hex (md5/sha1/sha256)
    pwb = password.encode('utf-8')
    for algo in ('md5','sha1','sha256'):
        h = getattr(hashlib, algo)(pwb).hexdigest()
        if h == stored_str:
            return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    # 3) base64 encodings
    try:
        b64 = base64.b64encode(pwb).decode('ascii')
        if b64 == stored_str:
            return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}
        b64u = base64.urlsafe_b64encode(pwb).decode('ascii')
        if b64u == stored_str:
            return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}
    except Exception:
        pass

    # 4) reversed password
    if password[::-1] == stored_str:
        return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}}

    # 5) Try segment mapping: is `stored_str` concatenation of segments that map to each char of password?
    seg_map = _try_segment_mapping(stored_str, password)
    if seg_map:
        # sucesso pela heurística de mapeamento por segmentos
        return {'ok': True, 'user': {'id': idusuario, 'username': username, 'nome': nome}, 'mapping': seg_map}

    # 6) fallback: nenhuma heurística bateu
    return {'ok': False, 'reason': 'invalid_password'}


# ------------ Busca Usuarios ----------
def buscar_usuarios_TGERUSUARIO():
    """
    Retorna lista de usuários ativos da tabela TGERUSUARIO.
    Cada item: { "id": <idusuario>, "username": <usuario>, "nome": <nome>, "ativo": <S/N> }
    """
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
    """
    Busca em TESTPRODUTO por descrição (LIKE) ou código de barras (match exato).
    Retorna: idproduto, descricao, codbarras, precovenda
    """
    q_raw = (query or "").strip()
    q_like = f"%{q_raw.upper()}%" if q_raw else None

    sql = """
        SELECT
            P.IDPRODUTO,
            TRIM(P.DESCRICAO) AS DESCRICAO,
            TRIM(P.CODBARRAS) AS CODBARRAS,
            P.PRECOVENDA
        FROM TESTPRODUTO P
        WHERE 1 = 1
    """
    params = []

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
        })
    return out


# ---------- DETALHE 1 PRODUTO + ESTOQUE ----------
def obter_produto_com_estoque(idproduto: int, empresa: str | int):
    """
    Busca dados do produto em TESTPRODUTO e o estoque disponível em TESTPRODUTOESTOQUE
    assumindo que TESTPRODUTOESTOQUE.EMPRESA = empresa e IDPRODUTOPRINCIPAL = idproduto.
    """
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
    sql_e = """
        SELECT COALESCE(E.ESTDISPONIVEL, 0)
        FROM TESTPRODUTOESTOQUE E
        WHERE E.EMPRESA = CAST(? AS INTEGER) AND E.IDPRODUTOPRINCIPAL = CAST(? AS INTEGER)
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


def ajustar_estoque_TESTPRODUTOESTOQUE(
    empresa, idproduto, delta,
    bloquear_negativo=True,
    qty_col='ESTDISPONIVEL',
    id_col='IDPRODUTOPRINCIPAL',
    emp_col='EMPRESA',
    idalmox: int | None = None,
    idinventario: int | None = None,
    usuario_id: int | None = None,
    usuario_label: str | None = None,
    motivo: str | None = None,
    max_retries=5, retry_delay=0.05
):
    """
    SEMPRE cria um novo TESTINVENTARIO (pai) e insere um movimento em
    TESTPRODUTOMOVIMENTO. Agora grava o nome do usuário no campo USUARIO
    e o id numérico em IDUSUARIO quando disponível.
    Retorna o novo saldo (float).
    """
    from decimal import Decimal, InvalidOperation
    import re
    import time

    # normaliza tipos básicos
    try:
        empresa = int(empresa)
    except Exception:
        raise RuntimeError("empresa inválida (inteiro esperado)")
    try:
        idproduto = int(idproduto)
    except Exception:
        raise RuntimeError("idproduto inválido (inteiro esperado)")
    try:
        delta = Decimal(str(delta))
    except (InvalidOperation, Exception):
        raise RuntimeError("delta inválido (número esperado)")

    if idalmox is None:
        idalmox = 1
    else:
        try:
            idalmox = int(idalmox)
        except Exception:
            raise RuntimeError("idalmox inválido (inteiro esperado)")

    t_estoque = 'TESTPRODUTOESTOQUE'
    mov_table = 'TESTPRODUTOMOVIMENTO'
    inv_table = 'TESTINVENTARIO'
    qty_col = qty_col.upper()
    id_col = id_col.upper()
    emp_col = emp_col.upper()

    attempt = 0
    last_exc = None

    while attempt < max_retries:
        attempt += 1
        with fb_connect() as con:
            cur = con.cursor()
            try:
                # Se o front enviou só usuario_id mas não o label, tenta buscar o nome em TGERUSUARIO
                if usuario_id and not usuario_label:
                    try:
                        cur.execute("SELECT COALESCE(NOME, USUARIO) FROM TGERUSUARIO WHERE IDUSUARIO = CAST(? AS INTEGER)", (int(usuario_id),))
                        rowu = cur.fetchone()
                        if rowu and rowu[0]:
                            usuario_label = str(rowu[0])
                    except Exception:
                        usuario_label = None

                # ---------- 1) CRIA um novo TESTINVENTARIO SEMPRE ----------
                cur.execute(f"SELECT COALESCE(MAX(IDINVENTARIO),0)+1 FROM {inv_table} WHERE EMPRESA = ?", (empresa,))
                row = cur.fetchone()
                next_invid = int(row[0]) if row and row[0] is not None else 1

                # base para insert - agora colocamos USUARIO (varchar) com label e IDUSUARIO com id numérico (quando houver)
                base_map = {
                    'EMPRESA': empresa,
                    'IDINVENTARIO': next_invid,
                    'IDALMOX': idalmox,
                    'TIPO': 'AJU',
                    'SITUACAO': 'ABERTO',
                    'USUARIO': usuario_label if usuario_label else (str(usuario_id) if usuario_id else 'API'),
                    'OBS': motivo or 'Inventário gerado automaticamente para ajuste'
                }
                # se usuário numérico foi informado, preenche também campo IDUSUARIO (coluna FK)
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
                    sql_ins = f"INSERT INTO {inv_table} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
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
                    raise RuntimeError("Não foi possível criar TESTINVENTARIO (pai) para o ajuste.")
                idinventario = next_invid

                # ---------- 2) calcula IDMOVIMENTO e insere o movimento ----------
                cur.execute(f"SELECT COALESCE(MAX(IDMOVIMENTO),0)+1 FROM {mov_table} WHERE EMPRESA = ?", (empresa,))
                rowm = cur.fetchone()
                next_idmov = int(rowm[0]) if rowm and rowm[0] is not None else 1

                idtipomov = 6  # 6 = Inventario (AJUSTE)
                descricao = (motivo or 'AJUSTE')[:250]

                insert_sql = f"""
                    INSERT INTO {mov_table}
                      (EMPRESA, IDMOVIMENTO, IDTIPOMOVIMENTO, IDPRODUTO, IDPRODUTOPRINCIPAL,
                       IDALMOX, IDINVENTARIO, QTDE, ESTDISPONIVEL, QTDEEMBALAGEM, MOVIMENTAESTOQUE, DESCRICAO
                      )
                    VALUES
                      (CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS INTEGER),
                       CAST(? AS INTEGER), CAST(? AS INTEGER), CAST(? AS NUMERIC(18,4)), CAST(? AS NUMERIC(18,4)), CAST(? AS NUMERIC(18,4)), ?, ?)
                """

                params = [
                    empresa, next_idmov, idtipomov, idproduto, idproduto,
                    idalmox, idinventario, float(delta), float(delta), 1.0, '1', descricao
                ]

                try:
                    cur.execute(insert_sql, tuple(params))
                except Exception as ie:
                    msgie = str(ie).upper()
                    if 'UNIQUE' in msgie or 'CONSTRAINT' in msgie or '-803' in msgie or 'DUPLICAT' in msgie:
                        cur.execute(f"SELECT COALESCE(MAX(IDMOVIMENTO),0)+1 FROM {mov_table} WHERE EMPRESA = ?", (empresa,))
                        row2 = cur.fetchone()
                        next_idmov = int(row2[0]) if row2 and row2[0] is not None else next_idmov + 1
                        con.rollback()
                        cur.close()
                        time.sleep(retry_delay * attempt)
                        continue
                    else:
                        raise

                # ---------- 3) leitura do saldo atualizado ----------
                cur.execute(
                    f"SELECT COALESCE({qty_col},0) FROM {t_estoque} WHERE {emp_col} = CAST(? AS INTEGER) AND {id_col} = CAST(? AS INTEGER)",
                    (empresa, idproduto)
                )
                rowbal = cur.fetchone()
                if not rowbal:
                    con.commit()
                    cur.close()
                    raise RuntimeError("Nenhuma linha atualizada — produto/empresa não encontrados após inserção do movimento.")
                novo = float(rowbal[0] or 0.0)

                con.commit()
                cur.close()
                return novo

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
                raise RuntimeError(f"Erro no ajuste: {e}")

    raise RuntimeError(f"Falha ao ajustar estoque: {last_exc}")
