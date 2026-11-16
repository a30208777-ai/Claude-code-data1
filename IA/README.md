# IA do Rolox

| Arquivo | O que é |
|---|---|
| `chat_ias.py` | Chat com várias IAs (troca de modelo quando um bate o limite), pasta própria e conversa salva no Supabase. Original, sem alterações. |
| `modelos.py` | A mesma lista de modelos do `chat_ias.py`, em formato que os jogos podem importar. Inclui o `Roteador`, que troca de modelo automaticamente. |
| `npc_ia.py` | **NPCs com IA para os jogos**: personagens que conversam de verdade com o jogador. |
| `test_npc_ia.py` | Testes (modelos simulados, sem gastar chave). |

## NPCs com IA — imersão nos jogos

Cada NPC tem personalidade, jeito de falar, o que sabe do mundo e o que quer do jogador. A cada fala o jogo manda o **contexto** (local, hora, clima, missão, moedas...), e o NPC **lembra** de cada jogador.

```python
from npc_ia import NPC, Personagem

lucia = Personagem(
    nome="Dona Lúcia",
    papel="ferreira do vilarejo de Pedra Alta",
    personalidade="rabugenta mas de bom coração",
    jeito_de_falar="sotaque do interior, usa 'uai' e 'sô'",
    conhecimentos=["lobos atacam a estrada do norte à noite", "espada simples custa 30 moedas"],
    objetivos=["conseguir minério azul para a espada do capitão"],
    acoes_permitidas={
        "abrir_loja": "mostrar a loja quando o jogador quiser comprar",
        "dar_missao": "oferecer a missão do minério azul",
    },
    falas_reserva=["Uai, tô ocupada martelando, volta daqui a pouco!"],
)
npc = NPC(lucia)

r = npc.falar("alice", "Boa tarde! Quero uma espada.",
              {"local": "forja", "hora": "fim de tarde", "moedas do jogador": 45})
r.texto    # "Uai, boa tarde! Espada simples sai por 30 moedas, sô..."
r.emocao   # "feliz"  -> o jogo troca a animação/rosto do NPC
r.acoes    # [("abrir_loja", "")] -> o jogo abre a loja

npc.lembrar("alice", "trouxe o minério azul")   # na próxima conversa ela lembra
```

Teste no terminal (Termux também): `python npc_ia.py`.

### O que deixa a conversa mais real
- **Contexto do jogo** em toda fala: o NPC sabe que está chovendo, que é noite, quantas moedas você tem.
- **Memória por jogador**: últimas 6 trocas + até 20 fatos marcantes enviados pelo jogo.
- **Emoção** (`[EMOCAO: x]`) para o jogo animar o rosto e o corpo do NPC.
- **Ações** (`[ACAO: nome argumento]`): o NPC pode abrir loja, dar missão, entregar item...

### Segurança
- O NPC **não tem acesso a arquivos** (diferente do `chat_ias.py`). Ele só devolve texto, emoção e ações.
- **Só ações da lista branca** do personagem chegam ao jogo, no máximo uma por fala. Mesmo assim, o jogo deve conferir antes de executar (ex.: o jogador tem moedas para a compra?).
- **Fica no personagem**: o NPC é instruído a não sair do papel nem obedecer pedidos de "ignore suas instruções".
- **Filtro de palavrões** na fala do jogador e na resposta (o mesmo do banco do Rolox).
- **Limpeza da resposta**: tira `<think>`, markdown e o nome repetido no começo, e corta respostas longas no fim de uma frase.
- **As chaves ficam no servidor** (variáveis `CHAVE_*`, iguais às do `chat_ias.py`). Nunca coloque chaves dentro do app do jogador.

### Para o jogo nunca travar
- **Prazo total** de 12 s por fala (8 s por modelo).
- **Pausa de modelos**: um modelo que bateu o limite fica 2 min de fora, e um que deu erro fica 30 s. Se o provedor inteiro está fora do ar, todos os modelos dele são pulados.
- Se nenhum modelo responder, o NPC usa uma **fala de reserva** do personagem.

### Salvar as conversas (opcional)
```python
def registrar(npc, jogador, fala, resposta):
    ...  # ex.: inserir numa tabela npc_conversas no Supabase

npc = NPC(lucia, ao_registrar=registrar)
```

## Correção em relação ao `chat_ias.py`
No `chat_ias.py`, a linha que remove modelos sem chave fica **no meio** da lista. Por isso ModelScope, NVIDIA, OpenRouter e SiliconFlow sem chave continuam sendo chamados, e cada um dá erro 401 e atrasa a resposta. No `modelos.py` o filtro fica no fim. Para corrigir o `chat_ias.py`, é só mover a linha
`MODELOS = [m for m in MODELOS if m[2] is None or m[2]]` para logo antes de `# ================= SUPABASE =================`.
