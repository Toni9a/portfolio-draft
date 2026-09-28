import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { AwsClient } from "npm:aws4fetch@1.0.20";

// ---------------------------------------------------------------------------
// presign-media
// Given a list of R2 object keys (from inbox.stored_media), returns short-lived
// presigned GET URLs so the admin UI can display private-bucket images without
// ever exposing R2 credentials client-side. See second_brain_capture_prd.md Part 3.
//
// v4 (2026-09-28): verify_jwt alone accepts the public anon key, which meant
// anyone could presign any key in the private bucket (captures, voice notes).
// Now requires a signed-in user (or the service role key).
// ---------------------------------------------------------------------------

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const R2_ACCOUNT_ID = Deno.env.get("R2_ACCOUNT_ID")!;
const R2_ACCESS_KEY_ID = Deno.env.get("R2_ACCESS_KEY_ID")!;
const R2_SECRET_ACCESS_KEY = Deno.env.get("R2_SECRET_ACCESS_KEY")!;
const R2_BUCKET = Deno.env.get("R2_BUCKET") ?? "capture-media";
const R2_ENDPOINT = `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;

const EXPIRES_SECONDS = 3600; // 1 hour — plenty for a browsing session, short enough to not matter if cached/shared
const MAX_KEYS_PER_REQUEST = 200; // sanity cap, grid pages should never need more than this at once

const r2 = new AwsClient({
  service: "s3",
  region: "auto",
  accessKeyId: R2_ACCESS_KEY_ID,
  secretAccessKey: R2_SECRET_ACCESS_KEY,
});

// verify_jwt only proves the caller holds *a* valid JWT, and the public anon
// key (visible in the site's HTML) is one. So check for a signed-in user, or
// the service role key for server-side scripts.
const authClient = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!);
async function isAllowed(req: Request): Promise<boolean> {
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return false;
  if (token === Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) return true;
  const { data, error } = await authClient.auth.getUser(token);
  return !error && !!data?.user;
}

async function presignOne(key: string): Promise<string> {
  const url = `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}?X-Amz-Expires=${EXPIRES_SECONDS}`;
  const signed = await r2.sign(new Request(url), { aws: { signQuery: true } });
  return signed.url.toString();
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: corsHeaders });
  }
  if (!(await isAllowed(req))) {
    return new Response(JSON.stringify({ error: "Sign in required" }), { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  try {
    const body = await req.json();
    const keys: unknown = body?.keys;
    if (!Array.isArray(keys) || keys.some((k) => typeof k !== "string")) {
      return new Response(JSON.stringify({ error: "Body must be { keys: string[] }" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    if (keys.length === 0) {
      return new Response(JSON.stringify({ urls: {} }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    if (keys.length > MAX_KEYS_PER_REQUEST) {
      return new Response(
        JSON.stringify({ error: `Too many keys — max ${MAX_KEYS_PER_REQUEST} per request` }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const entries = await Promise.all(
      (keys as string[]).map(async (key) => [key, await presignOne(key)] as const),
    );
    const urls = Object.fromEntries(entries);

    return new Response(JSON.stringify({ urls, expiresIn: EXPIRES_SECONDS }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("presign-media error:", err);
    return new Response(JSON.stringify({ error: "Internal server error" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
