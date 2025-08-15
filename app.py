import sqlite3
from contextlib import closing
from datetime import datetime, date
import pandas as pd
import streamlit as st
import altair as alt
import os

# -----------------------------
# Configuração
# -----------------------------
st.set_page_config(page_title="Controle de Vendas", layout="wide")
DB_PATH = os.path.join("data", "db.sqlite3")

# Taxas fixas do negócio (podem ser ajustadas no sidebar)
DEFAULT_VAR_FEE = 0.20         # 20%
DEFAULT_FIXED_FEE = 4.0        # R$ 4
DEFAULT_TAX = 0.08             # 8%
DEFAULT_ANTECIP = 0.01         # 1%

# -----------------------------
# DB utilities
# -----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with closing(get_conn()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                cost REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                d TEXT UNIQUE NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                marketplace TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(date_id) REFERENCES dates(id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

def df(query, params=None):
    with closing(get_conn()) as conn:
        return pd.read_sql_query(query, conn, params=params or [])

def execute(query, params=None):
    with closing(get_conn()) as conn, conn:
        conn.execute(query, params or [])

def executemany(query, seq):
    with closing(get_conn()) as conn, conn:
        conn.executemany(query, seq)

# -----------------------------
# Cálculos de negócio
# -----------------------------
def calc_row(qty, unit_price, cost_unit, var_fee=DEFAULT_VAR_FEE, fixed_fee=DEFAULT_FIXED_FEE, tax=DEFAULT_TAX, antecip=DEFAULT_ANTECIP):
    """Retorna (receita_bruta, total_taxas, custo_total, lucro)"""
    receita = qty * unit_price
    taxas_unit = (var_fee * unit_price) + fixed_fee + (tax * unit_price) + (antecip * unit_price)
    total_taxas = qty * taxas_unit
    custo_total = qty * cost_unit
    lucro = receita - total_taxas - custo_total
    return receita, total_taxas, custo_total, lucro

def add_calc_columns(df_sales, var_fee, fixed_fee, tax, antecip):
    if df_sales.empty:
        return df_sales.assign(receita_bruta=[], total_taxas=[], custo_total=[], lucro=[])
    df_sales = df_sales.copy()
    df_sales["receita_bruta"] = df_sales["qty"] * df_sales["unit_price"]
    df_sales["total_taxas"] = df_sales["qty"] * ((var_fee + tax + antecip) * df_sales["unit_price"] + fixed_fee)
    df_sales["custo_total"] = df_sales["qty"] * df_sales["cost"]
    df_sales["lucro"] = df_sales["receita_bruta"] - df_sales["total_taxas"] - df_sales["custo_total"]
    return df_sales

# -----------------------------
# Inicialização
# -----------------------------
init_db()

# Sidebar - parâmetros de taxas
st.sidebar.header("Parâmetros de Taxas")
var_fee = st.sidebar.number_input("Taxa variável (%)", min_value=0.0, max_value=1.0, value=DEFAULT_VAR_FEE, step=0.01, format="%.2f")
fixed_fee = st.sidebar.number_input("Taxa fixa (R$ por un.)", min_value=0.0, value=DEFAULT_FIXED_FEE, step=0.5, format="%.2f")
tax = st.sidebar.number_input("Imposto (%)", min_value=0.0, max_value=1.0, value=DEFAULT_TAX, step=0.01, format="%.2f")
antecip = st.sidebar.number_input("Antecipação (%)", min_value=0.0, max_value=1.0, value=DEFAULT_ANTECIP, step=0.01, format="%.2f")

st.sidebar.markdown("---")
st.sidebar.caption("Dica: 0.20 = 20%")

tabs = st.tabs(["🧾 Produtos", "📅 Datas", "🛒 Vendas", "📊 Resumo Diário", "📈 Dashboard", "📜 Relatórios"])

