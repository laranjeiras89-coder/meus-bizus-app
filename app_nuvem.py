import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection # A nossa nova ferramenta para a Nuvem!

st.set_page_config(page_title="Gestor Bizu Cloud", layout="wide")

# Lista de matérias para os menus suspensos
LISTA_MATERIAS = ["Direito Penal", "Estatística", "Processual Penal", "Economia"]

# --- CONEXÃO COM O GOOGLE SHEETS ---
# Criamos a ligação usando a ferramenta oficial do Streamlit para o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados_nuvem(nome_aba, colunas_padrao):
    try:
        # O ttl=0 garante que lê sempre os dados frescos
        df = conn.read(worksheet=nome_aba, ttl=0)
        df = df.dropna(how="all") # Remove linhas totalmente vazias
        
        # --- O BIZU DA LIMPEZA DOS ZEROS (.0) E VAZIOS (NAN) ---
        colunas_para_limpar = ['Código', 'Ano']
        for col in colunas_para_limpar:
            if col in df.columns:
                # 1. Converte tudo para texto
                df[col] = df[col].astype(str)
                # 2. Apaga o ".0" que fica preso no final dos números
                df[col] = df[col].str.replace(r'\.0$', '', regex=True)
                # 3. Limpa a palavra 'nan' deixando a célula vazia novamente
                df[col] = df[col].replace('nan', '').str.strip()
                
        return df
    except:
        # Se a aba der erro, cria uma tabela vazia com as colunas certas
        return pd.DataFrame(columns=colunas_padrao)

def guardar_dados_nuvem(df, nome_aba):
    # Atualiza o Google Sheets com a nova tabela
    conn.update(worksheet=nome_aba, data=df)

# Carregamos as duas abas do nosso Google Sheets (O Banco principal e o Histórico)
COLUNAS_BANCO = ['Código', 'Matéria', 'Ano', 'Banca', 'Assunto', 'Comentário', 'Última Modificação']
COLUNAS_EXCLUSOES = ['Código', 'Matéria', 'Banca', 'Assunto', 'Data Exclusão']

df = carregar_dados_nuvem("Banco", COLUNAS_BANCO)

# --- INTERFACE PRINCIPAL ---
st.title("☁️ Sistema de Gestão de Bizus (Cloud)")

aba_pesquisa, aba_add, aba_rel = st.tabs([
    "🔍 Pesquisar e Gerir", 
    "➕ Adicionar Nova",
    "📊 Relatórios e Estatísticas"
])

