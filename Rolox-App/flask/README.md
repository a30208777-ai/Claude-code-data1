# Rolox — versão Flask (Termux)

Mesmo app do `../mobile` (Flet), só que em **Flask**: roda dentro do Termux e abre no navegador do celular. Só usa `flask` e `requests`, que são Python puro, então **não precisa compilar nada** (sem Rust, sem `pydantic-core`).

## Rodar no Termux

```bash
pkg install python git
pip install flask requests
git clone -b claude/rolox-arquitetura-v2-review-n5kxxe https://github.com/a30208777-ai/Claude-code-data1
cd Claude-code-data1/Rolox-App/flask
python app.py
```

Abra **http://localhost:8550** no Chrome do celular. Dica: no menu do Chrome, use "Adicionar à tela inicial" para abrir como se fosse um app.

| Variável | Padrão | Para quê |
|---|---|---|
| `ROLOX_PORTA` | `8550` | Porta do servidor |
| `ROLOX_HOST` | `127.0.0.1` | `0.0.0.0` libera para outros aparelhos do Wi-Fi (cuidado: eles poderiam usar a sua sessão) |
| `ROLOX_SUPABASE_URL` / `ROLOX_SUPABASE_CHAVE` | projeto "Rolox" | Outro projeto Supabase |

## Telas
Login (com tentativas restantes e aviso de IP bloqueado), Cadastro, Início (status e alertas *"Alguém tentou entrar na sua conta"* com botão para ver a senha usada), Servidores (lista, filtro hack/limpo, criar, entrar ou fila), Chat (atualiza a cada 2 s; o host manda heartbeat) e Perfil (idioma, jogo com hack/mod, localização, sair). Tema claro e escuro automático.

### Studio (`/studio`)
A aba 🧱 **Studio** mostra se o ROLOX Studio (`../../Rolox-Studio/servidor.py`, porta 8600) está ligado neste aparelho:

- **ligado:** botões para abrir o Studio leve (celular) ou o Studio PC, criar um jogo a partir de um modelo (Vazio, Obby em Luau, Coleta de moedas em Python) e abrir os projetos salvos;
- **desligado:** mostra o comando para ligar no Termux (`cd Claude-code-data1/Rolox-Studio && python servidor.py`, numa segunda sessão) e o botão "Tentar de novo".

Outro endereço para o Studio: variável `ROLOX_STUDIO_URL` (padrão `http://localhost:8600`). A lógica fica em `studio_local.py`, igual à do app Flet (`../mobile/src/rolox/studio.py`).

## Segurança
- Só escuta em `127.0.0.1` por padrão.
- Proteção CSRF em todos os formulários e chamadas.
- Cookie de sessão `HttpOnly` e `SameSite=Lax`, assinado com um segredo salvo em `~/.rolox_flask_segredo`.
- Tudo o que vem do servidor é escapado (nada de HTML injetado pelo nome ou pelo chat).

## Testes
```bash
pip install pytest
python -m pytest -q
```
São 21 testes, usando um Supabase falso em memória.

## Backend
É o mesmo do app Flet: `../supabase` (migração SQL e Edge Functions). Veja `../mobile/README.md` para o passo a passo.
