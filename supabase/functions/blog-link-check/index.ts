import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// blog-link-check
// Admin-only. Runs a Gemini pass over a blog draft's body to
// (1) catch places where the text implies a link was going to be dropped in
//     ("I'll link this below", "see the video below") but no link appears,
// (2) suggest links/related things worth adding, from the post's own
//     source_urls/related_project_ids, the user's saved bookmarks (inbox.url)
//     and Gemini's general suggestions,
// (3) suggest a title and topic tags, and
// (4) since v4 (2026-09-23): suggest RELATED PROJECTS and RELATED TAKES from
//     the knowledge graph, by embedding the draft and running match_nodes().
//     This is the missing post -> project edge described in system_atlas.md
//     §6: related_project_ids is filled with portfolio/repo node source_ids,
//     commentary_ids with commentary ids. The editor shows them as chips that
//     Toni confirms; this function never writes.
//
// POST { post_id }
//   -> { missing_links, suggestions, suggested_title, suggested_tags,
//        related_projects: [{id, title, kind, similarity}],
//        related_takes: [{id, title, similarity}] }
// ---------------------------------------------------------------------------

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY")!;
const GEMINI_MODEL = "gemini-flash-latest";
const EMBEDDING_MODEL = Deno.env.get("GEMINI_EMBEDDING_MODEL") ?? "gemini-embedding-2";
const DIMS = 768;

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);
const authClient = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!);

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const BOOKMARK_CANDIDATE_LIMIT = 250;
const PROJECT_KINDS = new Set(["project", "venture", "repo"]);

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

// verify_jwt accepts the public anon key too; this spends Gemini credit and
// reads private tables with the service role, so require a signed-in user.
async function isSignedIn(req: Request): Promise<boolean> {
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return false;
  const { data, error } = await authClient.auth.getUser(token);
  return !error && !!data?.user;
}

async function callGemini(prompt: string): Promise<string> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: { responseMimeType: "application/json" },
      }),
    },
  );
  const j = await res.json();
  const out = j?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!out) throw new Error(`Gemini call failed (status ${res.status}): ${JSON.stringify(j).slice(0, 300)}`);
  return out;
}

async function embed(text: string): Promise<number[]> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${EMBEDDING_MODEL}:embedContent?key=${GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: `models/${EMBEDDING_MODEL}`,
        content: { parts: [{ text }] },
        taskType: "SEMANTIC_SIMILARITY",
        outputDimensionality: DIMS,
      }),
    },
  );
  const j = await res.json();
  const values = j?.embedding?.values;
  if (!Array.isArray(values)) throw new Error(`Embedding failed (status ${res.status})`);
  return values;
}