# --- 1. ABA PESQUISAR E GERIR ---
with aba_pesquisa:
    st.markdown("### Pesquise e clique na linha para ver/editar/excluir")
    
    search = st.text_input("Filtrar na tabela (Banca, Assunto, Código, Matéria...):")
    
    df_visualizacao = df.copy()
    if search:
        mask = df_visualizacao.apply(lambda r: r.astype(str).str.contains(search, case=False).any(), axis=1)
        df_visualizacao = df_visualizacao[mask]

    # Tabela Interativa
    selecao = st.dataframe(
        df_visualizacao[['Código', 'Matéria', 'Ano', 'Banca', 'Assunto', 'Última Modificação']], 
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(selecao.selection.rows) > 0:
        idx_selecionado = df_visualizacao.index[selecao.selection.rows[0]]
        row = df.loc[idx_selecionado]
        
        st.markdown("---")
        st.subheader(f"📖 Detalhes da Questão: {row['Código']}")
        
        with st.form("form_gestao"):
            c_mat, c_ano, c_banca, c_assu = st.columns(4)
            
            # Descobrir o índice da matéria atual para mostrar no menu suspenso
            materia_atual = str(row.get('Matéria', 'Direito Penal'))
            idx_mat = LISTA_MATERIAS.index(materia_atual) if materia_atual in LISTA_MATERIAS else 0
            
            e_mat = c_mat.selectbox("Matéria", LISTA_MATERIAS, index=idx_mat)
            e_ano = c_ano.text_input("Ano", value=str(row.get('Ano', '')))
            e_banca = c_banca.text_input("Banca", value=str(row.get('Banca', '')))
            e_assu = c_assu.text_input("Assunto", value=str(row.get('Assunto', '')))
            
            e_coment = st.text_area("Comentário Completo / Bizu", value=str(row.get('Comentário', '')), height=350)
            
            col_btn1, col_btn2, _ = st.columns([1, 1, 3])
            btn_save = col_btn1.form_submit_button("💾 Salvar Alterações", use_container_width=True)
            btn_del = col_btn2.form_submit_button("🗑️ Excluir Questão", type="primary", use_container_width=True)
            
            if btn_save:
                df.at[idx_selecionado, 'Matéria'] = e_mat
                df.at[idx_selecionado, 'Ano'] = e_ano
                df.at[idx_selecionado, 'Banca'] = e_banca
                df.at[idx_selecionado, 'Assunto'] = e_assu
                df.at[idx_selecionado, 'Comentário'] = e_coment
                df.at[idx_selecionado, 'Última Modificação'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                guardar_dados_nuvem(df, "Banco")
                st.success("Alterações guardadas na Nuvem!")
                st.rerun()
                
            if btn_del:
                # Regista exclusão
                df_exclusoes = carregar_dados_nuvem("Exclusoes", COLUNAS_EXCLUSOES)
                nova_exclusao = pd.DataFrame([{
                    'Código': row['Código'], 'Matéria': row.get('Matéria', ''),
                    'Banca': row['Banca'], 'Assunto': row['Assunto'],
                    'Data Exclusão': datetime.now().strftime("%d/%m/%Y %H:%M")
                }])
                df_exclusoes = pd.concat([df_exclusoes, nova_exclusao], ignore_index=True)
                guardar_dados_nuvem(df_exclusoes, "Exclusoes")
                
                # Apaga do banco principal
                df = df.drop(idx_selecionado)
                guardar_dados_nuvem(df, "Banco")
                st.warning("Questão removida da Nuvem!")
                st.rerun()

# --- 2. ABA ADICIONAR NOVA ---
with aba_add:
    st.subheader("📝 Cadastrar Novo Bizu")
    with st.form("new_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        n_cod = c1.text_input("Código (Chave Primária)")
        n_mat = c2.selectbox("Matéria", LISTA_MATERIAS)
        n_ano = c3.text_input("Ano")
        
        c4, c5 = st.columns(2)
        n_banca = c4.text_input("Banca")
        n_assu = c5.text_input("Assunto")
        
        n_com = st.text_area("Comentário / Bizu", height=200)
        
        if st.form_submit_button("Adicionar ao Banco Cloud"):
            if n_cod and n_com:
                # O TEU REQUISITO: VERIFICAR SE A QUESTÃO JÁ EXISTE!
                if str(n_cod).strip() in df['Código'].values:
                    st.error(f"⚠️ Ação Bloqueada: A questão com o Código '{n_cod}' já existe no banco de dados!")
                else:
                    nova = pd.DataFrame([{
                        'Código': str(n_cod).strip(), 'Matéria': n_mat, 'Ano': n_ano, 'Banca': n_banca,
                        'Assunto': n_assu, 'Comentário': n_com,
                        'Última Modificação': datetime.now().strftime("%d/%m/%Y %H:%M")
                    }])
                    df = pd.concat([df, nova], ignore_index=True)
                    guardar_dados_nuvem(df, "Banco")
                    st.success("Nova questão guardada na Nuvem com sucesso!")
                    st.rerun()
            else:
                st.error("Código e Comentário são obrigatórios.")

# --- 3. ABA RELATÓRIOS ---
with aba_rel:
    st.subheader("📊 Estatísticas Cloud")
    
    col_tot, col_mat, col_ban = st.columns(3)
    col_tot.metric("Total Geral de Questões", len(df))
    col_mat.metric("Matérias Diferentes", df.get('Matéria', pd.Series()).nunique())
    col_ban.metric("Bancas Atendidas", df['Banca'].nunique())

    st.markdown("---")
    
    if not df.empty:
        st.write("#### Quantidade por Matéria")
        st.dataframe(df['Matéria'].value_counts().reset_index().rename(columns={'count':'Quantidade'}), use_container_width=True)