# -----------------------------
# Tab: Produtos
# -----------------------------
with tabs[0]:
    st.subheader("Cadastro de Produtos")
    col1, col2, col3 = st.columns([3,2,1])
    with col1:
        pname = st.text_input("Nome do produto", key="prod_nome")
    with col2:
        pcost = st.number_input("Preço de custo (R$/un.)", min_value=0.0, step=0.5, format="%.2f", key="prod_custo")
    with col3:
        if st.button("Adicionar", type="primary"):
            if pname.strip() == "":
                st.error("Informe o nome do produto.")
            else:
                try:
                    execute("INSERT INTO products(name, cost) VALUES(?,?)", [pname.strip(), pcost])
                    st.success(f"Produto '{pname}' adicionado!")
                    st.experimental_rerun()
                except sqlite3.IntegrityError:
                    st.error("Já existe um produto com esse nome.")

    prods = df("SELECT id, name AS nome, cost AS custo FROM products ORDER BY name")
    st.dataframe(prods, use_container_width=True, hide_index=True)

    # Remover produto
    if not prods.empty:
        st.markdown("**Excluir produto**")
        colx, coly = st.columns([3,1])
        with colx:
            pid = st.selectbox("Selecione o produto (ID)", prods["id"].tolist())
        with coly:
            if st.button("Excluir", key="del_prod"):
                try:
                    execute("DELETE FROM products WHERE id = ?", [int(pid)])
                    st.success("Produto excluído.")
                    st.experimental_rerun()
                except sqlite3.IntegrityError as e:
                    st.error(f"Erro ao excluir: {e}")

# -----------------------------
# Tab: Datas
# -----------------------------
with tabs[1]:
    st.subheader("Cadastro de Datas")
    d = st.date_input("Data", value=date.today())
    if st.button("Adicionar data", key="add_date"):
        try:
            execute("INSERT INTO dates(d) VALUES(?)", [d.isoformat()])
            st.success(f"Data {d.isoformat()} adicionada!")
            st.experimental_rerun()
        except sqlite3.IntegrityError:
            st.warning("Essa data já está cadastrada.")

    datas = df("SELECT id, d AS data FROM dates ORDER BY d")
    st.dataframe(datas, use_container_width=True, hide_index=True)

    # Remover data
    if not datas.empty:
        colx, coly = st.columns([3,1])
        with colx:
            did = st.selectbox("Selecione a data (ID)", datas["id"].tolist())
        with coly:
            if st.button("Excluir data", key="del_date"):
                try:
                    execute("DELETE FROM dates WHERE id = ?", [int(did)])
                    st.success("Data excluída.")
                    st.experimental_rerun()
                except sqlite3.IntegrityError as e:
                    st.error(f"Erro ao excluir: {e}")

# -----------------------------
# Tab: Vendas
# -----------------------------
with tabs[2]:
    st.subheader("Lançar Vendas (vários produtos no mesmo dia)")

    datas = df("SELECT id, d FROM dates ORDER BY d")
    prods = df("SELECT id, name, cost FROM products ORDER BY name")

    if datas.empty or prods.empty:
        st.info("Cadastre **Datas** e **Produtos** antes de lançar vendas.")
    else:
        col1, col2, col3, col4, col5 = st.columns([2,3,2,2,3])
        with col1:
            did = st.selectbox("Data", options=datas["id"], format_func=lambda x: datas.loc[datas["id"]==x, "d"].iloc[0])
        with col2:
            pid = st.selectbox("Produto", options=prods["id"], format_func=lambda x: prods.loc[prods["id"]==x, "name"].iloc[0])
        with col3:
            qty = st.number_input("Quantidade", min_value=1, step=1, value=1)
        with col4:
            unit_price = st.number_input("Preço de venda (R$/un.)", min_value=0.0, step=0.5, format="%.2f")
        with col5:
            marketplace = st.text_input("Marketplace (opcional)")

        if st.button("Adicionar venda", type="primary"):
            execute("""
                INSERT INTO sales(date_id, product_id, qty, unit_price, marketplace)
                VALUES(?,?,?,?,?)
            """, [int(did), int(pid), int(qty), float(unit_price), marketplace.strip() or None])
            st.success("Venda adicionada!")
            st.experimental_rerun()

    # Tabela de vendas com cálculos
    sales = df("""
        SELECT s.id, d.d AS data, p.name AS produto, p.cost AS cost, s.qty, s.unit_price, s.marketplace
        FROM sales s
        JOIN dates d ON d.id = s.date_id
        JOIN products p ON p.id = s.product_id
        ORDER BY d.d, s.id
    """)

    sales_calc = add_calc_columns(sales, var_fee, fixed_fee, tax, antecip)
    st.markdown("### Vendas Lançadas")
    st.dataframe(sales_calc.rename(columns={
        "cost": "custo_unit",
        "qty": "quantidade",
        "unit_price": "preco_un"
    }), use_container_width=True, hide_index=True)

    # Excluir venda
    if not sales_calc.empty:
        colx, coly = st.columns([3,1])
        with colx:
            sid = st.selectbox("Excluir venda (ID)", options=sales_calc["id"].tolist())
        with coly:
            if st.button("Excluir", key="del_sale"):
                execute("DELETE FROM sales WHERE id = ?", [int(sid)])
                st.success("Venda excluída.")
                st.experimental_rerun()

