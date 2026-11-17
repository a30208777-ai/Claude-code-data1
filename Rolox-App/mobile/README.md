# Rolox Mobile (Python + Flet)

App do Rolox para celular, escrito em Python com [Flet](https://flet.dev) (gera APK para Android e app para iOS).
Segue a arquitetura v3: **o celular acessa direto as bases de dados do Supabase**, protegidas por RLS, e o login passa pela Edge Function `login-protegido` (regra das 3 tentativas).

## Telas

| Tela | O que faz |
|---|---|
| **Login** | Entra com usuário e senha. Mostra tentativas restantes e avisa se o IP foi bloqueado. |
| **Cadastro** | Usuário (minúsculas, números, hífen — vale como subdomínio no PC), senha, e-mail **opcional** e consentimento de localização (LGPD). Já entra na conta, sem confirmação por e-mail. |
| **Início** | Status (lobby, fila com posição ou servidor) e **alertas de segurança**: "Alguém tentou entrar na sua conta", com IP, data e botão para ver a senha que foi usada. |
| **Servidores** | Lista servidores com jogadores/capacidade e etiqueta HACK/MOD; filtro "só os que posso entrar"; criar servidor; entrar ou ir para a fila. |
| **Chat** | Chat do servidor com filtro de palavrões (filtro local antes da IA SELECT); botão Sair. O host manda heartbeat a cada 15 s. |
| **Perfil (config)** | Idioma do chat, jogo onde usa hack/mod (troca rápida), mostrar localização, e-mail opcional, sair da conta. |

## Rodar

```bash
cd mobile
python -m venv .venv && source .venv/bin/activate
pip install flet==1.1.2 pytest

flet run src/main.py            # janela no PC
flet run --android src/main.py  # no celular, pelo app "Flet" da Play Store (mesma rede Wi-Fi)
flet build apk                  # gera o APK em build/apk
python -m pytest                # testes do cliente da API
```

O endereço do Supabase e a *publishable key* ficam em `src/rolox/config.py` (ou nas variáveis `ROLOX_SUPABASE_URL` / `ROLOX_SUPABASE_CHAVE`). A publishable key é pública por natureza; **nunca** coloque a service_role key no app.

## Backend necessário (pasta `../supabase`)

1. **Banco:** aplicar `supabase/migrations/20261116000000_rolox_base.sql` e depois `20261117000000_email_opcional.sql` (tabelas, RLS, RPCs `entrar_servidor`, `sair_servidor`, `enviar_mensagem`, `atualizar_local`, triggers e limpezas agendadas).
2. **Segredo da criptografia:** `supabase secrets set ROLOX_CHAVE=$(openssl rand -base64 32)`
3. **Edge Functions:**
   ```bash
   supabase functions deploy cadastro --no-verify-jwt
   supabase functions deploy login-protegido --no-verify-jwt
   supabase functions deploy ver-alerta
   ```
4. **pg_cron** (opcional, recomendado): ativar a extensão antes da migração para limpar servidores sem heartbeat e apagar dados com mais de 30 dias.
5. **Catálogo:** cadastrar os jogos em `jogos` com `commit_aprovado` preenchido (só jogos aprovados aparecem no app).

Testes do banco num Postgres local: `supabase/tests/rodar.sh`.

## E-mail opcional
O cadastro passa pela Edge Function `cadastro`, que cria a conta no Supabase Auth com um e-mail interno (`<usuario>@jogador.rolox.invalid`, domínio reservado que nunca recebe mensagens) já confirmado. O e-mail de verdade, se o jogador quiser, fica em `perfis.email` e pode ser trocado em Perfil/config. Contas sem e-mail não recebem o e-mail de recuperação depois de 3 senhas erradas no próprio aparelho; em vez disso aparece "Muitas senhas erradas, espere um pouco".

## Limitações conhecidas

- **Login direto no Supabase Auth:** a regra das 3 tentativas vale para quem entra pelo app (Edge Function). Alguém que chamar o endpoint `/auth/v1/token` do Supabase direto pula essa contagem (só pega o limite padrão do Supabase). Para fechar isso: usar o *Password Verification Hook* do Supabase Auth (planos pagos) ou bloquear o login por senha direto e deixar só a Edge Function.
- **Tempo real por consulta periódica:** o app consulta o chat a cada 2 s e os alertas a cada 10 s, em vez de usar o WebSocket do Supabase Realtime (o SDK de Realtime em Python não roda no APK sem dependências nativas). As tabelas já estão na publicação do Realtime para quando isso for trocado.
- **IA SELECT e tradução** ainda não estão ligadas (Fase 17); hoje só o filtro local por lista de termos (`termos_bloqueados`).
- As Edge Functions (TypeScript) não foram executadas nos testes; o SQL e o app foram testados.
