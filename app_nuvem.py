import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Gestor Bizu Cloud Pro", layout="wide")

LISTA_MATERIAS = ["Direito Penal", "Estatística", "Processual Penal", "Economia"]

# --- CONEXÃO COM O GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados_nuvem(nome_aba, colunas_padrao):
    try:
        # ttl=0 garante que não usamos cache e vemos os dados em tempo real
        df = conn.read(worksheet=nome_aba, ttl=0)
        df = df.dropna(how="all")
        
        # LIMPEZA DE FORMATO (Zerar o .0 e os NaNs)
        for col in ['Código', 'Ano']:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', '')
        return df
    except:
        return pd.DataFrame(columns=colunas_padrao)

def guardar_dados_nuvem(df, nome_aba):
    conn.update(worksheet=nome_aba, data=df)

# Colunas padrão
COLUNAS_BANCO = ['Código', 'Matéria', 'Ano', 'Banca', 'Assunto', 'Comentário', 'Última Modificação']
COLUNAS_EXCLUSOES = ['Código', 'Matéria', 'Banca', 'Assunto', 'Data Exclusão']

df = carregar_dados_nuvem("Banco", COLUNAS_BANCO)

# --- INTERFACE ---
st.title("☁️ Painel de Gestão de Bizus")

aba_pesquisa, aba_add, aba_rel, aba_config = st.tabs([
    "🔍 Pesquisar e Gerir", 
    "➕ Adicionar Nova",
    "📊 Relatórios",
    "⚙️ Configurações / Importar"
])

# --- ABA PESQUISAR E GERIR ---
with aba_pesquisa:
    search = st.text_input("Filtrar na tabela:")
    df_visualizacao = df.copy()
    if search:
        mask = df_visualizacao.apply(lambda r: r.astype(str).str.contains(search, case=False).any(), axis=1)
        df_visualizacao = df_visualizacao[mask]

    selecao = st.dataframe(
        df_visualizacao[['Código', 'Matéria', 'Ano', 'Banca', 'Assunto', 'Última Modificação']], 
        use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row"
    )

    if len(selecao.selection.rows) > 0:
        idx_selecionado = df_visualizacao.index[selecao.selection.rows[0]]
        row = df.loc[idx_selecionado]
        st.markdown("---")
        with st.form("form_gestao"):
            c1, c2, c3, c4 = st.columns(4)
            m_at = str(row.get('Matéria', ''))
            idx_m = LISTA_MATERIAS.index(m_at) if m_at in LISTA_MATERIAS else 0
            e_mat = c1.selectbox("Matéria", LISTA_MATERIAS, index=idx_m)
            e_ano = c2.text_input("Ano", value=str(row.get('Ano', '')))
            e_banca = c3.text_input("Banca", value=str(row.get('Banca', '')))
            e_assu = c4.text_input("Assunto", value=str(row.get('Assunto', '')))
            e_coment = st.text_area("Comentário", value=str(row.get('Comentário', '')), height=300)
            
            if st.form_submit_button("💾 Salvar Alterações"):
                df.at[idx_selecionado, 'Matéria'] = e_mat
                df.at[idx_selecionado, 'Ano'] = e_ano
                df.at[idx_selecionado, 'Banca'] = e_banca
                df.at[idx_selecionado, 'Assunto'] = e_assu
                df.at[idx_selecionado, 'Comentário'] = e_coment
                df.at[idx_selecionado, 'Última Modificação'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                guardar_dados_nuvem(df, "Banco")
                st.success("Atualizado!")
                st.rerun()

# --- ABA ADICIONAR ---
with aba_add:
    with st.form("new_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        n_cod = c1.text_input("Código")
        n_mat = c2.selectbox("Matéria", LISTA_MATERIAS)
        n_ano = c3.text_input("Ano")
        n_com = st.text_area("Comentário")
        if st.form_submit_button("Salvar na Nuvem"):
            if n_cod.strip() in df['Código'].values:
                st.error("Questão já existe!")
            else:
                nova = pd.DataFrame([{'Código': n_cod, 'Matéria': n_mat, 'Ano': n_ano, 'Comentário': n_com, 'Última Modificação': datetime.now().strftime("%d/%m/%Y %H:%M")}])
                df = pd.concat([df, nova], ignore_index=True)
                guardar_dados_nuvem(df, "Banco")
                st.success("Adicionada!")
                st.rerun()

# --- ABA RELATÓRIOS ---
with aba_rel:
    st.metric("Total de Questões", len(df))
    if not df.empty:
        st.write("#### Por Matéria")
        st.bar_chart(df['Matéria'].value_counts())

# --- ABA CONFIGURAÇÕES / IMPORTAR (A SOLUÇÃO PARA O BANCO ANTIGO) ---
with aba_config:
    st.subheader("📥 Importar Banco de Dados Local (CSV)")
    st.write("Usa esta ferramenta para carregar o teu ficheiro `banco_de_questoes.csv` antigo para o Google Sheets.")
    
    upload = st.file_uploader("Escolhe o teu ficheiro CSV antigo", type="csv")
    mat_import = st.selectbox("A que matéria pertencem estas questões?", LISTA_MATERIAS)
    
    if upload and st.button("Iniciar Importação para a Nuvem"):
        df_old = pd.read_csv(upload, dtype={'Código': str})
        
        # Limpar os códigos do CSV antigo
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
            st.success(f"Sucesso! {len(novas_questoes)} questões novas foram migradas para o Google Sheets!")
            st.rerun()
        else:
            st.info("Todas as questões do ficheiro já existem no banco da nuvem.")