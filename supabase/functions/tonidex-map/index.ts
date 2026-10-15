import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { AwsClient } from "npm:aws4fetch@1.0.20";

// ---------------------------------------------------------------------------
// tonidex-map  (2026-10-15)
// Feeds /tonidex, the visual mind map of the second brain.
// Signed-in user (or service role) only: verify_jwt alone accepts the public
// anon key, so we check for a real user here. Returns the output of the
// service-role-only SQL function tonidex_map_data() plus a 1-hour presigned
// R2 URL for every image. Read only; writes nothing.
// ---------------------------------------------------------------------------

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(SUPABASE_URL, SERVICE_KEY);
const authClient = createClient(SUPABASE_URL, Deno.env.get("SUPABASE_ANON_KEY")!);

const R2_ACCOUNT_ID = Deno.env.get("R2_ACCOUNT_ID") ?? "";
const R2_BUCKET = Deno.env.get("R2_BUCKET") ?? "capture-media";
const R2_ENDPOINT = `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;
const r2 = new AwsClient({
  service: "s3",
  region: "auto",
  accessKeyId: Deno.env.get("R2_ACCESS_KEY_ID") ?? "",
  secretAccessKey: Deno.env.get("R2_SECRET_ACCESS_KEY") ?? "",
});

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

async function isAllowed(req: Request): Promise<boolean> {
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return false;
  if (token === SERVICE_KEY) return true;
  const { data, error } = await authClient.auth.getUser(token);
  return !error && !!data?.user;
}

const objUrl = (key: string) => `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}`;
async function presign(key: string): Promise<string> {
  const signed = await r2.sign(new Request(`${objUrl(key)}?X-Amz-Expires=3600`), { aws: { signQuery: true } });
  return signed.url.toString();
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (!(await isAllowed(req))) return json({ error: "Sign in required" }, 401);
  try {
    const { data, error } = await supabase.rpc("tonidex_map_data");
    if (error) throw error;
    const items = (data?.items ?? []) as Array<Record<string, unknown>>;
    await Promise.all(items.map(async (it) => {
      const k = it.image_key as string | null;
      it.img = k ? await presign(k) : null;
      delete it.image_key;
    }));
    return json({ ...data, items, generated_at: new Date().toISOString() });
  } catch (err) {
    console.error("tonidex-map error:", err);
    return json({ error: String((err as Error)?.message ?? err) }, 500);
  }
});
