# Controle de Vendas (Python + Streamlit + SQLite)

App simples para controlar **produtos**, **datas**, **vendas**, **faturamento** e **lucro**, com as seguintes taxas por venda:
- 20% (taxa variável)
- R$ 4,00 (taxa fixa por unidade vendida)
- 8% (imposto)
- 1% (antecipação)

> **Observação:** as taxas são configuráveis na barra lateral.

## 📦 Como rodar no VS Code

1. **Instale as dependências** (recomendado usar um venv):
   ```bash
   pip install -r requirements.txt
   ```

2. **Inicie o app**:
   ```bash
   streamlit run app.py
   ```

3. O navegador abre em `http://localhost:8501`.

## 🧱 Estrutura
```
controle_vendas_app/
├─ app.py
├─ requirements.txt
├─ README.md
└─ data/
   └─ db.sqlite3  (criado automaticamente ao executar)
```

## 🧾 Como usar
1. **Produtos**: cadastre nome e custo unitário.
2. **Datas**: cadastre cada dia (uma vez).
3. **Vendas**: selecione **Data** e **Produto**, informe **Quantidade** e **Preço de Venda (R$ / un.)**.
4. **Resumo Diário** e **Dashboard** são calculados automaticamente.

## 📊 Cálculos
Para cada venda:
- **Receita Bruta** = `quantidade * preço_venda`
- **Total de Taxas** = `quantidade * ((20% + 8% + 1%) * preço_venda + 4)`
- **Custo Total** = `quantidade * custo_unitário`
- **Lucro** = `Receita Bruta - Total de Taxas - Custo Total`

## 🚀 Como enviar para o GitHub
```bash
# dentro da pasta do projeto
git init
git add .
git commit -m "feat: controle de vendas streamlit + sqlite"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/controle_vendas_app.git
git push -u origin main
```

> Dica: substitua `SEU_USUARIO` pelo seu usuário no GitHub e crie o repositório antes do `push`.

## 🧹 .gitignore (opcional)
Crie um arquivo `.gitignore` e adicione:
```
data/db.sqlite3
__pycache__/
.env
```

---

Feito para permitir **múltiplos produtos no mesmo dia**: basta lançar várias linhas na aba **Vendas** com a mesma **Data**.