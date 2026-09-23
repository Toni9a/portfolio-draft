import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// blog-studio
// Admin-only (verify_jwt: true). The Gemini passes behind the editorial blog
// editor in admin.html. Never writes to the database: every result comes back
// to the editor as a proposal that Toni applies (or not) himself.
//
// POST { action: "shape", transcript, title? }
//   -> { title, deck, lead_note, sections: [{label, heading, paragraphs[]}],
//        pull_quote, filed_under[], body_md, warnings[] }
//   Turns a voice-note transcript into the editorial structure from
//   SITE-HANDOFF.md while keeping Toni's words verbatim.
//
// POST { action: "cutout_ideas", title, body_md }
//   -> { ideas: [{idea, passage, placement, alt, after_section}] }   (0-3 ideas)
//
// POST { action: "generate_cutout", title, passage, idea, placement,
//        style_refs?: [{ mime, data }] }
//   -> { image_base64, mime, prompt, model }
//   style_refs are the supplied prototype cutouts (assets/blog/style-refs),
//   sent as style references only, as SITE-HANDOFF.md asks.
//   The image comes back on a flat chroma-green ground. Gemini image models do
//   not return real alpha, so admin.html keys the green out on a canvas and
//   uploads a genuine transparent PNG (no CSS blend-mode tricks).
//
// POST { action: "models" } -> { models: [...] }   (diagnostics)
// ---------------------------------------------------------------------------

const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY")!;
const TEXT_MODEL = Deno.env.get("BLOG_TEXT_MODEL") ?? "gemini-flash-latest";
const IMAGE_MODELS = (Deno.env.get("BLOG_IMAGE_MODELS") ??
  "gemini-3.1-flash-image,gemini-2.5-flash-image,gemini-3-pro-image").split(",").map((s) => s.trim()).filter(Boolean);
const API = "https://generativelanguage.googleapis.com/v1beta";

// verify_jwt only proves the caller holds *a* valid JWT, and the public anon
// key is one. These actions spend Gemini credit, so require a signed-in user.
const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_ANON_KEY")!);
async function isSignedIn(req: Request): Promise<boolean> {
  const token = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token) return false;
  const { data, error } = await supabase.auth.getUser(token);
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

async function geminiJson(prompt: string): Promise<any> {
  const res = await fetch(`${API}/models/${TEXT_MODEL}:generateContent?key=${GEMINI_API_KEY}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      generationConfig: { responseMimeType: "application/json", temperature: 0.3 },
    }),
  });
  const j = await res.json();
  const out = j?.candidates?.[0]?.content?.parts?.map((p: any) => p.text || "").join("");
  if (!out) throw new Error(`Gemini call failed (status ${res.status}): ${JSON.stringify(j).slice(0, 300)}`);
  try {
    return JSON.parse(out);
  } catch {
    throw new Error(`Gemini returned non-JSON: ${out.slice(0, 300)}`);
  }
}

// ---- house rules ----------------------------------------------------------

// No em or en dashes anywhere in blog copy (SITE-HANDOFF.md). A spaced dash
// reads as a pause, so it becomes a comma; an unspaced one inside a range or
// compound becomes a hyphen.
function stripDashes(s: string): { text: string; count: number } {
  let count = 0;
  const text = (s || "")
    .replace(/\s*[—–]\s*(?=\S)/g, (m) => {
      count++;
      return /\s/.test(m) ? ", " : "-";
    })
    .replace(/[—–]/g, () => {
      count++;
      return ",";
    });
  return { text, count };
}

const norm = (s: string) =>
  (s || "").toLowerCase().replace(/[‘’]/g, "'").replace(/[^a-z0-9' ]+/g, " ").replace(/\s+/g, " ").trim();

// Words in `shaped` that never appear in `source`. Cheap, but it catches the
// failure that matters: Gemini adding its own vocabulary.
function addedWords(source: string, shaped: string): string[] {
  // British/American spellings count as the same word (optimisation/optimization).
  const canon = (w: string) => w.replace(/is(e|es|ed|ing|ation|ations)$/, "iz$1").replace(/ys(e|es|ed|ing)$/, "yz$1");
  const have = new Set(norm(source).split(" ").map(canon));
  const out = new Set<string>();
  for (const w of norm(shaped).split(" ")) if (w && !have.has(canon(w))) out.add(w);
  return [...out];
}

function toMarkdown(s: any): string {
  const parts: string[] = [];
  if (s.lead_note) parts.push(`> ${s.lead_note.trim()}`);
  const sections = Array.isArray(s.sections) ? s.sections : [];
  const quoteAfter = Number.isInteger(s.pull_quote_after_section) ? s.pull_quote_after_section : 1;
  sections.forEach((sec: any, i: number) => {
    const label = (sec.label || "").trim();
    parts.push(`## ${label ? `[${label}] ` : ""}${(sec.heading || "").trim()}`);
    (sec.paragraphs || []).forEach((p: string) => p && parts.push(p.trim()));
    if (s.pull_quote && i === Math.min(quoteAfter, sections.length - 1)) parts.push(`>> ${s.pull_quote.trim()}`);
  });
  return parts.join("\n\n") + "\n";
}

