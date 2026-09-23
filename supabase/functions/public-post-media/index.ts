import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { AwsClient } from "npm:aws4fetch@1.0.20";

// ---------------------------------------------------------------------------
// public-post-media
// Public (verify_jwt: false). Lets blog.html show the cutouts and images of a
// PUBLISHED post. The R2 bucket is private, so this presigns short-lived GET
// URLs, with the same safety shape as public-voice-presign: only for a post
// that is actually published, and only for media whose [[cutout:ID]] or
// [[image:ID]] token literally appears in that post's body_md. Drafts and
// unreferenced uploads are never exposed.
//
// POST { post_id } -> { media: { [id]: { url, alt, placement, kind } } }
// ---------------------------------------------------------------------------

const R2_ACCOUNT_ID = Deno.env.get("R2_ACCOUNT_ID")!;
const R2_BUCKET = Deno.env.get("R2_BUCKET") ?? "capture-media";
const R2_ENDPOINT = `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;
const EXPIRES_SECONDS = 3600;

const r2 = new AwsClient({
  service: "s3",
  region: "auto",
  accessKeyId: Deno.env.get("R2_ACCESS_KEY_ID")!,
  secretAccessKey: Deno.env.get("R2_SECRET_ACCESS_KEY")!,
});

const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...corsHeaders, "Content-Type": "application/json" } });
}

async function presignGet(key: string): Promise<string> {
  const url = `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}?X-Amz-Expires=${EXPIRES_SECONDS}`;
  const signed = await r2.sign(new Request(url), { aws: { signQuery: true } });
  return signed.url.toString();
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);
  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "Bad request body" }, 400);
  }
  const postId = body.post_id;
  if (!postId || typeof postId !== "string") return json({ error: "post_id required" }, 400);

  try {
    const { data: post } = await supabase.from("published_posts")
      .select("body_md, published_at").eq("id", postId).maybeSingle();
    const live = !!post?.published_at && new Date(post.published_at).getTime() <= Date.now();
    if (!post || !live) return json({ media: {} });

    const ids = [...new Set([...(post.body_md || "").matchAll(/\[\[(?:cutout|image):([0-9a-f-]{36})\]\]/g)].map((m) => m[1]))];
    if (!ids.length) return json({ media: {} });

    const { data: rows, error } = await supabase.from("post_media")
      .select("id, storage_path, alt, caption, placement, kind").eq("post_id", postId).in("id", ids);
    if (error) throw error;

    const entries = await Promise.all((rows ?? []).map(async (r: any) => [r.id, {
      url: await presignGet(r.storage_path),
      alt: r.alt ?? r.caption ?? "",
      placement: r.placement,
      kind: r.kind,
    }] as const));
    return json({ media: Object.fromEntries(entries) });
  } catch (err) {
    console.error("public-post-media error:", err);
    return json({ error: String(err) }, 500);
  }
});
