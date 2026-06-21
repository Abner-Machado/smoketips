# smokeTIPs — Projeto

> **Tese:** cansei de desempenho de IA *não-assistido*. Quando um orquestrador
> delega para outras camadas (modelos mais baratos, sub-agentes), ninguém está
> olhando ao vivo: o delegado estoura o cap de output, tenta uma ação destrutiva,
> ou queima token sem entregar — e só se descobre depois, no prejuízo.
>
> smokeTIPs é a camada que **observa, classifica e governa** essas camadas em
> tempo real. Onde há fumaça, há um aviso (*tip*).

Status: **planejamento + MVP em Python**. Rust era o plano para o núcleo-guarda
(hot path, memory-safe), mas o toolchain não está instalado nesta máquina; em vez
de shippar Rust não-compilado (stub), o MVP é 100% Python testado, e o núcleo Rust
fica como atualização futura (seção 8). Nada de código não-verificado vai pro ar.

---

## 1. O que é

Uma camada de **observabilidade + governança para orquestração de IA**. Não é só
ferramenta de defesa — é observação contínua. Dois lados, sempre juntos:

- **Defesa (guarda):** intercepta ações do delegado. Bloqueia destrutivo, força cap
  de output, varre segredo. Assertivo com o delegado, como quem dirige um grupo
  seleto: o delegado executa, não decide o que é perigoso.
- **Observação (ledger + score):** registra cada ação de cada camada, calcula
  métricas ao vivo e **classifica o desempenho mútuo** das camadas (qual tier
  entrega melhor por token, qual erra mais, qual viola regra).

Tudo **editável e rastreável**: eventos em JSONL append-only + relatório markdown
versionável no git. O mesmo princípio do [[projeto-cairn]] — o arquivo é o produto.

## 2. Por que mostrar isso ao humano

A ideia é chamar atenção para os pontos que o desenvolvedor **não coloca** — não
por serem opcionais, mas porque a ausência **defasa a própria ferramenta dele**:
sem cap, o delegado estoura contexto; sem guarda, um `rm -rf` do delegado apaga
trabalho; sem score, você nunca sabe se o tier barato vale a pena. smokeTIPs torna
o invisível visível, em linguagem de quem revisa como dev sênior, não como linter.

## 3. Problemas → solução por orquestração

| Problema (real, vivido) | Solução smokeTIPs |
|--------------------------|-------------------|
| Delegado estoura output (8096 tokens em arquivo grande) | cap configurável; guarda corta/avisa antes de devolver bloco gigante |
| Delegado tenta ação destrutiva sem ordem | guarda **nega** destrutivo para papel `delegate`; só `orchestrator` com OK explícito |
| Token queimado sem entrega | score de eficiência por camada (trabalho útil / token) |
| Não se sabe qual tier compensa | classificação mútua: ranking A–F por eficiência/segurança/confiabilidade |
| Segredo vaza num commit/output | varredura de padrões (chaves AWS/OpenAI/`gho_`/`sk-`) antes de passar |
| Desempenho só visível no fim | `watch`/`tail` ao vivo: tabela por agente atualizada em tempo real |

## 4. Arquitetura (Python MVP)

```
smoketips/
├── ledger.py    # append de evento (JSONL) + relatório markdown
├── guard.py     # regras: nega destrutivo, cap de output, scan de segredo
├── score.py     # score por camada + classificação mútua A–F
├── monitor.py   # tail ao vivo / métricas correntes
├── client.py    # API ergonômica: layer() context manager, emit(), guard()
└── cli.py       # smoketips watch|score|check|report|tail
skill/SKILL.md   # instrução que ensina o orquestrador a embrulhar delegações
```

**Modelo de evento** (uma linha JSONL, editável):
```json
{"ts":"…","layer":"delegate","agent":"produtor-haiku","tier":"haiku",
 "task":"gerar testes","action":"edit_file","tokens_in":0,"tokens_out":0,
 "output_bytes":0,"duration_ms":0,"status":"ok","flags":[]}
```

## 5. Critérios verificáveis (vago → testável, antes de codar)

1. **Rastreável:** toda ação delegada vira 1 linha no JSONL + entra no relatório md.
2. **Defesa:** ação destrutiva de `delegate` → guarda retorna `blocked` (testável).
3. **Cap:** output acima do limite → flag `over_cap` (testável).
4. **Segredo:** padrão de chave no texto → flag `secret`, bloqueia (testável).
5. **Observação:** `tail` mostra métrica por agente ao vivo (testável em sample).
6. **Classificação:** `score` emite grade A–F por camada (testável).
7. **Editável:** ledger e config são arquivos texto; editar reflete no próximo run.

## 6. Como a própria IA resolve (a skill)

A skill `smoketips` instrui o orquestrador: antes de delegar, abrir um `layer`;
toda ação do delegado passa por `guard`; ao fim, o score classifica a camada. A
inteligência fica na instrução — o código só mede e impõe.

## 7. Software companheiro (usar junto com a instrução)

- **Cairn** (irmão deste projeto) — registra o *porquê* das decisões; smokeTIPs
  registra o *desempenho* de quem as executa. Decisão + execução observadas.
- **MCP hosts** (Claude/Cursor/Cline) — emitem os eventos que o ledger consome.
- **pre-commit / git hooks** — chamar `smoketips check` antes de commit/push.
- **ripgrep** — motor de varredura de segredo no modo rápido.
- **jq** — fatiar o JSONL do ledger em pipelines/CI.

## 8. Sugestões / atualizações futuras (incluindo ideias não pedidas)

- **Núcleo em Rust** (`smoketips-core`): guarda + scorer no hot path, memory-safe,
  para interceptação em tempo real sem custo de Python. (Plano original, adiado.)
- **Limiar adaptativo:** o cap aprende com o histórico de cada agente.
- **Replay:** reconstruir uma sessão a partir do ledger para auditoria.
- **Webhook/alerta:** disparar quando uma camada cruza um limiar (custo, violação).
- **Badge de desempenho:** gerar um SVG com a nota da última run pro README.
- **Política por projeto:** `.smoketips.toml` versionado define caps/regras por repo.
- **Diff de regressão de desempenho:** comparar score entre commits (CI gate).

## 9. Princípio editorial dos posts

Os posts (README/releases) existem para **orientar e classificar desempenho mútuo**
— não vender. Tom dev sênior, honesto sobre limites, sempre com o que foi testado.
**Aceitamos sugestões:** issues e PRs abertos.

## 10. Próximo passo

MVP Python construído e testado → publicado no GitHub. Rust e os itens da seção 8
entram conforme prioridade.