// ---- actions --------------------------------------------------------------

async function shape(body: any) {
  const transcript: string = (body.transcript || "").trim();
  if (transcript.length < 20) return json({ error: "Transcript is too short to shape." }, 400);

  const prompt = `You are editing one of Toni Esan's voice notes into a short blog essay for his personal site. The page is a dark editorial layout with: a title, a one-sentence deck, an opening "quick take" paper note, 2 to 5 numbered sections (each with a short uppercase-style label and a descriptive heading), and exactly one pull quote.

THE ONE RULE THAT MATTERS: keep Toni's original words verbatim as much as possible.
- You may: fix clear transcription mistakes; remove accidental duplicated words and false starts ("it it", "Are the most Are most", "we kind of do We kind of"); add punctuation and paragraph breaks; split long run-ons into sentences; write short descriptive section headings and labels.
- You may NOT: invent claims, examples, facts or conclusions; turn uncertainty into certainty; add transitions or summaries he did not say; polish the language into a corporate voice; reorder the argument unless a section clearly belongs elsewhere.
- Keep natural phrases like "I think", "kind of", "I guess" where they carry meaning.
- The lead note and the pull quote must be words Toni actually said (lightly cleaned as above), never paraphrase.
- Every sentence of the transcript should end up somewhere in the lead note or a section, except pure filler.
- Headings, labels and the deck are the only places you write new words. Keep them plain, specific and short. The title may reuse his existing title if it is good.
- Never use em dashes or en dashes anywhere. Use a full stop, comma, colon, semicolon or parentheses instead.
- British English spelling (optimisation, analysing).

${body.title && !/^untitled/i.test(body.title) ? `CURRENT TITLE: ${body.title}\n` : ""}
TRANSCRIPT:
"""
${transcript}
"""

Respond ONLY with JSON:
{"title": "...", "title_emphasis": "a 1-4 word phrase from the title to italicise, or null",
 "deck": "one sentence, ideally his own words",
 "lead_note": "the opening quick take, 1-2 of his sentences",
 "sections": [{"label": "THE SOURCE", "heading": "When websites stop being enough", "paragraphs": ["...", "..."]}],
 "pull_quote": "one striking sentence he said", "pull_quote_after_section": 1,
 "filed_under": ["2-4 short topic words for the footer"]}`;

  const s = await geminiJson(prompt);
  const warnings: string[] = [];

  // House-rule pass over every string field.
  let dashes = 0;
  const clean = (v: string) => {
    const r = stripDashes(v || "");
    dashes += r.count;
    return r.text;
  };
  s.title = clean(s.title);
  s.deck = clean(s.deck);
  s.lead_note = clean(s.lead_note);
  s.pull_quote = clean(s.pull_quote);
  s.sections = (Array.isArray(s.sections) ? s.sections : []).map((sec: any) => ({
    label: clean(sec.label).toUpperCase(),
    heading: clean(sec.heading),
    paragraphs: (sec.paragraphs || []).map((p: string) => clean(p)).filter(Boolean),
  }));
  if (dashes) warnings.push(`Replaced ${dashes} em/en dash${dashes === 1 ? "" : "es"} with commas.`);

  if (s.title_emphasis && s.title && s.title.includes(s.title_emphasis)) {
    s.title_md = s.title.replace(s.title_emphasis, `*${s.title_emphasis}*`);
  } else {
    s.title_md = s.title;
  }

  const bodyText = [s.lead_note, s.pull_quote, ...s.sections.flatMap((x: any) => x.paragraphs)].join(" ");
  const added = addedWords(transcript, bodyText);
  if (added.length) warnings.push(`Words in the body that are not in the transcript: ${added.slice(0, 25).join(", ")}${added.length > 25 ? "…" : ""}`);
  if (s.pull_quote && addedWords(transcript, s.pull_quote).length) warnings.push("The pull quote contains words Toni did not say. Check it.");

  s.body_md = toMarkdown(s);
  s.added_words = added;
  s.warnings = warnings;
  s.model = TEXT_MODEL;
  return json(s);
}

