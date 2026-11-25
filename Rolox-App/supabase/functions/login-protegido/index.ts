// Fase 3 — Login protegido do Rolox
//
// Regras:
//  * IP em ips_bloqueados -> recusado na hora.
//  * Senha errada -> grava a tentativa (senha cifrada + base64) e cria um
//    alerta para o DONO da conta, que vê o IP e a senha usada.
//  * 3ª senha errada do mesmo IP na mesma conta (24 h) -> o IP de quem errou
//    é banido. A conta do dono NÃO é banida.
//  * Exceção: se o IP já é confiável do próprio dono (ele mesmo errou),
//    não bane; envia e-mail de recuperação de senha.
//
// Deploy: supabase functions deploy login-protegido --no-verify-jwt

import { createClient } from "jsr:@supabase/supabase-js@2";
import { cifrar } from "./cripto.ts";
import { cors, ipDoCliente, json } from "./http.ts";

const URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON = Deno.env.get("SUPABASE_ANON_KEY")!;

const LIMITE = 3;
const JANELA_MS = 24 * 60 * 60 * 1000;

const admin = createClient(URL, SERVICE, { auth: { persistSession: false } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ erro: "metodo_invalido" }, 405);

  let username = "", senha = "";
  try {
    const corpo = await req.json();
    username = String(corpo.username ?? "").trim().toLowerCase();
    senha = String(corpo.senha ?? "");
  } catch {
    return json({ erro: "corpo_invalido" }, 400);
  }
  if (!username || !senha || senha.length > 200) return json({ erro: "dados_invalidos" }, 400);

  const ip = await ipDoCliente(req, admin);
  if (!ip) return json({ erro: "ip_desconhecido" }, 400);

  // 1. IP bloqueado?
  const { data: bloqueado } = await admin
    .from("ips_bloqueados").select("ip").eq("ip", ip).maybeSingle();
  if (bloqueado) return json({ erro: "ip_bloqueado" }, 403);

  // 2. Conta existe?
  const { data: perfil } = await admin
    .from("perfis").select("id, banido, motivo_ban").eq("username", username).maybeSingle();
  if (!perfil) return json({ erro: "credenciais_invalidas" }, 401);
  // conta banida: só avisa DEPOIS de conferir a senha (assim só o dono da conta abre o suporte de ban)

  const { data: usuario, error: erroUsuario } = await admin.auth.admin.getUserById(perfil.id);
  const email = usuario?.user?.email;
  if (erroUsuario || !email) return json({ erro: "credenciais_invalidas" }, 401);

  // 3. Tenta logar no Supabase Auth
  const publico = createClient(URL, ANON, { auth: { persistSession: false } });
  const { data: sessao, error } = await publico.auth.signInWithPassword({ email, password: senha });

  if (!error && sessao.session && perfil.banido) {
    await admin.auth.admin.signOut(sessao.session.access_token).catch(() => {});
    return json({ erro: "conta_banida", motivo: perfil.motivo_ban, senha_ok: true }, 403);
  }

  if (!error && sessao.session) {
    await admin.from("ips_confiaveis").upsert(
      { user_id: perfil.id, ip, visto_em: new Date().toISOString() },
    );
    await admin.from("tentativas_login").delete().eq("conta_alvo", perfil.id).eq("ip", ip);
    return json({
      access_token: sessao.session.access_token,
      refresh_token: sessao.session.refresh_token,
      expires_in: sessao.session.expires_in,
      user_id: perfil.id,
    });
  }

  if (error && /email not confirmed/i.test(error.message)) {
    return json({ erro: "email_nao_confirmado" }, 401);
  }

  // 4. Senha errada
  const cifrada = await cifrar(senha);
  await admin.from("tentativas_login").insert({
    conta_alvo: perfil.id, ip, senha_tentada_cifrada: cifrada,
  });

  const desde = new Date(Date.now() - JANELA_MS).toISOString();
  const { count } = await admin
    .from("tentativas_login")
    .select("id", { count: "exact", head: true })
    .eq("conta_alvo", perfil.id).eq("ip", ip).gte("criado_em", desde);
  const falhas = count ?? 1;

  const { data: confiavel } = await admin
    .from("ips_confiaveis").select("ip").eq("user_id", perfil.id).eq("ip", ip).maybeSingle();

  let banido = false;
  if (falhas >= LIMITE && !confiavel) {
    await admin.from("ips_bloqueados").upsert({ ip, conta_alvo: perfil.id });
    banido = true;
  }

  await admin.from("alertas_seguranca").insert({
    user_id: perfil.id, ip, senha_tentada_cifrada: cifrada, ip_foi_banido: banido,
  });

  if (banido) return json({ erro: "ip_bloqueado" }, 403);

  if (falhas >= LIMITE && confiavel) {
    // conta criada sem e-mail real (e-mail interno .invalid): não há para onde mandar
    if (!email.endsWith("@jogador.rolox.invalid")) {
      await publico.auth.resetPasswordForEmail(email);
      return json({ erro: "confirme_por_email" }, 401);
    }
    return json({ erro: "muitas_tentativas" }, 429);
  }

  return json({ erro: "credenciais_invalidas", tentativas_restantes: LIMITE - falhas }, 401);
});
