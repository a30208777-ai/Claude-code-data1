"""Configuração do app Rolox Mobile.

A chave abaixo é a *publishable key* do Supabase: ela é pública por natureza
(vai dentro do app) e só dá o acesso que as regras RLS permitem.
Nunca coloque aqui a service_role key.
"""

import os

SUPABASE_URL = os.environ.get("ROLOX_SUPABASE_URL", "https://eqeleozhqwmziiscsyco.supabase.co")
SUPABASE_CHAVE = os.environ.get("ROLOX_SUPABASE_CHAVE", "sb_publishable_VQ7G5FBH-hpFZgkgGxCmrw_vNtmYC-P")

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
