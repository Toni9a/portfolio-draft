import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { AwsClient } from "npm:aws4fetch@1.0.20";

// ---------------------------------------------------------------------------
// telegram-query  (second bot: QUERY the second brain, not capture into it)
//
// Deploy with --no-verify-jwt (verify_jwt: false): it's a public Telegram webhook, Telegram cannot
// send a Supabase JWT. Auth is (1) X-Telegram-Bot-Api-Secret-Token header and (2) a whitelist on the
// sender's Telegram user ID, both checked before anything touches the database.
//
// Secrets (Supabase function secrets): TG_QUERY_BOT_TOKEN, TG_QUERY_WEBHOOK_SECRET (new, this bot only),
// TELEGRAM_ALLOWED_USER_ID / GEMINI_API_KEY / R2_* / SUPABASE_* (shared with the other functions).
//
// Needs the DB helpers from migration telegram_query_bot_support (bot_tag_search, bot_cards,
// bot_folder_counts, bot_related_concepts, bot_node_card, bot_query_session) -- service_role only.
// ---------------------------------------------------------------------------

const BOT_TOKEN = Deno.env.get("TG_QUERY_BOT_TOKEN") ?? "";
const WEBHOOK_SECRET = Deno.env.get("TG_QUERY_WEBHOOK_SECRET") ?? "";
const ALLOWED_USER_ID = Deno.env.get("TELEGRAM_ALLOWED_USER_ID") ?? "";
const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY") ?? "";
const GEMINI_MODEL = "gemini-flash-latest";
const EMBEDDING_MODEL = Deno.env.get("GEMINI_EMBEDDING_MODEL") ?? "gemini-embedding-2";
const DIMS = 768; // must match node.embedding vector(768) and embed_nodes.py

const R2_ACCOUNT_ID = Deno.env.get("R2_ACCOUNT_ID") ?? "";
const R2_BUCKET = Deno.env.get("R2_BUCKET") ?? "capture-media";
const R2_ENDPOINT = `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`;
const r2 = new AwsClient({
  service: "s3",
  region: "auto",
  accessKeyId: Deno.env.get("R2_ACCESS_KEY_ID") ?? "",
  secretAccessKey: Deno.env.get("R2_SECRET_ACCESS_KEY") ?? "",
});

const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
const TG_API = `https://api.telegram.org/bot${BOT_TOKEN}`;

const PAGE_SIZE = 8;
const MAX_RESULTS = 64;

