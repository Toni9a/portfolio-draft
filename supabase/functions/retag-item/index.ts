import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// retag-item
// Admin-only. Re-runs the current Gemini tagging prompt on one or more
// existing inbox rows, so items tagged before the prompt was tightened
// (specific entities/claims instead of generic categories) can be refreshed
// without waiting for new captures.
//
// Important: for links/bookmarks, inbox.full_text is often just the raw
// message text (sometimes just the URL itself) — low-signal. The real
// substance is usually in a linked commentary row (the "take" you attach
// after filing it, text or voice). So this pulls BOTH and tags off whichever
// has more content, preferring commentary when both exist.
//
// v6 (2026-09-28): verify_jwt alone accepts the public anon key, so anyone
// could spend Gemini credit and rewrite tags. Now requires a signed-in user
// (or the service role key).
// ---------------------------------------------------------------------------

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY")!;
const GEMINI_MODEL = "gemini-flash-latest";

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
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

async function callGemini(text: string): Promise<string> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text }] }],
        generationConfig: { responseMimeType: "application/json" },
      }),
    },
  );
  const json = await res.json();
  const out = json?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!out) {
    throw new Error(`Gemini call failed (status ${res.status}): ${JSON.stringify(json).slice(0, 300)}`);
  }
  return out;
}

async function tagText(text: string): Promise<string[]> {
  const raw = await callGemini(
    `Suggest 2-5 short lowercase tags for this note: "${text}". ` +
      "Pull tags from the SPECIFIC content — named entities, products, people — and the " +
      "specific claim or angle, not broad category words like 'tech' or 'news' unless " +
      "nothing more specific applies. Prefer multi-word tags with hyphens over vague single " +
      'words. Respond ONLY with JSON: {"tags": ["...", "..."]}',
  );
  const parsed = JSON.parse(raw);
  return Array.isArray(parsed.tags) ? parsed.tags.map(String) : [];
}

// Heuristic: is this string substantive prose, or just a bare URL / near-empty caption?
function isLowSignal(text: string | null | undefined): boolean {
  if (!text) return true;
  const stripped = text.replace(/https?:\/\/\S+/gi, "").trim();
  return stripped.length < 20; // basically nothing left once the URL is removed
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

  let body: any;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Bad request body" }), { status: 400, headers: corsHeaders });
  }

  const ids: string[] = Array.isArray(body.ids) ? body.ids : body.id ? [body.id] : [];
  if (!ids.length) {
    return new Response(JSON.stringify({ error: "Provide id or ids" }), { status: 400, headers: corsHeaders });
  }

  const { data: rows, error: fetchErr } = await supabase
    .from("inbox")
    .select("id, full_text, url")
    .in("id", ids);

  if (fetchErr) {
    return new Response(JSON.stringify({ error: fetchErr.message }), { status: 500, headers: corsHeaders });
  }

  const { data: commentaryRows } = await supabase
    .from("commentary")
    .select("inbox_ids, body, created_at")
    .overlaps("inbox_ids", ids)
    .order("created_at", { ascending: false });

  const commentaryByItem: Record<string, string> = {};
  (commentaryRows ?? []).forEach((c: any) => {
    (c.inbox_ids ?? []).forEach((id: string) => {
      if (!commentaryByItem[id]) commentaryByItem[id] = c.body; // most recent wins, list is already sorted desc
    });
  });

  const results: Record<string, string[] | null> = {};

  for (const row of rows ?? []) {
    const commentaryText = commentaryByItem[row.id];
    // Prefer whichever text is actually substantive; commentary (the "take")
    // usually carries more signal than a link's raw caption.
    let textToTag: string | null = null;
    if (commentaryText && !isLowSignal(commentaryText)) {
      textToTag = row.full_text && !isLowSignal(row.full_text)
        ? `${row.full_text}\n\n${commentaryText}`
        : commentaryText;
    } else if (row.full_text && !isLowSignal(row.full_text)) {
      textToTag = row.full_text;
    } else if (commentaryText) {
      textToTag = commentaryText; // better than nothing even if short
    }

    if (!textToTag) {
      results[row.id] = null; // nothing substantive to tag from
      continue;
    }
    try {
      const tags = await tagText(textToTag);
      await supabase.from("inbox").update({ topic_tags: tags }).eq("id", row.id);
      results[row.id] = tags;
    } catch (err) {
      console.error(`Retag failed for ${row.id}:`, err);
      results[row.id] = null;
    }
  }

  return new Response(JSON.stringify({ results }), {
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
});
