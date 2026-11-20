import type { SupabaseClient } from "jsr:@supabase/supabase-js@2";

export const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

export function json(corpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------- IP do jogador
//
// App no celular/Termux: fala direto com o Supabase, e o gateway preenche
// x-forwarded-for com o IP de quem conectou.
//
// Site no Render: quem conecta aqui é o SERVIDOR do Render (o mesmo IP para todos
// os jogadores). Sem isso, 3 senhas erradas de qualquer pessoa baniriam o IP do
// Render e ninguém mais entraria pelo site. Por isso o servidor manda o IP real do
// jogador em x-rolox-ip-cliente, junto com x-rolox-proxy-chave. A chave fica em
// public.config_servidor (nome = 'proxy_chave'), que só a service_role lê.

const IP = /^[0-9a-fA-F:.]{2,45}$/;
let cacheChave: { valor: string | null; ate: number } | null = null;

async function chaveDoProxy(admin: SupabaseClient): Promise<string | null> {
  if (cacheChave && cacheChave.ate > Date.now()) return cacheChave.valor;
  const { data, error } = await admin
    .from("config_servidor").select("valor").eq("nome", "proxy_chave").maybeSingle();
  const valor = !error && data?.valor ? String(data.valor) : null;
  cacheChave = { valor, ate: Date.now() + 5 * 60_000 };
  return valor;
}

function iguais(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

/** IP real do jogador, ou null se não der para saber com segurança. */
export async function ipDoCliente(req: Request, admin: SupabaseClient): Promise<string | null> {
  const enviada = req.headers.get("x-rolox-proxy-chave");
  if (enviada !== null) {
    // veio pelo site: só vale com a chave certa; se não, recusa (nunca usa o IP do servidor)
    const chave = await chaveDoProxy(admin);
    if (!chave || !iguais(chave, enviada)) return null;
    const ip = req.headers.get("x-rolox-ip-cliente")?.trim() ?? "";
    return IP.test(ip) && (ip.includes(".") || ip.includes(":")) ? ip : null;
  }
  const xff = req.headers.get("x-forwarded-for");
  const ip = xff?.split(",")[0]?.trim() || req.headers.get("x-real-ip")?.trim();
  return ip || null;
}