type Intent = "pics" | "links" | "folders" | "help";
type Plan = { intent: Intent; folder: string | null; terms: string[]; semantic_query: string; topic: string; transcript: string };
type Item = { n: number; k: string | null; f: string | null; t: string; u: string | null; h: string | null; m: string[]; s: string | null };
type Payload = { plan: Plan; items: Item[]; chips: string[] };
type FolderRow = { folder: string; items: number; with_pics: number };

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escAttr = (s: string) => esc(s).replace(/"/g, "&quot;");

function cleanTitle(s: string | null | undefined): string {
  const t = (s ?? "").replace(/https?:\/\/t\.co\/\w+/g, "").replace(/\s+/g, " ").trim();
  return t || "(no caption)";
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function rpc(fn: string, args: Record<string, unknown>): Promise<any[]> {
  const { data, error } = await supabase.rpc(fn, args);
  if (error) throw error;
  return (data ?? []) as any[];
}

// ---------------------------------------------------------------------------
// Telegram helpers
// ---------------------------------------------------------------------------

async function tg(method: string, payload: Record<string, unknown>) {
  const res = await fetch(`${TG_API}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const json = await res.json();
  if (!json.ok) console.error(`Telegram ${method} failed:`, json.error_code, json.description);
  return json;
}

async function tgForm(method: string, form: FormData) {
  const res = await fetch(`${TG_API}/${method}`, { method: "POST", body: form });
  const json = await res.json();
  if (!json.ok) console.error(`Telegram ${method} (upload) failed:`, json.error_code, json.description);
  return json;
}

async function sendText(
  chatId: number,
  text: string,
  opts: { html?: boolean; markup?: unknown; replyTo?: number } = {},
) {
  const p: Record<string, unknown> = {
    chat_id: chatId,
    text: text.slice(0, 4000),
    link_preview_options: { is_disabled: true },
  };
  if (opts.html) p.parse_mode = "HTML";
  if (opts.markup) p.reply_markup = opts.markup;
  if (opts.replyTo) p.reply_to_message_id = opts.replyTo;
  return tg("sendMessage", p);
}

const chatAction = (chatId: number, action: string) => tg("sendChatAction", { chat_id: chatId, action });

function keyboard(rows: { text: string; callback_data: string }[][]) {
  return { inline_keyboard: rows.filter((r) => r.length) };
}

function chipRows(sid: string, chips: string[]) {
  const rows: { text: string; callback_data: string }[][] = [];
  for (let i = 0; i < chips.length; i += 2) {
    rows.push(chips.slice(i, i + 2).map((c, j) => ({ text: `🏷 ${c}`.slice(0, 40), callback_data: `chip:${sid}:${i + j}` })));
  }
  return rows;
}

// ---------------------------------------------------------------------------
// R2 / photos
// ---------------------------------------------------------------------------

const objUrl = (key: string) => `${R2_ENDPOINT}/${R2_BUCKET}/${key.split("/").map(encodeURIComponent).join("/")}`;

async function presign(key: string): Promise<string> {
  const signed = await r2.sign(new Request(`${objUrl(key)}?X-Amz-Expires=3600`), { aws: { signQuery: true } });
  return signed.url.toString();
}

async function fetchR2Blob(key: string): Promise<Blob | null> {
  try {
    const signed = await r2.sign(new Request(objUrl(key)));
    const res = await fetch(signed);
    if (!res.ok) return null;
    return await res.blob();
  } catch (err) {
    console.error("R2 fetch failed:", err);
    return null;
  }
}

// Last-resort path for a single image Telegram wouldn't take by URL (over ~5MB, odd dimensions...):
// pull the bytes ourselves and upload -- as a photo first, then as a plain document.
async function sendImageByUpload(chatId: number, key: string, caption: string): Promise<boolean> {
  const blob = await fetchR2Blob(key);
  if (!blob) return false;
  const name = key.split("/").pop() || "image.jpg";
  for (const [method, field] of [["sendPhoto", "photo"], ["sendDocument", "document"]] as const) {
    const form = new FormData();
    form.append("chat_id", String(chatId));
    form.append("caption", caption);
    form.append(field, blob, name);
    const r = await tgForm(method, form);
    if (r.ok) return true;
  }
  return false;
}

function caption(i: Item): string {
  const head = [i.f ? `📁 ${i.f}` : null, i.h ? `@${i.h}` : null].filter(Boolean).join(" · ");
  const tags = i.m.slice(0, 3).join(", ");
  return [head, cleanTitle(i.t).slice(0, 180), tags ? `🏷 ${tags}` : null, i.u]
    .filter(Boolean)
    .join("\n")
    .slice(0, 1000);
}

async function sendPhotos(chatId: number, items: Item[]): Promise<number> {
  const withKey = items.filter((i) => i.k);
  if (!withKey.length) return 0;
  const urls = await Promise.all(withKey.map((i) => presign(i.k!)));

  // Fast path: one album, Telegram fetches the presigned URLs itself.
  if (withKey.length >= 2) {
    const r = await tg("sendMediaGroup", {
      chat_id: chatId,
      media: withKey.map((i, idx) => ({ type: "photo", media: urls[idx], caption: caption(i) })),
    });
    if (r.ok) return withKey.length;
  } else {
    const r = await tg("sendPhoto", { chat_id: chatId, photo: urls[0], caption: caption(withKey[0]) });
    if (r.ok) return 1;
  }

  // Fallback: one at a time, by URL then by upload, so a single bad image can't sink the whole page.
  let sent = 0;
  for (let idx = 0; idx < withKey.length; idx++) {
    const i = withKey[idx];
    const r = await tg("sendPhoto", { chat_id: chatId, photo: urls[idx], caption: caption(i) });
    if (r.ok || (await sendImageByUpload(chatId, i.k!, caption(i)))) sent++;
  }
  return sent;
}

// ---------------------------------------------------------------------------
// Gemini
// ---------------------------------------------------------------------------

async function callGemini(parts: unknown[]): Promise<string> {
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contents: [{ role: "user", parts }], generationConfig: { responseMimeType: "application/json" } }),
    },
  );
  const json = await res.json();
  const text = json?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error(`Gemini returned no text (status ${res.status}): ${JSON.stringify(json).slice(0, 200)}`);
  return text;
}

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
  if (!Array.isArray(values)) throw new Error(`Embedding failed (status ${res.status})`);
  return values;
}

// ---------------------------------------------------------------------------
// Folders + query planning
// ---------------------------------------------------------------------------

let folderCache: { rows: FolderRow[]; ts: number } | null = null;
async function getFolders(): Promise<FolderRow[]> {
  if (folderCache && Date.now() - folderCache.ts < 5 * 60 * 1000) return folderCache.rows;
  const rows = (await rpc("bot_folder_counts", {})) as FolderRow[];
  folderCache = { rows, ts: Date.now() };
  return rows;
}

function sanitizeTerms(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const out = new Set<string>();
  for (const t of raw) {
    const s = String(t).toLowerCase().replace(/[^a-z0-9 \-]/g, " ").replace(/\s+/g, " ").trim();
    if (s.length >= 3 && s.length <= 30) out.add(s);
  }
  return [...out].slice(0, 10);
}

async function planQuery(
  input: { text?: string; audio?: { b64: string; mime: string }; force?: Intent },
  folders: FolderRow[],
): Promise<Plan> {
  const folderList = folders.map((f) => `"${f.folder}" (${f.items} items, ${f.with_pics} with images)`).join("; ");
  const prompt =
    "You turn a request into a search plan over Toni's personal 'second brain': ~1,100 saved bookmarks, images and notes, " +
    "each tagged by Gemini with concepts and visual tags (e.g. 'forest wallpaper', 'landscape photography'), organised in folders.\n" +
    `Existing folders: ${folderList}.\n` +
    "The request may be dictated by voice or voice-to-text, so folder names can be misheard. Map to the closest existing folder: " +
    "'hard picks' means 'hard pics'; 'journey aesthetics' / 'journey' / 'mid journey' means 'MJ aesthetic' (MJ = Midjourney). " +
    "'Hard projects' is a DIFFERENT folder from 'hard pics'. Only set a folder if the request implies one.\n" +
    "Return ONLY JSON: {\"intent\":\"pics|links|folders|help\",\"folder\":<exact existing folder name or null>," +
    "\"terms\":[...],\"semantic_query\":\"...\",\"topic\":\"...\",\"transcript\":\"...\"}.\n" +
    "intent: 'pics' when he wants to SEE images / pictures / inspiration / aesthetics; 'links' when he asks what connects to, " +
    "relates to, or what he has on a topic; 'folders' when asking what folders/categories exist; 'help' when asking what you can do.\n" +
    "terms: 4-10 lowercase words or short phrases that tags/concepts might contain for this request, INCLUDING synonyms and specific " +
    "sub-topics (for 'nature': nature, forest, plants, flowers, landscape, mountains, ocean, botanical, trees). Use [] if the request is " +
    "only 'show me pics from <folder>' with no subject.\n" +
    "semantic_query: one short natural phrase describing what to find ('' if no subject). topic: a 1-4 word label for the subject " +
    "(or the folder name if no subject). transcript: verbatim words heard if audio was given, else ''." +
    (input.force ? `\nThe intent is FORCED to '${input.force}'.` : "");

  const parts: unknown[] = [{ text: prompt + (input.text ? `\n\nREQUEST: ${input.text}` : "\n\nThe request is in the attached audio.") }];
  if (input.audio) parts.push({ inlineData: { mimeType: input.audio.mime, data: input.audio.b64 } });

  let parsed: any = null;
  try {
    parsed = JSON.parse(await callGemini(parts));
  } catch (err) {
    console.error("Planner failed, using fallback plan:", err);
  }

  const rawText = input.text ?? "";
  const fallbackTerms = sanitizeTerms(rawText.split(/[^A-Za-z0-9\-]+/).filter((w) => w.length >= 3).slice(0, 6));
  const folder = folders.find((f) => f.folder.toLowerCase() === String(parsed?.folder ?? "").toLowerCase())?.folder ?? null;
  const intentRaw = String(parsed?.intent ?? "");
  const intent: Intent = input.force ?? (["pics", "links", "folders", "help"].includes(intentRaw) ? (intentRaw as Intent) : "pics");
  const terms = parsed ? sanitizeTerms(parsed.terms) : fallbackTerms;
  const semantic = String(parsed?.semantic_query ?? (parsed ? "" : rawText)).slice(0, 200);
  const topic = String(parsed?.topic || folder || rawText || "your saves").slice(0, 40);
  return { intent, folder, terms, semantic_query: semantic, topic, transcript: String(parsed?.transcript ?? "") };
}

// ---------------------------------------------------------------------------
// Retrieval
// ---------------------------------------------------------------------------

const toItem = (c: any, matched: string[] = []): Item => ({
  n: Number(c.node_id),
  k: c.image_key ?? null,
  f: c.folder ?? null,
  t: String(c.title ?? "").slice(0, 200),
  u: c.url ?? null,
  h: c.author_handle ?? null,
  m: matched,
  s: c.source_table ?? null,
});

async function semanticIds(q: string, n: number): Promise<number[]> {
  if (!q.trim()) return [];
  try {
    const embedding = await embedQuery(q);
    const { data, error } = await supabase.rpc("match_nodes", { query_embedding: embedding, match_count: n });
    if (error) throw error;
    return (data ?? []).map((r: any) => Number(r.id));
  } catch (err) {
    console.error("Semantic search failed (continuing with tags only):", err);
    return [];
  }
}

async function findPics(plan: Plan): Promise<Item[]> {
  const hasQuery = plan.terms.length > 0 || plan.semantic_query.trim().length > 0;

  // "Show me hard pics" with no subject -> a shuffled sample of that folder (or everything).
  if (!hasQuery) {
    let q = supabase
      .from("bot_node_card")
      .select("node_id, kind, source_table, title, url, folder, inbox_id, author_handle, image_key")
      .not("image_key", "is", null)
      .limit(300);
    if (plan.folder) q = q.eq("folder", plan.folder);
    const { data, error } = await q;
    if (error) throw error;
    return shuffle(data ?? []).slice(0, MAX_RESULTS).map((c: any) => toItem(c));
  }

  const [tagHits, semIds] = await Promise.all([
    plan.terms.length
      ? rpc("bot_tag_search", { terms: plan.terms, folder_filter: plan.folder, pics_only: true, lim: 150 })
      : Promise.resolve([] as any[]),
    semanticIds(plan.semantic_query || plan.topic, 60),
  ]);
  const semCards = semIds.length
    ? await rpc("bot_cards", { node_ids: semIds, folder_filter: plan.folder, pics_only: true })
    : [];

  const merged = new Map<number, { card: any; tag: number; matched: string[]; semRank: number | null }>();
  for (const h of tagHits) {
    merged.set(Number(h.node_id), { card: h, tag: Number(h.score) || 0, matched: h.matched ?? [], semRank: null });
  }
  const rankOf = new Map(semIds.map((id, idx) => [id, idx]));
  for (const c of semCards) {
    const id = Number(c.node_id);
    const existing = merged.get(id);
    if (existing) existing.semRank = rankOf.get(id) ?? null;
    else merged.set(id, { card: c, tag: 0, matched: [], semRank: rankOf.get(id) ?? null });
  }

  const scored = [...merged.values()].map((m) => ({
    m,
    score: Math.min(m.tag, 5) + (m.semRank !== null ? 3 * (1 - m.semRank / 60) : 0),
  }));
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, MAX_RESULTS).map((s) => toItem(s.m.card, s.m.matched));
}

async function relatedChips(nodeIds: number[], excludeTerms: string[], folders: FolderRow[]): Promise<{ label: string; n: number }[]> {
  if (!nodeIds.length) return [];
  try {
    const rows = await rpc("bot_related_concepts", { node_ids: nodeIds, exclude_terms: excludeTerms, lim: 14 });
    const folderNames = new Set(folders.map((f) => f.folder.toLowerCase()));
    return rows
      .filter((r) => !folderNames.has(String(r.label).toLowerCase()))
      .map((r) => ({ label: String(r.label), n: Number(r.n) }));
  } catch (err) {
    console.error("Related concepts failed:", err);
    return [];
  }
}

async function saveSession(payload: Payload): Promise<string> {
  // Housekeeping: paging state is only useful for a short while.
  await supabase.from("bot_query_session").delete().lt("created_at", new Date(Date.now() - 7 * 86400_000).toISOString());
  const { data, error } = await supabase.from("bot_query_session").insert({ payload }).select("id").single();
  if (error) throw error;
  return data.id as string;
}

// ---------------------------------------------------------------------------
// Intents
// ---------------------------------------------------------------------------

async function sendPicsPage(chatId: number, sid: string, payload: Payload, offset: number) {
  const { plan, items, chips } = payload;
  const slice = items.slice(offset, offset + PAGE_SIZE);
  await chatAction(chatId, "upload_photo");
  const sent = await sendPhotos(chatId, slice);

  const end = offset + slice.length;
  const lines = [`🖼 ${offset + 1}–${end} of ${items.length} · ${plan.folder ?? "all folders"} · ${plan.topic}`];
  if (sent < slice.length) lines.push(`⚠️ ${slice.length - sent} image(s) couldn't be sent.`);
  const actions: { text: string; callback_data: string }[] = [];
  if (end < items.length) actions.push({ text: `More ▶ (${items.length - end} left)`, callback_data: `more:${sid}:${end}` });
  actions.push({ text: "🔗 What's linked", callback_data: `lnk:${sid}` });
  await sendText(chatId, lines.join("\n"), { markup: keyboard([...chipRows(sid, chips), actions]) });
}

async function runPics(chatId: number, plan: Plan) {
  await chatAction(chatId, "typing");
  const [items, folders] = await Promise.all([findPics(plan), getFolders()]);
  if (!items.length) {
    await sendText(
      chatId,
      `Nothing with pictures matched "${plan.topic}"${plan.folder ? ` in ${plan.folder}` : ""}. Try a broader word, drop the folder, or /folders.`,
    );
    return;
  }
  const chips = (await relatedChips(items.slice(0, 30).map((i) => i.n), plan.terms, folders)).slice(0, 6).map((c) => c.label);
  const payload: Payload = { plan, items, chips };
  const sid = await saveSession(payload);
  await sendPicsPage(chatId, sid, payload, 0);
}

async function runLinks(chatId: number, plan: Plan) {
  await chatAction(chatId, "typing");
  const terms = plan.terms.length ? plan.terms : sanitizeTerms([plan.topic]);
  const [direct, semIds, folders] = await Promise.all([
    terms.length ? rpc("bot_tag_search", { terms, folder_filter: plan.folder, pics_only: false, lim: 60 }) : Promise.resolve([] as any[]),
    semanticIds(plan.semantic_query || plan.topic, 30),
    getFolders(),
  ]);
  const directIds = new Set(direct.map((d) => Number(d.node_id)));
  const wantSem = semIds.filter((id) => !directIds.has(id));
  const semCardsRaw = wantSem.length ? await rpc("bot_cards", { node_ids: wantSem, folder_filter: plan.folder, pics_only: false }) : [];
  const semOrder = new Map(wantSem.map((id, idx) => [id, idx]));
  const semCards = semCardsRaw.sort((a, b) => (semOrder.get(Number(a.node_id)) ?? 0) - (semOrder.get(Number(b.node_id)) ?? 0));
  const related = await relatedChips([...directIds].slice(0, 40), terms, folders);

  if (!direct.length && !semCards.length) {
    await sendText(chatId, `Nothing linked to "${plan.topic}" yet.`);
    return;
  }

  const line = (c: any) => {
    const title = esc(cleanTitle(c.title).slice(0, 80));
    const url = typeof c.url === "string" && /^https?:\/\//i.test(c.url) ? c.url : null;
    const label = url ? `<a href="${escAttr(url)}">${title}</a>` : title;
    const where = c.folder ? ` · ${esc(c.folder)}` : c.source_table && c.source_table !== "inbox" ? ` · ${esc(String(c.source_table))}` : "";
    return `• ${label}${where}`;
  };

  const byFolder = new Map<string, number>();
  for (const d of direct) if (d.folder) byFolder.set(d.folder, (byFolder.get(d.folder) ?? 0) + 1);
  const topFolders = [...byFolder.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([f, n]) => `${esc(f)} (${n})`).join(", ");

  const head = `🔗 <b>${esc(plan.topic)}</b>\n${direct.length}${direct.length >= 60 ? "+" : ""} tagged directly${topFolders ? ` · mostly ${topFolders}` : ""}`;
  const sections: string[] = [head];
  if (direct.length) sections.push("<b>Tagged with this</b>\n" + direct.slice(0, 8).map(line).join("\n"));
  if (semCards.length) sections.push("<b>Close in meaning</b>\n" + semCards.slice(0, 5).map(line).join("\n"));
  const chipLabels = related.slice(0, 6).map((r) => r.label);
  if (related.length) sections.push("<b>Often appears with</b>\n" + related.slice(0, 8).map((r) => `${esc(r.label)} (${r.n})`).join(" · "));

  const payload: Payload = { plan: { ...plan, terms }, items: [], chips: chipLabels };
  const sid = await saveSession(payload);
  await sendText(chatId, sections.join("\n\n"), {
    html: true,
    markup: keyboard([...chipRows(sid, chipLabels), [{ text: "🖼 See the pictures", callback_data: `pic:${sid}` }]]),
  });
}

async function runFolders(chatId: number) {
  const folders = await getFolders();
  const text = "📁 <b>Folders</b>\n" + folders.map((f) => `• ${esc(f.folder)} — ${f.items} items, ${f.with_pics} with pictures`).join("\n");
  const withPics = folders.filter((f) => f.with_pics >= 3).slice(0, 8);
  const rows: { text: string; callback_data: string }[][] = [];
  for (let i = 0; i < withPics.length; i += 2) {
    rows.push(withPics.slice(i, i + 2).map((f) => ({ text: `🖼 ${f.folder}`.slice(0, 40), callback_data: `fld:${f.folder}`.slice(0, 60) })));
  }
  await sendText(chatId, text, { html: true, markup: keyboard(rows) });
}

const HELP =
  "👋 I search your second brain.\n\n" +
  "Just type or send a voice note:\n" +
  "• \"nature inspiration from hard pics\"\n" +
  "• \"show me my MJ aesthetic\"\n" +
  "• \"what do I have linked to typography?\"\n\n" +
  "Commands: /pics <topic> · /links <topic> · /folders\n" +
  "Under the results: More, 🏷 related tags to narrow, and 🔗 / 🖼 to flip between links and pictures.";

async function runPlan(chatId: number, plan: Plan) {
  if (plan.intent === "help") return void (await sendText(chatId, HELP));
  if (plan.intent === "folders") return void (await runFolders(chatId));
  if (plan.intent === "links") return void (await runLinks(chatId, plan));
  return void (await runPics(chatId, plan));
}

// ---------------------------------------------------------------------------
// Update handlers
// ---------------------------------------------------------------------------

async function downloadVoice(fileId: string): Promise<{ b64: string; mime: string } | null> {
  const f = await tg("getFile", { file_id: fileId });
  const path = f?.result?.file_path;
  if (!path) return null;
  const res = await fetch(`https://api.telegram.org/file/bot${BOT_TOKEN}/${path}`);
  if (!res.ok) return null;
  const buf = new Uint8Array(await res.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return { b64: btoa(bin), mime: "audio/ogg" };
}

async function handleMessage(msg: any) {
  if (String(msg.from?.id ?? "") !== ALLOWED_USER_ID) return; // silently ignore anyone else
  const chatId: number = msg.chat.id;

  try {
    const folders = await getFolders();

    if (msg.voice) {
      await chatAction(chatId, "typing");
      const audio = await downloadVoice(msg.voice.file_id);
      if (!audio) return void (await sendText(chatId, "⚠️ Couldn't download that voice note — try again?"));
      const plan = await planQuery({ audio }, folders);
      if (plan.transcript) await sendText(chatId, `🎙 “${plan.transcript.slice(0, 200)}”`);
      return void (await runPlan(chatId, plan));
    }

    const text: string = typeof msg.text === "string" ? msg.text.trim() : "";
    if (!text) return void (await sendText(chatId, "I take text or voice — try “nature pics from hard pics”, or /help."));

    const cmd = text.match(/^\/(\w+)(?:@\w+)?\s*([\s\S]*)$/);
    if (cmd) {
      const name = cmd[1].toLowerCase();
      const rest = cmd[2].trim();
      if (name === "start" || name === "help") return void (await sendText(chatId, HELP));
      if (name === "folders") return void (await runFolders(chatId));
      if (name === "pics" || name === "links") {
        if (!rest) return void (await sendText(chatId, `Usage: /${name} <topic>, e.g. /${name} nature`));
        const plan = await planQuery({ text: rest, force: name as Intent }, folders);
        return void (await runPlan(chatId, plan));
      }
      return void (await sendText(chatId, "Unknown command — /help lists what I can do."));
    }

    await chatAction(chatId, "typing");
    const plan = await planQuery({ text }, folders);
    await runPlan(chatId, plan);
  } catch (err) {
    console.error("handleMessage error:", err);
    await sendText(chatId, "⚠️ Hit an error running that — try again in a moment?");
  }
}

async function handleCallback(cq: any) {
  if (String(cq.from?.id ?? "") !== ALLOWED_USER_ID) {
    await tg("answerCallbackQuery", { callback_query_id: cq.id });
    return;
  }
  const chatId: number = cq.message?.chat?.id;
  const data: string = cq.data ?? "";
  await tg("answerCallbackQuery", { callback_query_id: cq.id });

  try {
    if (data.startsWith("fld:")) {
      const folders = await getFolders();
      const folder = folders.find((f) => f.folder === data.slice(4))?.folder ?? null;
      if (!folder) return void (await sendText(chatId, "That folder no longer exists — /folders to refresh."));
      return void (await runPics(chatId, { intent: "pics", folder, terms: [], semantic_query: "", topic: folder, transcript: "" }));
    }

    const [action, sid, arg] = data.split(":");
    const { data: row, error } = await supabase.from("bot_query_session").select("payload").eq("id", sid).maybeSingle();
    if (error || !row) return void (await sendText(chatId, "That search has expired — just ask again."));
    const payload = row.payload as Payload;

    if (action === "more") {
      const offset = Math.max(0, Number(arg) || 0);
      return void (await sendPicsPage(chatId, sid, payload, offset));
    }
    if (action === "chip") {
      const label = payload.chips[Number(arg)];
      if (!label) return void (await sendText(chatId, "That tag is no longer available."));
      const keepIntent: Intent = payload.plan.intent === "links" ? "links" : "pics";
      return void (await runPlan(chatId, {
        ...payload.plan,
        intent: keepIntent,
        terms: sanitizeTerms([label]),
        semantic_query: label,
        topic: label,
        folder: keepIntent === "pics" ? payload.plan.folder : null,
      }));
    }
    if (action === "lnk") return void (await runLinks(chatId, { ...payload.plan, intent: "links", folder: null }));
    if (action === "pic") return void (await runPics(chatId, { ...payload.plan, intent: "pics" }));
  } catch (err) {
    console.error("handleCallback error:", err);
    await sendText(chatId, "⚠️ Hit an error — try again in a moment?");
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

const seenUpdates: number[] = []; // drop Telegram re-deliveries within a warm instance

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });

  // Fail closed: refuse everything if the secrets aren't configured yet.
  if (!WEBHOOK_SECRET || !BOT_TOKEN || !ALLOWED_USER_ID) {
    console.error("telegram-query: secrets not configured.");
    return new Response("Not configured", { status: 503 });
  }
  if (req.headers.get("x-telegram-bot-api-secret-token") !== WEBHOOK_SECRET) {
    console.warn("Rejected webhook call: bad or missing secret token header.");
    return new Response("Unauthorized", { status: 401 });
  }

  let update: any;
  try {
    update = await req.json();
  } catch {
    return new Response("Bad request", { status: 400 });
  }

  if (typeof update.update_id === "number") {
    if (seenUpdates.includes(update.update_id)) return new Response("OK", { status: 200 });
    seenUpdates.push(update.update_id);
    if (seenUpdates.length > 50) seenUpdates.shift();
  }

  try {
    if (update.callback_query) await handleCallback(update.callback_query);
    else if (update.message) await handleMessage(update.message);
  } catch (err) {
    console.error("Unhandled error processing update:", err);
  }
  return new Response("OK", { status: 200 });
});