async function cutoutIdeas(body: any) {
  const text = (body.body_md || "").trim();
  if (text.length < 40) return json({ ideas: [], note: "Not enough text to illustrate yet." });
  const prompt = `You are art-directing illustrations for a short essay on Toni Esan's blog. The house style is handmade editorial collage cutouts (cream paper, ink outlines, halftone, muted cornflower blue, dusty cyan, charcoal) placed beside related passages on a near-black page.

Read the whole article. Propose ONE leading visual drawn from its actual argument, objects or recurring metaphor, then AT MOST two smaller supporting cutouts, only where genuinely useful. Some posts need only one illustration or none: an empty list is fine.
Rules: each idea is one concrete object, scene or combination taken from THIS article. No generic AI brains, robots, lightbulbs, or rocket ships. No text, letters, logos or real people's likeness. Do not imply facts the article does not state.

Sections in the article are marked "## [LABEL] Heading" and numbered from 0 in order.

TITLE: ${body.title || "(untitled)"}
ARTICLE:
"""
${text.slice(0, 8000)}
"""

Respond ONLY with JSON:
{"ideas": [{"idea": "concrete description of the image", "passage": "the exact sentence from the article it illustrates", "placement": "lead" | "left" | "right", "after_section": 0, "alt": "meaningful alt text, under 120 characters"}]}
The first idea (if any) has placement "lead"; supporting ones alternate "right" then "left".`;
  const r = await geminiJson(prompt);
  const ideas = (Array.isArray(r.ideas) ? r.ideas : []).slice(0, 3).map((i: any, n: number) => ({
    idea: stripDashes(i.idea || "").text,
    passage: i.passage || "",
    placement: ["lead", "left", "right"].includes(i.placement) ? i.placement : (n === 0 ? "lead" : n === 1 ? "right" : "left"),
    after_section: Number.isInteger(i.after_section) ? i.after_section : n,
    alt: stripDashes(i.alt || "").text,
  }));
  return json({ ideas });
}

