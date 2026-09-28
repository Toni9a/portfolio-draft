import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { AwsClient } from "npm:aws4fetch@1.0.20";

// ---------------------------------------------------------------------------
// backfill-voice-audio
// Admin-only. One-off/rerunnable: finds inbox rows with
// raw_message_type='voice' and no voice_audio_path yet, pulls the file_id
// out of the archived raw_data (Telegram file_ids remain valid for bots
// indefinitely), re-downloads the audio via the bot API, and archives it to
// R2 under voice/<inboxId>.<ext> — same layout telegram-ingest v19+ uses for
// new voice notes going forward.
//
// POST {} -> backfills every eligible row
// POST { ids: ["...", "..."] } -> backfills only those rows (still requires
//   them to be raw_message_type='voice' with a file_id in raw_data)
// -> { processed: N, archived: N, skipped: [{id, reason}], failed: [{id, error}] }
//
// v4 (2026-09-28): verify_jwt alone accepts the public anon key. Now requires
// a signed-in user (or the service role key).
// ---------------------------------------------------------------------------

const TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN")!;

const R2_ACCOUNT_ID = Deno.env.get("R2_ACCOUNT_ID")!;
const R2_ACCESS_KEY_ID = Deno.env.get("R2_ACCESS_KEY_ID")!;
const R2_SECRET_ACCESS_KEY = Deno.env.get("R2_SECRET_ACCESS_KEY")!;
const R2_BUCKET = Deno.env.get("R2_BUCKET") ?? "capture-media";
const R2_ENDPOINT = `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;
const r2 = new AwsClient({ service: "s3", region: "auto", accessKeyId: R2_ACCESS_KEY_ID, secretAccessKey: R2_SECRET_ACCESS_KEY });

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

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

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

// Telegram file_path isn't guaranteed to carry a real extension (some voice
// paths come back as e.g. "voice/file_15" with no dot at all) — naive
// split(".").pop() silently returns the WHOLE path in that case, corrupting
// the R2 key. Only trust a dot that's after the last slash and short enough
// to plausibly be an extension.
function extractExt(filePath: string): string {
  const base = filePath.split("/").pop() || filePath;
  const dotIdx = base.lastIndexOf(".");
  if (dotIdx === -1) return "oga";
  const candidate = base.slice(dotIdx + 1).toLowerCase().replace(/[^a-z0-9]/g, "");
  if (!candidate || candidate.length > 5) return "oga";
  return candidate;
}

async function tgGetFile(fileId: string): Promise<{ file_path?: string } | null> {
  const res = await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getFile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_id: fileId }),
  });
  const j = await res.json();
  if (!j.ok) {
    console.error("getFile failed:", JSON.stringify(j));
    return null;
  }
  return j.result;
}

async function uploadVoiceToR2(inboxId: string, bytes: Uint8Array, ext: string, mime: string): Promise<string | null> {
  const key = `voice/${inboxId}.${ext}`;
  const putUrl = `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}`;
  const signed = await r2.sign(new Request(putUrl, { method: "PUT", body: bytes, headers: { "Content-Type": mime } }));
  const res = await fetch(signed);
  if (!res.ok) {
    console.error("Voice R2 upload failed:", res.status, await res.text());
    return null;
  }
  return key;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);
  if (!(await isAllowed(req))) return json({ error: "Sign in required" }, 401);

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    // empty body is fine — backfill everything eligible
  }

  const onlyIds: string[] | null = Array.isArray(body.ids) ? body.ids : null;

  try {
    let query = supabase
      .from("inbox")
      .select("id, raw_data")
      .eq("raw_message_type", "voice")
      .is("voice_audio_path", null);
    if (onlyIds) query = query.in("id", onlyIds);

    const { data: rows, error } = await query;
    if (error) throw error;

    const skipped: { id: string; reason: string }[] = [];
    const failed: { id: string; error: string }[] = [];
    let archived = 0;

    for (const row of rows ?? []) {
      const fileId = row.raw_data?.voice?.file_id;
      if (!fileId) {
        skipped.push({ id: row.id, reason: "no file_id in raw_data" });
        continue;
      }
      try {
        const fileInfo = await tgGetFile(fileId);
        const filePath = fileInfo?.file_path;
        if (!filePath) {
          failed.push({ id: row.id, error: "Telegram getFile returned no file_path (file may have expired server-side)" });
          continue;
        }
        const fileUrl = `https://api.telegram.org/file/bot${TELEGRAM_BOT_TOKEN}/${filePath}`;
        const res = await fetch(fileUrl);
        if (!res.ok) {
          failed.push({ id: row.id, error: `download failed: ${res.status}` });
          continue;
        }
        const bytes = new Uint8Array(await res.arrayBuffer());
        const ext = extractExt(filePath);
        const mime = ext === "oga" || ext === "ogg" ? "audio/ogg" : `audio/${ext}`;

        const voicePath = await uploadVoiceToR2(row.id, bytes, ext, mime);
        if (!voicePath) {
          failed.push({ id: row.id, error: "R2 upload failed" });
          continue;
        }

        const { error: updateErr } = await supabase.from("inbox").update({ voice_audio_path: voicePath }).eq("id", row.id);
        if (updateErr) {
          failed.push({ id: row.id, error: `db update failed: ${updateErr.message}` });
          continue;
        }
        archived++;
      } catch (err) {
        failed.push({ id: row.id, error: String(err) });
      }
    }

    return json({ processed: (rows ?? []).length, archived, skipped, failed });
  } catch (err) {
    console.error("backfill-voice-audio error:", err);
    return json({ error: String(err) }, 500);
  }
});
