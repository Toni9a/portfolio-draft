import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

/**
 * bookmark-ingest
 * ───────────────
 * Receives bookmark payloads from the xarchive fork and upserts them
 * into the inbox table. Called client-side from the extension after export.
 *
 * POST /functions/v1/bookmark-ingest
 * Authorization: Bearer <SUPABASE_ANON_KEY>
 *
 * Body (single bookmark or array):
 * {
 *   url: string
 *   source: "twitter" | "youtube" | "tiktok" | "manual"
 *   folder: string
 *   source_item_id?: string
 *   title?: string
 *   full_text?: string
 *   author_name?: string
 *   author_handle?: string
 *   media_urls?: string[]
 *   source_created_at?: string  // ISO 8601
 *   raw_data?: object
 * }
 */

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const body = await req.json();

    // Accept single item or array
    const items: Record<string, unknown>[] = Array.isArray(body) ? body : [body];

    if (items.length === 0) {
      return new Response(JSON.stringify({ error: "Empty payload" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Validate and sanitise each item
    const rows = items
      .filter((item) => typeof item.url === "string" && item.url.length > 0)
      .map((item) => ({
        url: item.url,
        source: item.source || "manual",
        folder: item.folder || null,
        source_item_id: item.source_item_id || null,
        title: item.title || null,
        full_text: item.full_text || null,
        author_name: item.author_name || null,
        author_handle: item.author_handle || null,
        media_urls: Array.isArray(item.media_urls) ? item.media_urls : [],
        status: "new",
        source_created_at: item.source_created_at || null,
        raw_data: item.raw_data || null,
      }));

    if (rows.length === 0) {
      return new Response(JSON.stringify({ error: "No valid items in payload" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Upsert — skip duplicates on URL, don't overwrite existing annotations
    const { data, error } = await supabase
      .from("inbox")
      .upsert(rows, { onConflict: "url", ignoreDuplicates: true });

    if (error) {
      console.error("Supabase upsert error:", error);
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response(
      JSON.stringify({ success: true, received: items.length, inserted: rows.length }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (err) {
    console.error("Unexpected error:", err);
    return new Response(JSON.stringify({ error: "Internal server error" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