function cutoutPrompt(b: any): string {
  const scale = b.placement === "lead"
    ? "Wide leading image beside the opening sections, displayed about 390px wide on desktop"
    : "Small margin cutout beside a passage, displayed about 280px wide on desktop";
  // This is the reusable prompt from SITE-HANDOFF.md, verbatim except for the
  // background paragraph (see header comment).
  return `Create one standalone editorial cutout illustration for a Toni Esan blog article.

Article title: ${b.title || ""}
Relevant passage or article summary: ${b.passage || ""}
Specific image idea: ${b.idea || ""}
Placement and scale: ${scale}

Style: sophisticated handmade editorial collage. Layered cream paper, slightly irregular cut edges, expressive hand-inked outlines, subtle photocopy grain, restrained halftone shading and tactile screen-print texture. Combine recognisable objects thoughtfully.${b.hasRefs ? " Use the attached prototype cutouts as style references only; do not repeat their subjects unless this article calls for them." : ""}

Palette: off-white paper, charcoal black, muted cornflower blue and dusty cyan. A tiny burnt-orange accent is optional. The cutout will sit on a near-black webpage, so keep its silhouette readable without glow. Never use any green in the subject itself.

Output one isolated subject with generous clear padding, placed on a perfectly flat, uniform, fully saturated bright chroma green background (#00FF00, like a film green screen) with no shadow, gradient, texture or floor, so the background can be keyed out cleanly. No background scene, border, frame, mockup, letters, numbers, labels, logos, watermark, glossy 3D, generic AI brain imagery or unrelated objects. Depict only the specified idea. Do not invent factual details, identifiable people or claims absent from the article.`;
}

async function listModels(): Promise<any[]> {
  const res = await fetch(`${API}/models?pageSize=200&key=${GEMINI_API_KEY}`);
  const j = await res.json();
  return (j.models || []).map((m: any) => ({ name: (m.name || "").replace(/^models\//, ""), methods: m.supportedGenerationMethods }));
}

async function tryImage(model: string, prompt: string, refs: any[]) {
  const res = await fetch(`${API}/models/${model}:generateContent?key=${GEMINI_API_KEY}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [...refs.map((r) => ({ inlineData: { mimeType: r.mime, data: r.data } })), { text: prompt }] }],
      generationConfig: { responseModalities: ["TEXT", "IMAGE"], imageConfig: { aspectRatio: "1:1" } },
    }),
  });
  const j = await res.json();
  if (!res.ok) return { error: `${model}: ${res.status} ${JSON.stringify(j?.error?.message || j).slice(0, 200)}`, status: res.status };
  const part = (j?.candidates?.[0]?.content?.parts || []).find((p: any) => p.inlineData?.data || p.inline_data?.data);
  const data = part?.inlineData || part?.inline_data;
  if (!data) return { error: `${model}: no image in response (${JSON.stringify(j).slice(0, 200)})`, status: 200 };
  return { image_base64: data.data, mime: data.mimeType || data.mime_type || "image/png", model };
}

async function generateCutout(body: any) {
  if (!body.idea) return json({ error: "idea required" }, 400);
  const refs = (Array.isArray(body.style_refs) ? body.style_refs : [])
    .filter((r: any) => r && typeof r.data === "string" && /^image\//.test(r.mime || "")).slice(0, 3);
  const prompt = cutoutPrompt({ ...body, hasRefs: refs.length > 0 });
  const errors: string[] = [];
  let candidates = [...IMAGE_MODELS];
  for (let pass = 0; pass < 2; pass++) {
    for (const m of candidates) {
      const r: any = await tryImage(m, prompt, refs);
      if (r.image_base64) return json({ ...r, prompt });
      errors.push(r.error);
    }
    // Model names move fast. If none of the configured ones exist, ask the API
    // which image-capable models this key can see and try those once.
    const listed = (await listModels())
      .filter((m) => /image/.test(m.name) && (m.methods || []).includes("generateContent") && !candidates.includes(m.name))
      .map((m) => m.name);
    if (!listed.length) break;
    candidates = listed;
  }
  return json({ error: "Image generation failed", details: errors }, 502);
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
  try {
    switch (body.action) {
      case "shape": return await shape(body);
      case "cutout_ideas": return await cutoutIdeas(body);
      case "generate_cutout": return await generateCutout(body);
      case "models": return json({ models: await listModels() });
      default: return json({ error: "Unknown action" }, 400);
    }
  } catch (err) {
    console.error("blog-studio error:", err);
    return json({ error: String(err) }, 500);
  }
});
