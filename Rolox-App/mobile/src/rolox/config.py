"""Configuração do app Rolox Mobile.

A chave abaixo é a *publishable key* do Supabase: ela é pública por natureza
(vai dentro do app) e só dá o acesso que as regras RLS permitem.
Nunca coloque aqui a service_role key.
"""

import os

SUPABASE_URL = os.environ.get("ROLOX_SUPABASE_URL", "https://llgriaqnlcylpaxudrlg.supabase.co")
SUPABASE_CHAVE = os.environ.get("ROLOX_SUPABASE_CHAVE", "sb_publishable_GFKzsWxgUtXTff5fHWVVfQ_dUKdF62n")

# Rolox Studio (editor de jogos) rodando neste aparelho: Rolox-Studio/servidor.py
STUDIO_URL = os.environ.get("ROLOX_STUDIO_URL", "http://localhost:8600")

# Intervalos de atualização (segundos)
INTERVALO_CHAT = 2
INTERVALO_ALERTAS = 10
INTERVALO_SERVIDORES = 5
INTERVALO_HEARTBEAT = 15

IDIOMAS = {
    "pt-BR": "Português",
    "en": "English",
    "es": "Español",
}
