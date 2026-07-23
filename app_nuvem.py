import streamlit as st
import pandas as pd
from datetime import datetime
import re
from streamlit_gsheets import GSheetsConnection

# Configuração da Página
st.set_page_config(page_title="Banco de Questões - APP", layout="wide")

# --- CONFIGURAÇÕES E CONSTANTES ---
LISTA_MATERIAS = ["", "Direito Penal", "Processual Penal", "Estatística", "Economia"]
LISTA_BANCAS = ["", "CESPE", "FGV", "FCC", "VUNESP", "FADESP", "CESGRANRIO", "Outra"]
OUTRO_ASSUNTO = "➕ Outro assunto (não está na lista)"

# Função de validação de Ano
def validar_ano(ano_str):
    ano_str = str(ano_str).strip()
    if not ano_str:
        return True
    return bool(re.match(r"^20\d{2}$", ano_str))

# --- CONEXÃO COM GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados_nuvem(nome_aba, colunas_padrao):
    try:
        df = conn.read(worksheet=nome_aba, ttl=0)
        df = df.dropna(how="all")

        # A mágica contra o TypeError
        df = df.astype(str)
        df = df.replace('nan', '').replace('None', '')

        for col in ['Código', 'Ano']:
            if col in df.columns:
                df[col] = df[col].str.replace(r'\.0$', '', regex=True).str.strip()

        return df
    except Exception:
        return pd.DataFrame(columns=colunas_padrao)

def guardar_dados_nuvem(df, nome_aba):
    conn.update(worksheet=nome_aba, data=df)

# Colunas padrão
COL_BANCO = ['Código', 'Matéria', 'Ano', 'Banca', 'Assunto', 'Comentário', 'Última Modificação']
COL_EXC = ['Código', 'Matéria', 'Banca', 'Assunto', 'Data Exclusão']
COL_ASSUNTOS = ['Matéria', 'Assunto']

# --- VALIDAÇÃO DE ASSUNTO (lista controlada por Matéria, aba "Assuntos") ---
def carregar_assuntos_nuvem():
    return carregar_dados_nuvem("Assuntos", COL_ASSUNTOS)

def registrar_novo_assunto(materia, assunto):
    """Adiciona um novo Assunto à lista de validação, se ainda não existir para aquela Matéria."""
    if not materia or not assunto:
        return
    df_a = carregar_assuntos_nuvem()
    ja_existe = ((df_a['Matéria'] == materia) & (df_a['Assunto'] == assunto)).any()
    if not ja_existe:
        novo = pd.DataFrame([{'Matéria': materia, 'Assunto': assunto}])
        df_a = pd.concat([df_a, novo], ignore_index=True)
        guardar_dados_nuvem(df_a, "Assuntos")

def montar_opcoes_assunto(materia, df_assuntos):
    """Monta a lista de opções de Assunto para a Matéria escolhida. Se não houver
    nenhum assunto cadastrado para a Matéria, a lista fica só com o Outro (texto livre)."""
    if not materia:
        return ["", OUTRO_ASSUNTO]
    opcoes_mat = sorted(
        df_assuntos[df_assuntos['Matéria'] == materia]['Assunto']
        .dropna().loc[lambda s: s.str.strip() != ''].unique().tolist()
    )
    return [""] + opcoes_mat + [OUTRO_ASSUNTO]

def resolver_assunto_final(assunto_selecionado, assunto_digitado):
    """Dado o que foi escolhido no selectbox e o que foi digitado no campo 'Outro',
    devolve o valor final de Assunto a ser salvo."""
    if assunto_selecionado == OUTRO_ASSUNTO:
        return assunto_digitado.strip()
    return assunto_selecionado

# Carregamento inicial
df = carregar_dados_nuvem("Banco", COL_BANCO)
df_assuntos_global = carregar_assuntos_nuvem()

# --- INTERFACE ---
st.title("📚 Banco de Questões - APP")

aba_pesquisa, aba_add, aba_rel, aba_import = st.tabs([
    "🔍 Pesquisar e Gerir",
    "➕ Adicionar Nova",
    "📊 Relatórios e Dashboard",
    "⚙️ Importar CSV Local"
])

