// Cleanup Expired Temp Screenshots
//
// This Edge Function handles the cleanup of temporary screenshots that haven't
// been confirmed within the retention period (default 48 hours).
//
// It performs two operations:
// 1. Delete files from Supabase Storage bucket
// 2. Delete records from public_media database table
//
// Usage:
//   curl -X POST "https://<project>.supabase.co/functions/v1/cleanup-temp-screenshots" \
//     -H "Authorization: Bearer <SUPABASE_ANON_KEY>" \
//     -H "Content-Type: application/json" \
//     -d '{"hours_old": 48}'

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // Get Supabase credentials from environment
    const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
    const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

    if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
      throw new Error("Missing Supabase environment variables");
    }

    // Parse hours_old from request body (default 48)
    let hours_old = 48;
    try {
      const body = await req.json();
      hours_old = body.hours_old ?? 48;
    } catch {
      // Use default if body parsing fails
    }

    // Validate hours_old
    if (typeof hours_old !== "number" || hours_old < 1 || hours_old > 720) {
      throw new Error("hours_old must be a number between 1 and 720");
    }

    // Create Supabase client with service role key
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

    // Calculate cutoff timestamp
    const cutoffDate = new Date(Date.now() - hours_old * 60 * 60 * 1000);

    // 1. Query expired temp screenshots
    const { data: expiredItems, error: queryError } = await supabase
      .from("public_media")
      .select("id, storage_path, storage_bucket")
      .eq("type", "screenshot")
      .lt("created_at", cutoffDate.toISOString())
      .not("metadata->storage_status", "neq", "temp");  // Get items where storage_status = 'temp'

    if (queryError) {
      throw new Error(`Query failed: ${queryError.message}`);
    }

    // Also try with direct filter (backup approach)
    const { data: expiredItems2, error: queryError2 } = await supabase
      .from("public_media")
      .select("id, storage_path, storage_bucket")
      .lt("created_at", cutoffDate.toISOString())
      .filter("metadata->>storage_status", "eq", "temp");

    // Use whichever query returned results
    const itemsToDelete = expiredItems?.length ? expiredItems : (expiredItems2 || []);

    if (!itemsToDelete || itemsToDelete.length === 0) {
      return new Response(
        JSON.stringify({
          deleted_count: 0,
          message: "No expired temp screenshots found",
          hours_checked: hours_old,
          cutoff_date: cutoffDate.toISOString()
        }),
        {
          status: 200,
          headers: { ...corsHeaders, "Content-Type": "application/json" }
        }
      );
    }

    console.log(`Found ${itemsToDelete.length} expired temp screenshots to delete`);

    // 2. Delete files from storage bucket
    const storagePaths = itemsToDelete
      .filter((item) => item.storage_path)
      .map((item) => item.storage_path);

    let storageDeleteError: string | null = null;
    if (storagePaths.length > 0) {
      const { error: storageError } = await supabase.storage
        .from("public_media")
        .remove(storagePaths);

      if (storageError) {
        console.error("Storage deletion error (continuing):", storageError.message);
        storageDeleteError = storageError.message;
        // Continue anyway - some files might not exist or already be deleted
      } else {
        console.log(`Deleted ${storagePaths.length} files from storage`);
      }
    }

    // 3. Delete records from database
    const idsToDelete = itemsToDelete.map((item) => item.id);
    const { error: deleteError } = await supabase
      .from("public_media")
      .delete()
      .in("id", idsToDelete);

    if (deleteError) {
      throw new Error(`Database deletion failed: ${deleteError.message}`);
    }

    console.log(`Deleted ${idsToDelete.length} records from database`);

    // Return success response
    return new Response(
      JSON.stringify({
        deleted_count: itemsToDelete.length,
        storage_paths_removed: storagePaths,
        storage_error: storageDeleteError,
        message: `Deleted ${itemsToDelete.length} expired temp screenshots`,
        hours_checked: hours_old,
        cutoff_date: cutoffDate.toISOString()
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      }
    );

  } catch (error) {
    console.error("Cleanup error:", error);
    return new Response(
      JSON.stringify({
        error: error.message || "Unknown error",
        deleted_count: 0
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" }
      }
    );
  }
});