# -----------------------------
# Tab: Resumo Diário
# -----------------------------
with tabs[3]:
    st.subheader("Resumo Diário")
    sales = df("""
        SELECT d.d AS data, p.name AS produto, p.cost, s.qty, s.unit_price, s.marketplace
        FROM sales s
        JOIN dates d ON d.id = s.date_id
        JOIN products p ON p.id = s.product_id
    """)
    sales_calc = add_calc_columns(sales, var_fee, fixed_fee, tax, antecip)

    if sales_calc.empty:
        st.info("Sem vendas para resumir.")
    else:
        resumo = (sales_calc
                  .groupby("data", as_index=False)
                  .agg(faturamento=("receita_bruta","sum"),
                       lucro=("lucro","sum")))
        resumo["data"] = pd.to_datetime(resumo["data"]).dt.date
        st.dataframe(resumo, use_container_width=True, hide_index=True)

        # Exportar CSV
        csv = resumo.to_csv(index=False).encode("utf-8")
        st.download_button("Baixar resumo (CSV)", csv, "resumo_diario.csv", "text/csv")

# -----------------------------
# Tab: Dashboard
# -----------------------------
with tabs[4]:
    st.subheader("Dashboard")
    sales = df("""
        SELECT d.d AS data, p.name AS produto, p.cost, s.qty, s.unit_price, s.marketplace
        FROM sales s
        JOIN dates d ON d.id = s.date_id
        JOIN products p ON p.id = s.product_id
    """)
    sales_calc = add_calc_columns(sales, var_fee, fixed_fee, tax, antecip)
    if sales_calc.empty:
        st.info("Lance vendas para ver o dashboard.")
    else:
        # Filtros
        colf1, colf2, colf3 = st.columns(3)
        with colf1:
            produtos = ["(todos)"] + sorted(sales_calc["produto"].unique().tolist())
            f_prod = st.selectbox("Produto", produtos)
        with colf2:
            markets = ["(todos)"] + sorted([m for m in sales_calc["marketplace"].dropna().unique().tolist()])
            f_market = st.selectbox("Marketplace", markets)
        with colf3:
            # Range de datas
            sales_calc["data"] = pd.to_datetime(sales_calc["data"]).dt.date
            dmin, dmax = sales_calc["data"].min(), sales_calc["data"].max()
            drange = st.date_input("Período", value=(dmin, dmax))

        # Aplicar filtros
        df_f = sales_calc.copy()
        if f_prod != "(todos)":
            df_f = df_f[df_f["produto"] == f_prod]
        if f_market != "(todos)":
            df_f = df_f[df_f["marketplace"] == f_market]
        if isinstance(drange, tuple) and len(drange) == 2:
            df_f = df_f[(df_f["data"] >= drange[0]) & (df_f["data"] <= drange[1])]

        if df_f.empty:
            st.warning("Nenhum dado para os filtros escolhidos.")
        else:
            resumo = (df_f.groupby("data", as_index=False)
                      .agg(faturamento=("receita_bruta","sum"),
                           lucro=("lucro","sum")))

            c1, c2 = st.columns(2)
            with c1:
                kpi_fat = resumo["faturamento"].sum()
                st.metric("Faturamento (período)", f"R$ {kpi_fat:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with c2:
                kpi_luc = resumo["lucro"].sum()
                st.metric("Lucro (período)", f"R$ {kpi_luc:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            chart_data = resumo.rename(columns={"data":"Data","faturamento":"Faturamento","lucro":"Lucro"})
            chart = alt.Chart(chart_data).transform_fold(
                ["Faturamento","Lucro"],
                as_=["Tipo","Valor"]
            ).mark_bar().encode(
                x="yearmonthdate(Data):T",
                y="Valor:Q",
                color="Tipo:N",
                tooltip=["Data:T","Valor:Q","Tipo:N"]
            ).properties(height=400)
            st.altair_chart(chart, use_container_width=True)

st.caption("💡 Dica: Para vários produtos no mesmo dia, basta lançar várias linhas na aba **Vendas** com a mesma Data.")
# -----------------------------
# Tab: Relatórios (Produto mais vendido do mês)
# -----------------------------
with tabs[5]:
    st.subheader("Relatórios — Produto mais vendido do mês")

    # Carrega vendas com joins
    sales = df("""
        SELECT d.d AS data, p.name AS produto, p.cost, s.qty, s.unit_price, s.marketplace
        FROM sales s
        JOIN dates d ON d.id = s.date_id
        JOIN products p ON p.id = s.product_id
    """)

    if sales.empty:
        st.info("Sem vendas para analisar.")
    else:
        # Conversões
        sales["data"] = pd.to_datetime(sales["data"]).dt.date
        sales["ano"] = pd.to_datetime(sales["data"]).dt.year
        sales["mes"] = pd.to_datetime(sales["data"]).dt.month

        # Filtros (ano, mês, marketplace)
        col1, col2, col3 = st.columns(3)
        with col1:
            anos = sorted(sales["ano"].unique().tolist())
            f_ano = st.selectbox("Ano", anos, index=len(anos)-1)
        with col2:
            meses = sorted(sales.loc[sales["ano"]==f_ano, "mes"].unique().tolist())
            mes_nome = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
            f_mes = st.selectbox("Mês", meses, format_func=lambda m: mes_nome.get(m, str(m)))
        with col3:
            markets = ["(todos)"] + sorted([m for m in sales["marketplace"].dropna().unique().tolist()])
            f_market = st.selectbox("Marketplace", markets)

        # Aplicar filtro
        use = sales[(sales["ano"]==f_ano) & (sales["mes"]==f_mes)].copy()
        if f_market != "(todos)":
            use = use[use["marketplace"]==f_market]

        # Recalcular métricas com as taxas atuais do sidebar
        use_calc = add_calc_columns(use, var_fee, fixed_fee, tax, antecip)

        if use_calc.empty:
            st.warning("Nenhuma venda para os filtros escolhidos.")
        else:
            # Produto mais vendido por quantidade
            by_qty = (use_calc.groupby("produto", as_index=False)
                      .agg(qtd_total=("qty","sum"),
                           faturamento=("receita_bruta","sum"),
                           lucro=("lucro","sum"))
                      .sort_values(["qtd_total","faturamento"], ascending=[False, False]))

            top_qty = by_qty.iloc[0]

            # Destaques
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Produto mais vendido (qtd)", top_qty["produto"])
            with c2:
                st.metric("Quantidade vendida", f"{int(top_qty['qtd_total'])}")
            with c3:
                st.metric("Lucro (produto campeão)", f"R$ {top_qty['lucro']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

            st.markdown("### Ranking de produtos (mês filtrado)")
            st.dataframe(by_qty.reset_index(drop=True), use_container_width=True)

            # Export
            st.download_button("Baixar ranking (CSV)", by_qty.to_csv(index=False).encode("utf-8"),
                               f"ranking_produtos_{f_ano}_{f_mes}.csv", "text/csv")

            # Resumo diário do mês filtrado
            st.markdown("### Resumo diário do mês (faturamento e lucro)")
            resumo = (use_calc.groupby("data", as_index=False)
                      .agg(faturamento=("receita_bruta","sum"),
                           lucro=("lucro","sum"))
                      .sort_values("data"))
            st.dataframe(resumo, use_container_width=True, hide_index=True)

            # Dica operacional
            st.caption("💡 Lembrete: cadastre vendas **todos os dias** — várias linhas com a mesma data representam vários produtos vendidos naquele dia, inclusive por marketplace.")