// Graph neighbours of the draft, split into projects and takes. Embeds the
// current text rather than reusing the draft's node embedding, because the
// node may not exist yet or may predate the latest edits.
async function relatedFromGraph(postId: string, title: string, bodyMd: string) {
  const text = `post\n${title || ""}\n${bodyMd.replace(/\[\[[a-z]+:[^\]]+\]\]/g, "")}`.slice(0, 6000);
  const vector = await embed(text);
  const { data: selfNode } = await supabase.from("node").select("id")
    .eq("source_table", "published_posts").eq("source_id", postId).maybeSingle();
  // match_nodes_by_kind does an exact scan. match_nodes goes through the HNSW
  // index, which only ever returns ~40 neighbours (mostly captures).
  const exclude = selfNode?.id ?? null;
  const [projects, takes] = await Promise.all([
    supabase.rpc("match_nodes_by_kind", { query_embedding: vector, kinds: [...PROJECT_KINDS], match_count: 6, exclude_node: exclude }),
    supabase.rpc("match_nodes_by_kind", { query_embedding: vector, kinds: ["commentary"], match_count: 5, exclude_node: exclude }),
  ]);
  if (projects.error) throw projects.error;
  if (takes.error) throw takes.error;
  const shape = (h: any) => ({ id: h.source_id, title: h.title, kind: h.kind, similarity: Number(Number(h.similarity).toFixed(3)) });
  const related_projects = (projects.data ?? []).map(shape);
  const related_takes = (takes.data ?? []).map(shape);
  return { related_projects, related_takes };
}

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

  const postId = body.post_id;
  if (!postId) return json({ error: "post_id required" }, 400);

  try {
    const { data: post, error: postErr } = await supabase
      .from("published_posts")
      .select("title, body_md, source_urls, related_project_ids, topic_tags")
      .eq("id", postId)
      .maybeSingle();
    if (postErr) throw postErr;
    if (!post) return json({ error: "Post not found" }, 404);

    const bodyMd: string = post.body_md || "";
    if (!bodyMd.trim()) {
      return json({
        missing_links: [],
        suggestions: [],
        suggested_title: null,
        suggested_tags: [],
        related_projects: [],
        related_takes: [],
        note: "Post body is empty. Nothing to check yet.",
      });
    }

    // Start the graph lookup in parallel with the Gemini pass.
    const relatedPromise = relatedFromGraph(postId, post.title, bodyMd).catch((err) => {
      console.error("related lookup failed (continuing):", err);
      return { related_projects: [], related_takes: [], related_error: String(err) };
    });

    const relatedIds: string[] = Array.isArray(post.related_project_ids) ? post.related_project_ids : [];
    let repoContext = "";
    if (relatedIds.length) {
      const { data: repos } = await supabase
        .from("github_sync_cache")
        .select("display_name, description, homepage_url")
        .in("display_name", relatedIds);
      if (repos?.length) {
        repoContext = repos
          .map((r: any) => `- ${r.display_name}: ${r.description || "(no description)"} (${r.homepage_url || "no live url"})`)
          .join("\n");
      }
    }

    const { data: bookmarks } = await supabase
      .from("inbox")
      .select("url, title, full_text, source, folder, created_at")
      .not("url", "is", null)
      .order("created_at", { ascending: false })
      .limit(BOOKMARK_CANDIDATE_LIMIT);
    let bookmarkContext = "";
    if (bookmarks?.length) {
      bookmarkContext = bookmarks
        .map((b: any) => {
          const preview = (b.title || b.full_text || "").toString().slice(0, 120);
          return `- ${b.url}${b.folder ? ` (${b.folder})` : ""}${preview ? `: ${preview}` : ""}`;
        })
        .join("\n");
    }

    const sourceUrls: string[] = Array.isArray(post.source_urls) ? post.source_urls : [];

    const prompt = `You are proofreading a personal blog post draft before it goes live on a portfolio site. Four jobs:

1. MISSING LINKS: Find phrases where the writer implies a link, reference, or resource is coming ("linked below", "I'll drop the link here", "see this video", "check out X", "more on that here", "the repo for this is") but no actual markdown link ([text](url)) appears near that phrase. Quote the exact sentence/phrase for each one found.

2. SUGGESTIONS: Suggest links or related things worth adding. Prefer, in this order: (a) one of the writer's OWN SAVED BOOKMARKS below if genuinely relevant to what the post discusses, (b) the "known project links" list if a project mentioned in the post matches one, (c) otherwise a generally relevant, genuinely useful external reference (docs, tools, articles). Do not invent fake URLs. Only suggest a URL if you're confident it's real (or copied verbatim from the lists below), otherwise suggest the resource by name with url: null and let the writer find the exact link.

3. TITLE: If the post's current title is missing, generic, or clearly a placeholder (e.g. "Untitled post"), suggest a short, specific title based on what the body actually says. If the current title already reads like a real, deliberate title, return null instead of overriding it. Never use em dashes.

4. TAGS: Suggest 2-6 short lowercase topic tags for the whole post: named companies/products/people, the specific claim or angle taken, not broad category words like "tech" or "ai" unless nothing more specific applies. Skip any tag already in EXISTING TAGS below.

The body uses a few editorial markers you should ignore: "## [LABEL] Heading" section headings, ">> " pull quotes, and [[voice:ID]] / [[cutout:ID]] tokens.

POST TITLE: ${post.title || "(untitled)"}

EXISTING TAGS: ${(post.topic_tags || []).length ? (post.topic_tags as string[]).join(", ") : "(none)"}

POST BODY (markdown):
"""
${bodyMd}
"""

ALREADY-LISTED SOURCE URLS (don't re-suggest these):
${sourceUrls.length ? sourceUrls.join("\n") : "(none)"}

KNOWN PROJECT LINKS (from this portfolio's own data, prefer these when relevant):
${repoContext || "(none)"}

YOUR SAVED BOOKMARKS (most recent ${BOOKMARK_CANDIDATE_LIMIT}; prefer suggesting one of these over a generic external link when genuinely relevant):
${bookmarkContext || "(none)"}

Respond ONLY with JSON in this exact shape:
{"missing_links": [{"quote": "...", "reason": "..."}], "suggestions": [{"label": "...", "url": "..."|null, "reason": "..."}], "suggested_title": "..."|null, "suggested_tags": ["...", "..."]}
Keep missing_links and suggestions short (max 6 items each) and only include genuinely useful items. Empty arrays are a fine and expected result for a clean, complete draft. suggested_tags max 6 items, empty array if EXISTING TAGS already cover it well.`;

    const raw = await callGemini(prompt);
    let parsed: any;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new Error(`Gemini returned non-JSON: ${raw.slice(0, 300)}`);
    }
    const related = await relatedPromise;

    return json({
      missing_links: Array.isArray(parsed.missing_links) ? parsed.missing_links : [],
      suggestions: Array.isArray(parsed.suggestions) ? parsed.suggestions : [],
      suggested_title: typeof parsed.suggested_title === "string" ? parsed.suggested_title.replace(/\s*[—–]\s*/g, ": ") : null,
      suggested_tags: Array.isArray(parsed.suggested_tags) ? parsed.suggested_tags.map(String) : [],
      ...related,
    });
  } catch (err) {
    console.error("blog-link-check error:", err);
    return json({ error: String(err) }, 500);
  }
});