# --- 1. ABA PESQUISAR E GERIR ---
with aba_pesquisa:
    search = st.text_input("Filtrar questões (Código, Assunto, Banca...):")
    df_filt = df.copy()
    if search:
        mask = df_filt.apply(lambda r: r.astype(str).str.contains(search, case=False).any(), axis=1)
        df_filt = df_filt[mask]

    selecao = st.dataframe(
        df_filt[['Código', 'Matéria', 'Ano', 'Banca', 'Assunto', 'Última Modificação']],
        use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
    )

    if len(selecao.selection.rows) > 0:
        idx_selecionado = df_filt.index[selecao.selection.rows[0]]
        row = df.loc[idx_selecionado]
        st.markdown(f"### 📝 Editando Questão: {row['Código']}")

        # --- Matéria e Assunto ficam FORA do form para serem reativos:
        # trocar a Matéria precisa atualizar na hora a lista de Assuntos disponível.
        m_at = str(row.get('Matéria', '')).strip()
        idx_m = LISTA_MATERIAS.index(m_at) if m_at in LISTA_MATERIAS else 0
        e_mat = st.selectbox("Matéria", LISTA_MATERIAS, index=idx_m, key=f"edit_mat_{row['Código']}")

        a_at = str(row.get('Assunto', '')).strip()
        opcoes_assunto_edit = montar_opcoes_assunto(e_mat, df_assuntos_global)
        idx_a = opcoes_assunto_edit.index(a_at) if a_at in opcoes_assunto_edit else 0
        e_assu_sel = st.selectbox(
            "Assunto (pesquise ou selecione)", opcoes_assunto_edit, index=idx_a,
            key=f"edit_assu_sel_{row['Código']}"
        )
        e_assu_novo = ""
        if e_assu_sel == OUTRO_ASSUNTO:
            valor_inicial = a_at if a_at not in opcoes_assunto_edit else ""
            e_assu_novo = st.text_input(
                "Digite o novo Assunto:", value=valor_inicial, key=f"edit_assu_novo_{row['Código']}"
            )

        with st.form("form_edicao"):
            c2, c3 = st.columns(2)

            # Ano
            e_ano = c2.text_input("Ano (20XX ou vazio)", value=str(row.get('Ano', '')))

            # Banca
            b_at = str(row.get('Banca', '')).strip()
            idx_b = LISTA_BANCAS.index(b_at) if b_at in LISTA_BANCAS else 0
            e_banca = c3.selectbox("Banca", LISTA_BANCAS, index=idx_b)

            # Comentário
            e_coment = st.text_area("Comentário / Bizu", value=str(row.get('Comentário', '')), height=250)

            col_b1, col_b2, _ = st.columns([1, 1, 2])
            btn_save = col_b1.form_submit_button("💾 Salvar Alterações")
            btn_del = col_b2.form_submit_button("🗑️ Excluir Questão", type="primary")

            if btn_save:
                e_assu = resolver_assunto_final(e_assu_sel, e_assu_novo)
                # Regra: Comentário é obrigatório. Se a Matéria for Direito Penal
                # (que já tem lista curada de Assuntos), Assunto também passa a ser obrigatório.
                if not e_coment.strip():
                    st.error("⚠️ O campo Comentário não pode ficar vazio!")
                elif e_assu_sel == OUTRO_ASSUNTO and not e_assu:
                    st.error("⚠️ Você marcou 'Outro assunto' mas não digitou o novo assunto.")
                elif e_mat == "Direito Penal" and not e_assu:
                    st.error("⚠️ Assunto é obrigatório para questões de Direito Penal.")
                elif not validar_ano(e_ano):
                    st.error("⚠️ Erro: Ano inválido. Deixe em branco ou use o formato 20XX.")
                else:
                    df.at[idx_selecionado, 'Matéria'] = e_mat
                    df.at[idx_selecionado, 'Ano'] = e_ano
                    df.at[idx_selecionado, 'Banca'] = e_banca
                    df.at[idx_selecionado, 'Assunto'] = e_assu
                    df.at[idx_selecionado, 'Comentário'] = e_coment
                    df.at[idx_selecionado, 'Última Modificação'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    guardar_dados_nuvem(df, "Banco")
                    if e_assu_sel == OUTRO_ASSUNTO:
                        registrar_novo_assunto(e_mat, e_assu)
                    st.success("Alterações salvas!")
                    st.rerun()

            if btn_del:
                e_assu = resolver_assunto_final(e_assu_sel, e_assu_novo)
                df_exc = carregar_dados_nuvem("Exclusoes", COL_EXC)
                nova_exc = pd.DataFrame([{'Código': row['Código'], 'Matéria': e_mat, 'Banca': e_banca, 'Assunto': e_assu, 'Data Exclusão': datetime.now().strftime("%d/%m/%Y %H:%M")}])
                guardar_dados_nuvem(pd.concat([df_exc, nova_exc]), "Exclusoes")
                df = df.drop(idx_selecionado)
                guardar_dados_nuvem(df, "Banco")
                st.warning("Questão excluída com sucesso!")
                st.rerun()

# --- 2. ABA ADICIONAR NOVA ---
with aba_add:
    st.subheader("📝 Cadastrar Novo Bizu")

    # Matéria e Assunto ficam FORA do form pelo mesmo motivo da aba de edição.
    c1, c2 = st.columns(2)
    n_mat = c1.selectbox("Matéria", LISTA_MATERIAS, key="add_materia")
    opcoes_assunto_add = montar_opcoes_assunto(n_mat, df_assuntos_global)
    n_ass_sel = c2.selectbox("Assunto (pesquise ou selecione)", opcoes_assunto_add, key="add_assunto_sel")
    n_ass_novo = ""
    if n_ass_sel == OUTRO_ASSUNTO:
        n_ass_novo = st.text_input("Digite o novo Assunto:", key="add_assunto_novo")

    with st.form("add_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        n_cod = c1.text_input("Código (Chave Única)*")
        n_ano = c2.text_input("Ano (Ex: 2024 ou vazio)")
        n_ban = c3.selectbox("Banca", LISTA_BANCAS)
        n_com = st.text_area("Comentário / Bizu*", height=200)

        st.caption("* Campos obrigatórios. Assunto também é obrigatório para Direito Penal.")

        if st.form_submit_button("🚀 Adicionar ao Banco Cloud"):
            n_ass = resolver_assunto_final(n_ass_sel, n_ass_novo)
            if not n_cod.strip() or not n_com.strip():
                st.error("⚠️ Os campos 'Código' e 'Comentário' são obrigatórios!")
            elif n_ass_sel == OUTRO_ASSUNTO and not n_ass:
                st.error("⚠️ Você marcou 'Outro assunto' mas não digitou o novo assunto.")
            elif n_mat == "Direito Penal" and not n_ass:
                st.error("⚠️ Assunto é obrigatório para questões de Direito Penal.")
            elif n_cod.strip() in df['Código'].values:
                st.error(f"⚠️ Ação Bloqueada: O código '{n_cod}' já existe no banco!")
            elif not validar_ano(n_ano):
                st.error("⚠️ Erro: Ano inválido. Deixe em branco ou use o formato 20XX.")
            else:
                nova = pd.DataFrame([{
                    'Código': n_cod.strip(), 'Matéria': n_mat, 'Ano': n_ano,
                    'Banca': n_ban, 'Assunto': n_ass, 'Comentário': n_com,
                    'Última Modificação': datetime.now().strftime("%d/%m/%Y %H:%M")
                }])
                df = pd.concat([df, nova], ignore_index=True)
                guardar_dados_nuvem(df, "Banco")
                if n_ass_sel == OUTRO_ASSUNTO:
                    registrar_novo_assunto(n_mat, n_ass)
                st.success("Questão adicionada com sucesso!")
                st.rerun()

# --- 3. ABA RELATÓRIOS E DASHBOARD ---
with aba_rel:
    st.subheader("📊 Dashboard de Performance")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Geral", len(df))
    m2.metric("Direito Penal", len(df[df['Matéria'] == "Direito Penal"]))

    # Contagem ignorando campos vazios
    bancas_preenchidas = df[df['Banca'].astype(str).str.strip() != '']['Banca'].nunique()
    anos_preenchidos = df[df['Ano'].astype(str).str.strip() != '']['Ano'].nunique()

    m3.metric("Bancas Registadas", bancas_preenchidas)
    m4.metric("Anos Registados", anos_preenchidos)

    # --- Verificação de integridade: questões de Direito Penal com campo obrigatório faltando ---
    dpen = df[df['Matéria'] == "Direito Penal"]
    if not dpen.empty:
        faltantes = dpen[
            (dpen['Ano'].astype(str).str.strip() == '') |
            (dpen['Banca'].astype(str).str.strip() == '') |
            (dpen['Assunto'].astype(str).str.strip() == '')
        ]
        if len(faltantes) > 0:
            st.warning(f"⚠️ {len(faltantes)} questão(ões) de Direito Penal com Ano, Banca ou Assunto em branco — precisam de higienização.")
            with st.expander("Ver quais"):
                st.dataframe(faltantes[['Código', 'Ano', 'Banca', 'Assunto']], use_container_width=True, hide_index=True)
        else:
            st.success("✅ Nenhuma questão de Direito Penal com campo obrigatório faltando.")

    # --- Backup rápido: baixar o Banco inteiro em CSV ---
    st.download_button(
        "⬇️ Baixar backup do Banco (CSV)",
        data=df.to_csv(index=False).encode('utf-8'),
        file_name=f"backup_banco_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv"
    )

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.write("**Questões por Matéria**")
        mat_validas = df[df['Matéria'].astype(str).str.strip() != '']
        if not mat_validas.empty:
            st.bar_chart(mat_validas['Matéria'].value_counts())
        else:
            st.info("Nenhuma matéria preenchida.")

    with col_g2:
        st.write("**Questões por Banca**")
        bancas_validas = df[df['Banca'].astype(str).str.strip() != '']
        if not bancas_validas.empty:
            st.bar_chart(bancas_validas['Banca'].value_counts())
        else:
            st.info("Nenhuma banca preenchida.")

    st.markdown("---")

    st.write("#### 🎯 Top 5 Assuntos de Cada Matéria")
    # Filtra a lista de matérias para ignorar o campo vazio na hora de gerar o relatório
    materias_reais = [m for m in LISTA_MATERIAS if m.strip() != ""]
    for mat in materias_reais:
        # Filtra os assuntos da matéria, ignorando os vazios
        assuntos = df[(df['Matéria'] == mat) & (df['Assunto'].astype(str).str.strip() != '')]['Assunto'].value_counts().head(5)
        if not assuntos.empty:
            with st.expander(f"Top Assuntos: {mat}"):
                st.table(assuntos.reset_index().rename(columns={'count':'Qtd', 'Assunto': 'Descrição'}))

    st.markdown("---")
    col_h1, col_h2 = st.columns(2)

    with col_h1:
        st.write("#### 🗑️ 5 Últimas Exclusões")
        df_exc_hist = carregar_dados_nuvem("Exclusoes", COL_EXC)
        if not df_exc_hist.empty:
            st.dataframe(df_exc_hist.tail(5), use_container_width=True, hide_index=True)

    with col_h2:
        st.write("#### 🕒 5 Últimas Alterações/Adições")
        if not df.empty:
            df_recent = df.copy()
            df_recent['dt_temp'] = pd.to_datetime(df_recent['Última Modificação'], format="%d/%m/%Y %H:%M", errors='coerce')
            st.dataframe(df_recent.sort_values('dt_temp', ascending=False).head(5)[['Código', 'Assunto', 'Última Modificação']], use_container_width=True, hide_index=True)

# --- 4. ABA IMPORTAR (MANTIDA) ---
with aba_import:
    st.subheader("📥 Importar CSV Local")
    st.write("Carregue seu arquivo antigo para o Google Sheets de uma só vez.")

    upload = st.file_uploader("Escolhe o teu ficheiro CSV antigo", type="csv")
    mat_import = st.selectbox("A que matéria pertencem estas questões?", LISTA_MATERIAS)

    if upload and st.button("Iniciar Importação para a Nuvem"):
        df_old = pd.read_csv(upload, dtype={'Código': str})
        df_old['Código'] = df_old['Código'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        novas_questoes = []
        for _, row in df_old.iterrows():
            if row['Código'] not in df['Código'].values:
                novas_questoes.append({
                    'Código': row['Código'],
                    'Matéria': mat_import,
                    'Ano': row.get('Ano', ''),
                    'Banca': row.get('Banca', ''),
                    'Assunto': row.get('Assunto', ''),
                    'Comentário': row.get('Comentário', ''),
                    'Última Modificação': datetime.now().strftime("%d/%m/%Y %H:%M")
                })

        if novas_questoes:
            df_final = pd.concat([df, pd.DataFrame(novas_questoes)], ignore_index=True)
            guardar_dados_nuvem(df_final, "Banco")
            st.success(f"Sucesso! {len(novas_questoes)} questões migradas!")
            st.rerun()
        else:
            st.info("Todas as questões do ficheiro já existem no banco.")
