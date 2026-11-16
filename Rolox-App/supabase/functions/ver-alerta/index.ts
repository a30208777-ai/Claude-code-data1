// Mostra ao DONO da conta a senha que foi tentada num alerta de segurança.
// Só funciona com o token do próprio dono; marca o alerta como lido.
//
// Deploy: supabase functions deploy ver-alerta

import { createClient } from "jsr:@supabase/supabase-js@2";
import { decifrar } from "../_shared/cripto.ts";
import { cors, json } from "../_shared/http.ts";

const URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

const admin = createClient(URL, SERVICE, { auth: { persistSession: false } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ erro: "metodo_invalido" }, 405);

  const token = req.headers.get("Authorization")?.replace(/^Bearer\s+/i, "");
  if (!token) return json({ erro: "nao_autenticado" }, 401);

  const { data: quem, error } = await admin.auth.getUser(token);
  if (error || !quem.user) return json({ erro: "nao_autenticado" }, 401);

  let id: number;
  try {
    id = Number((await req.json()).alerta_id);
  } catch {
    return json({ erro: "corpo_invalido" }, 400);
  }
  if (!Number.isInteger(id)) return json({ erro: "dados_invalidos" }, 400);

  const { data: alerta } = await admin
    .from("alertas_seguranca")
    .select("id, user_id, senha_tentada_cifrada")
    .eq("id", id).eq("user_id", quem.user.id).maybeSingle();
  if (!alerta) return json({ erro: "alerta_nao_encontrado" }, 404);

  const senha = await decifrar(alerta.senha_tentada_cifrada);
  await admin.from("alertas_seguranca").update({ lido: true }).eq("id", id);
  return json({ senha_tentada: senha });
});
