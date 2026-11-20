// Cadastro do Rolox: e-mail OPCIONAL.
//
// A conta no Supabase Auth usa um e-mail interno (<username>@jogador.rolox.invalid),
// já confirmado, que nunca recebe mensagens (.invalid é um domínio reservado).
// O e-mail de verdade, se o jogador quiser informar, fica em perfis.email e pode
// ser trocado depois em Perfil/config. Depois de criar, já devolve a sessão.
//
// Deploy: supabase functions deploy cadastro --no-verify-jwt

import { createClient } from "jsr:@supabase/supabase-js@2";
import { cors, ipDoCliente, json } from "./http.ts";

const URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;

export const DOMINIO_INTERNO = "jogador.rolox.invalid";
const USERNAME = /^[a-z0-9]([a-z0-9-]{1,30}[a-z0-9])$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const admin = createClient(URL, SERVICE, { auth: { persistSession: false } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ erro: "metodo_invalido" }, 405);

  let username = "", senha = "", email = "", localizacao = false;
  try {
    const c = await req.json();
    username = String(c.username ?? "").trim().toLowerCase();
    senha = String(c.senha ?? "");
    email = String(c.email ?? "").trim().toLowerCase();
    localizacao = c.aceitou_localizacao === true;
  } catch {
    return json({ erro: "corpo_invalido" }, 400);
  }

  if (!USERNAME.test(username)) return json({ erro: "username_invalido" }, 400);
  if (senha.length < 8 || senha.length > 72) return json({ erro: "senha_curta" }, 400);
  if (email && (email.length > 254 || !EMAIL.test(email))) return json({ erro: "email_invalido" }, 400);

  const ip = await ipDoCliente(req, admin);
  if (!ip) return json({ erro: "ip_desconhecido" }, 400);
  const { data: bloqueado } = await admin
    .from("ips_bloqueados").select("ip").eq("ip", ip).maybeSingle();
  if (bloqueado) return json({ erro: "ip_bloqueado" }, 403);

  const { data: existe } = await admin
    .from("perfis").select("id").eq("username", username).maybeSingle();
  if (existe) return json({ erro: "username_em_uso" }, 409);

  const emailInterno = `${username}@${DOMINIO_INTERNO}`;
  const { error: erroCriar } = await admin.auth.admin.createUser({
    email: emailInterno,
    password: senha,
    email_confirm: true,
    user_metadata: { username, aceitou_localizacao: localizacao, email_contato: email || null },
  });
  if (erroCriar) {
    if (/already|registered|exists/i.test(erroCriar.message)) return json({ erro: "username_em_uso" }, 409);
    if (/password/i.test(erroCriar.message)) return json({ erro: "senha_fraca", detalhe: erroCriar.message }, 400);
    return json({ erro: "erro_cadastro", detalhe: erroCriar.message }, 400);
  }

  const publico = createClient(URL, ANON, { auth: { persistSession: false } });
  const { data: sessao, error } = await publico.auth.signInWithPassword({ email: emailInterno, password: senha });
  if (error || !sessao.session) return json({ erro: "erro_cadastro", detalhe: error?.message }, 500);

  await admin.from("ips_confiaveis").upsert({ user_id: sessao.user.id, ip });
  return json({
    access_token: sessao.session.access_token,
    refresh_token: sessao.session.refresh_token,
    expires_in: sessao.session.expires_in,
    user_id: sessao.user.id,
  }, 201);
});
