import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { AwsClient } from "npm:aws4fetch@1.0.20";

// ---------------------------------------------------------------------------
// admin-post-media
// Admin-only. Uploads an image or editorial cutout for a blog draft/post into
// R2 (same bucket/credentials as presign-media) and records it in
// public.post_media, updates its metadata, lists, or deletes one. Returns
// presigned GET URLs so the admin UI can preview without a second round trip.
//
// POST { action: "upload", post_id, filename, contentBase64, contentType,
//        caption?, kind?, alt?, placement?, inspired_by?, prompt? } -> { row, url }
// POST { action: "update", id, alt?, placement?, caption?, inspired_by? } -> { row }
// POST { action: "import_url", post_id, url, kind?, alt?, placement? } -> { row, url }
//   fetches an image from the web (logo, screenshot) and stores a copy
// POST { action: "delete", id } -> { ok: true }
// POST { action: "list", post_id } -> { rows: [{...with url}] }
//
// v3 (2026-09-23): cutout metadata (kind/alt/placement/inspired_by/prompt),
// the "update" action, and a signed-in-user check (verify_jwt alone also
// accepts the public anon key).
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
const EXPIRES_SECONDS = 3600;
const MAX_BYTES = 8 * 1024 * 1024;

const r2 = new AwsClient({ service: "s3", region: "auto", accessKeyId: R2_ACCESS_KEY_ID, secretAccessKey: R2_SECRET_ACCESS_KEY });
const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
const authClient = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!);

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });
}

async function isSignedIn(req: Request): Promise<boolean> {
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return false;
  const { data, error } = await authClient.auth.getUser(token);
  return !error && !!data?.user;
}

async function presignGet(key: string): Promise<string> {
  const url = `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}?X-Amz-Expires=${EXPIRES_SECONDS}`;
  const signed = await r2.sign(new Request(url), { aws: { signQuery: true } });
  return signed.url.toString();
}

