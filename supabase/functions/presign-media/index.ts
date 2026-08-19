import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { AwsClient } from "npm:aws4fetch@1.0.20";

// ---------------------------------------------------------------------------
// presign-media
// Given a list of R2 object keys (from inbox.stored_media), returns short-lived
// presigned GET URLs so the admin UI can display private-bucket images without
// ever exposing R2 credentials client-side. See second_brain_capture_prd.md Part 3.
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

  // Auth is enforced at the platform level (verify_jwt: true on this function) —
  // Supabase rejects unauthenticated calls before this handler ever runs, matching
  // the admin.html auth screen that signs users in via Supabase auth first.
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
