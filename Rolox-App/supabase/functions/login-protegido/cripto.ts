// Criptografia AES-GCM + base64 para senhas tentadas e credenciais de backup.
// Chave: segredo ROLOX_CHAVE (opcional) ou derivada da service role key.

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

// A chave AES vem do segredo ROLOX_CHAVE, se existir. Se não existir, é gerada
// a partir da SUPABASE_SERVICE_ROLE_KEY (que o Supabase já entrega às funções
// e nunca sai do servidor): SHA-256 dela = 32 bytes. Assim não é preciso
// configurar nenhum segredo extra.
async function chave(): Promise<CryptoKey> {
  if (chaveCache) return chaveCache;
  let bytes: Uint8Array;
  const bruta = Deno.env.get("ROLOX_CHAVE");
  if (bruta) {
    bytes = deB64(bruta);
    if (bytes.length !== 32) throw new Error("ROLOX_CHAVE precisa ter 32 bytes");
  } else {
    const base = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!base) throw new Error("sem chave de criptografia");
    bytes = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode("rolox-cripto:" + base)));
  }
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
