// Criptografia AES-GCM + base64 para senhas tentadas e credenciais de backup.
// A chave fica no segredo ROLOX_CHAVE (32 bytes em base64):
//   supabase secrets set ROLOX_CHAVE=$(openssl rand -base64 32)

const enc = new TextEncoder();
const dec = new TextDecoder();

function b64(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

function deB64(texto: string): Uint8Array {
  return Uint8Array.from(atob(texto), (c) => c.charCodeAt(0));
}

let chaveCache: CryptoKey | null = null;

async function chave(): Promise<CryptoKey> {
  if (chaveCache) return chaveCache;
  const bruta = Deno.env.get("ROLOX_CHAVE");
  if (!bruta) throw new Error("segredo ROLOX_CHAVE não configurado");
  const bytes = deB64(bruta);
  if (bytes.length !== 32) throw new Error("ROLOX_CHAVE precisa ter 32 bytes");
  chaveCache = await crypto.subtle.importKey("raw", bytes, "AES-GCM", false, ["encrypt", "decrypt"]);
  return chaveCache;
}

/** Retorna base64(iv[12] || ciphertext). */
export async function cifrar(texto: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const c = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await chave(), enc.encode(texto)),
  );
  const tudo = new Uint8Array(iv.length + c.length);
  tudo.set(iv);
  tudo.set(c, iv.length);
  return b64(tudo);
}

export async function decifrar(base64: string): Promise<string> {
  const tudo = deB64(base64);
  const p = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: tudo.slice(0, 12) },
    await chave(),
    tudo.slice(12),
  );
  return dec.decode(p);
}
