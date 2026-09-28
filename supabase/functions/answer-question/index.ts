import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-shortcut-key",
};

/**
 * answer-question
 * POST body: { question_id: string, answer: string }
 * Also supports: GET ?project_id=xxx  → returns unanswered questions for that project
 *
 * v10 (2026-09-28): verify_jwt alone let anyone with the public anon key read
 * and overwrite answers. Now requires one of: a signed-in user, the service
 * role key, or the iOS Shortcut's `x-shortcut-key` header (its SHA-256 is in
 * public.function_keys as 'answer-question-shortcut'; the key itself is
 * SHORTCUT_KEY in .env). See scripts/ios_shortcut_guide.md.
 */
const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);
const authClient = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!);

async function sha256(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function isAllowed(req: Request): Promise<boolean> {
  const shortcutKey = req.headers.get("x-shortcut-key");
  if (shortcutKey) {
    const { data } = await supabase.from("function_keys").select("key_sha256").eq("name", "answer-question-shortcut").maybeSingle();
    return !!data && data.key_sha256 === (await sha256(shortcutKey));
  }
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return false;
  if (token === Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")) return true;
  const { data, error } = await authClient.auth.getUser(token);
  return !error && !!data?.user;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (!(await isAllowed(req))) {
    return new Response(JSON.stringify({ error: "Sign in required" }), { status: 401, headers: { ...cors, "Content-Type": "application/json" } });
  }

  const url = new URL(req.url);

  // GET — return unanswered questions, optionally filtered by project
  if (req.method === "GET") {
    const projectId = url.searchParams.get("project_id");
    let query = supabase
      .from("project_qna_sessions")
      .select("id, project_id, question, answer, created_at")
      .is("answer", null)
      .order("created_at");
    if (projectId) query = query.eq("project_id", projectId);
    const { data, error } = await query;
    if (error) return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
    return new Response(JSON.stringify({ questions: data }), { headers: { ...cors, "Content-Type": "application/json" } });
  }

  // POST — save an answer
  if (req.method === "POST") {
    const body = await req.json();
    const { question_id, answer } = body;
    if (!question_id || !answer) {
      return new Response(JSON.stringify({ error: "question_id and answer required" }), { status: 400, headers: { ...cors, "Content-Type": "application/json" } });
    }
    const { error } = await supabase
      .from("project_qna_sessions")
      .update({ answer, answered_at: new Date().toISOString() })
      .eq("id", question_id);
    if (error) return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: { ...cors, "Content-Type": "application/json" } });
    return new Response(JSON.stringify({ success: true }), { headers: { ...cors, "Content-Type": "application/json" } });
  }

  return new Response("Method not allowed", { status: 405, headers: cors });
});
