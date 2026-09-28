import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// semantic-search
// Admin-only. Embeds the query text with the SAME model/settings
// scripts/embed_nodes.py uses to embed every node (gemini-embedding-2, 768
// dims, SEMANTIC_SIMILARITY), then calls the existing match_nodes() RPC to
// rank nodes by cosine similarity. Powers Explore's "search by meaning" box.
//
// v3 (2026-09-28): verify_jwt alone accepts the public anon key, so anyone
// could spend Gemini credit and read the graph. Now requires a signed-in user
// (or the service role key).
// ---------------------------------------------------------------------------

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY")!;
const EMBEDDING_MODEL = Deno.env.get("GEMINI_EMBEDDING_MODEL") ?? "gemini-embedding-2";
const DIMS = 768; // must match the node.embedding vector(768) column and embed_nodes.py

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

async function embedQuery(text: string): Promise<number[]> {
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
  const json = await res.json();
  const values = json?.embedding?.values;
  if (!Array.isArray(values)) {
    throw new Error(`Embedding call failed (status ${res.status}): ${JSON.stringify(json).slice(0, 300)}`);
  }
  return values;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405, headers: corsHeaders });
  if (!(await isAllowed(req))) {
    return new Response(JSON.stringify({ error: "Sign in required" }), { status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" } });
  }

  try {
    const body = await req.json();
    const query: unknown = body?.query;
    if (typeof query !== "string" || !query.trim()) {
      return new Response(JSON.stringify({ error: "Body must be { query: string }" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    const matchCount = Math.min(Math.max(Number(body?.limit) || 25, 1), 50);

    const embedding = await embedQuery(query.trim());
    const { data, error } = await supabase.rpc("match_nodes", {
      query_embedding: embedding,
      match_count: matchCount,
    });
    if (error) throw error;

    return new Response(JSON.stringify({ results: data }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("semantic-search error:", err);
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