function safeExt(filename: string, contentType: string): string {
  const fromName = (filename.split(".").pop() || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  if (fromName && fromName.length <= 5) return fromName;
  if (contentType.includes("png")) return "png";
  if (contentType.includes("webp")) return "webp";
  if (contentType.includes("gif")) return "gif";
  return "jpg";
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64.includes(",") ? b64.split(",", 2)[1] : b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

const PLACEMENTS = new Set(["lead", "left", "right"]);
const cleanPlacement = (p: unknown) => (typeof p === "string" && PLACEMENTS.has(p) ? p : null);

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);
  if (!(await isSignedIn(req))) return json({ error: "Sign in required" }, 401);

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Bad request body" }, 400);
  }

  try {
    if (body.action === "list") {
      if (!body.post_id) return json({ error: "post_id required" }, 400);
      const { data: rows, error } = await supabase.from("post_media").select("*")
        .eq("post_id", body.post_id).order("sort_order", { ascending: true });
      if (error) throw error;
      const withUrls = await Promise.all((rows ?? []).map(async (r: any) => ({ ...r, url: await presignGet(r.storage_path) })));
      return json({ rows: withUrls });
    }

    if (body.action === "update") {
      if (!body.id) return json({ error: "id required" }, 400);
      const patch: Record<string, unknown> = {};
      for (const k of ["alt", "caption", "inspired_by"]) if (k in body) patch[k] = body[k] ?? null;
      if ("placement" in body) patch.placement = cleanPlacement(body.placement);
      const { data: row, error } = await supabase.from("post_media").update(patch).eq("id", body.id).select().single();
      if (error) throw error;
      return json({ row });
    }

    if (body.action === "delete") {
      if (!body.id) return json({ error: "id required" }, 400);
      const { data: row, error: fetchErr } = await supabase.from("post_media").select("storage_path").eq("id", body.id).maybeSingle();
      if (fetchErr) throw fetchErr;
      if (row) {
        const delUrl = `${R2_ENDPOINT}/${R2_BUCKET}/${row.storage_path.split("/").map(encodeURIComponent).join("/")}`;
        const signedDel = await r2.sign(new Request(delUrl, { method: "DELETE" }));
        await fetch(signedDel).catch((e) => console.error("R2 delete failed (non-fatal):", e));
      }
      const { error: delErr } = await supabase.from("post_media").delete().eq("id", body.id);
      if (delErr) throw delErr;
      return json({ ok: true });
    }

    if (body.action === "import_url") {
      const { post_id, url } = body;
      if (!post_id || typeof url !== "string" || !/^https?:\/\//i.test(url)) return json({ error: "post_id and an http(s) url required" }, 400);
      const res = await fetch(url, { redirect: "follow", headers: { "User-Agent": "toniesan.com blog image import" } });
      if (!res.ok) return json({ error: `the site answered ${res.status}` }, 400);
      const type = (res.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
      if (!type.startsWith("image/")) return json({ error: `that link is not an image (${type || "unknown type"})` }, 400);
      const bytes = new Uint8Array(await res.arrayBuffer());
      if (bytes.byteLength > MAX_BYTES) return json({ error: "Image too large (max 8MB)" }, 400);
      const name = new URL(url).pathname.split("/").pop() || "image";
      const ext = safeExt(name, type);
      const key = `blog/${post_id}/${Date.now()}-${crypto.randomUUID().slice(0, 8)}.${ext}`;
      const putUrl = `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}`;
      const signedPut = await r2.sign(new Request(putUrl, { method: "PUT", body: bytes, headers: { "Content-Type": type } }));
      const putRes = await fetch(signedPut);
      if (!putRes.ok) throw new Error(`R2 upload failed: ${putRes.status} ${await putRes.text()}`);
      const { data: countRows } = await supabase.from("post_media").select("sort_order").eq("post_id", post_id)
        .order("sort_order", { ascending: false }).limit(1);
      const { data: inserted, error: insertErr } = await supabase.from("post_media").insert({
        post_id,
        storage_path: key,
        caption: null,
        sort_order: (countRows?.[0]?.sort_order ?? -1) + 1,
        kind: body.kind === "cutout" ? "cutout" : "image",
        alt: body.alt || null,
        placement: cleanPlacement(body.placement),
        inspired_by: `imported from ${url}`.slice(0, 500),
        prompt: null,
      }).select().single();
      if (insertErr) throw insertErr;
      return json({ row: inserted, url: await presignGet(key) });
    }

    if (body.action === "upload") {
      const { post_id, filename, contentBase64, contentType, caption } = body;
      if (!post_id || !contentBase64) return json({ error: "post_id and contentBase64 required" }, 400);
      const bytes = base64ToBytes(contentBase64);
      if (bytes.byteLength > MAX_BYTES) return json({ error: "Image too large (max 8MB)" }, 400);

      const ext = safeExt(filename || "", contentType || "image/jpeg");
      const key = `blog/${post_id}/${Date.now()}-${crypto.randomUUID().slice(0, 8)}.${ext}`;
      const putUrl = `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}`;
      const signedPut = await r2.sign(new Request(putUrl, { method: "PUT", body: bytes, headers: { "Content-Type": contentType || "image/jpeg" } }));
      const putRes = await fetch(signedPut);
      if (!putRes.ok) throw new Error(`R2 upload failed: ${putRes.status} ${await putRes.text()}`);

      const { data: countRows } = await supabase.from("post_media").select("sort_order").eq("post_id", post_id)
        .order("sort_order", { ascending: false }).limit(1);
      const nextSort = (countRows?.[0]?.sort_order ?? -1) + 1;

      const { data: inserted, error: insertErr } = await supabase.from("post_media").insert({
        post_id,
        storage_path: key,
        caption: caption || null,
        sort_order: nextSort,
        kind: body.kind === "cutout" ? "cutout" : "image",
        alt: body.alt || null,
        placement: cleanPlacement(body.placement),
        inspired_by: body.inspired_by || null,
        prompt: body.prompt || null,
      }).select().single();
      if (insertErr) throw insertErr;

      return json({ row: inserted, url: await presignGet(key) });
    }

    return json({ error: "Unknown action" }, 400);
  } catch (err) {
    console.error("admin-post-media error:", err);
    return json({ error: String(err) }, 500);
  }
});
